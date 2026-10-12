from app.models import Decision,DecisionAuditEvent
from conftest import bearer

PAYLOAD={'request_id':'router-test-0001','task_code':'DICOM_ROUTER_ERROR','task_version':'1.0',
         'source_id':'branch-ae-1','destination_id':'pacs-main','error_code':'UNRECOGNIZED_VENDOR_ERROR','retry_count':1}

def test_evaluate_requires_signed_identity(api):
    client,private,_=api
    assert client.post('/api/v1/decisions/evaluate',json=PAYLOAD).status_code==401

def test_unknown_router_error_is_audited_and_queued_without_execution(api):
    client,private,Session=api
    response=client.post('/api/v1/decisions/evaluate',json=PAYLOAD,headers=bearer(private))
    assert response.status_code==200
    body=response.json()
    assert body['status']=='NEEDS_REVIEW' and body['review_required']
    assert body['provider']=='RULES' and body['suggested_action']=='HUMAN_REVIEW'
    assert body['execution_allowed'] is False
    with Session() as db:
        row=db.get(Decision,body['decision_id'])
        assert set(row.evidence)=={'source_id','destination_id','error_code','retry_count'}
        assert db.query(DecisionAuditEvent).filter_by(decision_id=row.id).count()==1

def test_same_idempotency_key_is_replay_safe_and_changed_input_conflicts(api):
    client,private,_=api;headers=bearer(private)
    first=client.post('/api/v1/decisions/evaluate',json=PAYLOAD,headers=headers)
    same=client.post('/api/v1/decisions/evaluate',json=PAYLOAD,headers=headers)
    changed={**PAYLOAD,'error_code':'ASSOCIATION_TIMEOUT'}
    conflict=client.post('/api/v1/decisions/evaluate',json=changed,headers=headers)
    assert first.json()['decision_id']==same.json()['decision_id']
    assert conflict.status_code==409

def test_rejects_unapproved_fields_and_tasks(api):
    client,private,_=api;headers=bearer(private)
    assert client.post('/api/v1/decisions/evaluate',json={**PAYLOAD,'patient_id':'PHI'},headers=headers).status_code==422
    assert client.post('/api/v1/decisions/evaluate',json={**PAYLOAD,'task_code':'PATIENT_IDENTITY'},headers=headers).status_code==422
    assert client.post('/api/v1/decisions/evaluate',json={**PAYLOAD,'error_code':'patient 12345'},headers=headers).status_code==422

def test_reviews_are_branch_scoped_and_cannot_run_actions(api):
    client,private,_=api
    review_headers=bearer(private,sub='supervisor-1',roles=['HELPDESK_SUPERVISOR'])
    created=client.post('/api/v1/decisions/evaluate',json=PAYLOAD,headers=bearer(private)).json()
    assert len(client.get('/api/v1/reviews',headers=review_headers).json())==1
    foreign=bearer(private,sub='supervisor-2',branch='other-branch',roles=['HELPDESK_SUPERVISOR'])
    assert client.post(f"/api/v1/reviews/{created['decision_id']}",json={'outcome':'ACCEPTED','reason_code':'CONFIRMED_CATEGORY'},headers=foreign).status_code==404
    done=client.post(f"/api/v1/reviews/{created['decision_id']}",json={'outcome':'ACCEPTED','reason_code':'CONFIRMED_CATEGORY'},headers=review_headers)
    assert done.status_code==200 and done.json()['status']=='REVIEWED'
    assert done.json()['reason_code']=='CONFIRMED_CATEGORY'
    assert client.post(f"/api/v1/reviews/{created['decision_id']}",json={'outcome':'ACCEPTED','reason_code':'NOT_ACTIONABLE'},headers=review_headers).status_code==409

def test_jev_is_opt_in_and_any_suggestion_remains_human_review(api,monkeypatch):
    client,private,Session=api
    from app import main
    from app.providers.jev import JevSuggestion
    monkeypatch.setenv('DECISION_PROVIDER','jev')
    monkeypatch.setenv('JEV_ENABLED','true')
    monkeypatch.setenv('JEV_API_KEY','synthetic-test-key')
    calls=[]
    def fake_suggest(code,retries):
        calls.append((code,retries))
        return JevSuggestion('TRANSFER',0.99,'jev-test',10,2)
    monkeypatch.setattr(main,'suggest_category',fake_suggest)
    response=client.post('/api/v1/decisions/evaluate',json=PAYLOAD,headers=bearer(private))
    assert response.status_code==200 and calls==[]  # Unknown codes never leave the service.
    restricted={**PAYLOAD,'request_id':'router-test-0002','error_code':'C_STORE_FAILURE'}
    response=client.post('/api/v1/decisions/evaluate',json=restricted,headers=bearer(private))
    body=response.json()
    assert calls==[('C_STORE_FAILURE',1)]
    assert body['provider']=='JEV' and body['model_suggestion']=='TRANSFER' and body['model_confidence']==0.99
    assert body['status']=='NEEDS_REVIEW' and body['review_required'] and body['execution_allowed'] is False
    with Session() as db:
        from app.models import DecisionAuditEvent
        events=db.query(DecisionAuditEvent).filter_by(decision_id=body['decision_id']).all()
        assert {event.event_type for event in events}=={'DECISION_CLASSIFIED','PROVIDER_REQUESTED','JEV_SUGGESTION'}

def test_jev_failure_records_safe_audit_and_falls_back_to_rules(api,monkeypatch):
    client,private,Session=api
    from app import main
    from app.providers.jev import JevUnavailable
    monkeypatch.setenv('DECISION_PROVIDER','jev')
    monkeypatch.setenv('JEV_ENABLED','true')
    monkeypatch.setenv('JEV_API_KEY','synthetic-test-key')
    monkeypatch.setenv('OPENAI_DECISIONS_ENABLED','true')
    monkeypatch.setenv('OPENAI_API_KEY','synthetic-openai-key')
    monkeypatch.setenv('DECISION_PROVIDER_ORDER','jev,openai')
    openai_calls=[]
    monkeypatch.setattr(main,'suggest_openai_category',lambda *args:openai_calls.append(args))
    monkeypatch.setattr(main,'suggest_category',lambda *_: (_ for _ in ()).throw(JevUnavailable('private details')))
    payload={**PAYLOAD,'request_id':'router-test-0003','error_code':'C_STORE_FAILURE'}
    response=client.post('/api/v1/decisions/evaluate',json=payload,headers=bearer(private))
    body=response.json()
    assert body['status']=='NEEDS_REVIEW' and body['provider']=='RULES'
    assert body['model_suggestion'] is None and body['execution_allowed'] is False
    assert openai_calls==[]  # Auto selection does not fail over after the chosen provider fails.
    with Session() as db:
        from app.models import DecisionAuditEvent
        event=db.query(DecisionAuditEvent).filter_by(decision_id=body['decision_id'],event_type='JEV_UNAVAILABLE').one()
        assert event.details=={'provider':'JEV','reason_code':'PROVIDER_UNAVAILABLE'}

def test_openai_requires_both_provider_selection_and_opt_in(api,monkeypatch):
    client,private,_=api
    from app import main
    from app.providers.openai_decisions import OpenAISuggestion
    monkeypatch.setenv('DECISION_PROVIDER','openai')
    calls=[]
    monkeypatch.setattr(main,'suggest_openai_category',lambda code,retries:(calls.append((code,retries)) or
        OpenAISuggestion('TRANSFER',0.9,'gpt-6-luna',30,3)))
    payload={**PAYLOAD,'request_id':'openai-disabled-0001','error_code':'C_STORE_FAILURE'}
    response=client.post('/api/v1/decisions/evaluate',json=payload,headers=bearer(private))
    assert response.status_code==200 and calls==[]
    assert response.json()['provider']=='RULES'

def test_openai_opt_in_is_suggestion_only_and_unknown_codes_never_leave_service(api,monkeypatch):
    client,private,Session=api
    from app import main
    from app.providers.openai_decisions import OpenAISuggestion
    monkeypatch.setenv('DECISION_PROVIDER','openai')
    monkeypatch.setenv('OPENAI_DECISIONS_ENABLED','true')
    monkeypatch.setenv('OPENAI_API_KEY','synthetic-test-key')
    calls=[]
    monkeypatch.setattr(main,'suggest_openai_category',lambda code,retries:(calls.append((code,retries)) or
        OpenAISuggestion('TRANSFER',0.9,'gpt-6-luna',30,3)))
    unknown={**PAYLOAD,'request_id':'openai-unknown-0001'}
    assert client.post('/api/v1/decisions/evaluate',json=unknown,headers=bearer(private)).status_code==200
    assert calls==[]
    payload={**PAYLOAD,'request_id':'openai-allowed-0001','error_code':'C_STORE_FAILURE'}
    body=client.post('/api/v1/decisions/evaluate',json=payload,headers=bearer(private)).json()
    assert calls==[('C_STORE_FAILURE',1)]
    assert body['provider']=='OPENAI_DECISIONS' and body['model_suggestion']=='TRANSFER'
    assert body['status']=='NEEDS_REVIEW' and body['review_required'] and body['execution_allowed'] is False
    with Session() as db:
        events=db.query(DecisionAuditEvent).filter_by(decision_id=body['decision_id']).all()
        assert {event.event_type for event in events}=={'DECISION_CLASSIFIED','PROVIDER_REQUESTED','OPENAI_DECISIONS_SUGGESTION'}

def test_openai_failure_keeps_rule_result_and_records_safe_audit(api,monkeypatch):
    client,private,Session=api
    from app import main
    from app.providers.openai_decisions import OpenAIUnavailable
    monkeypatch.setenv('DECISION_PROVIDER','openai')
    monkeypatch.setenv('OPENAI_DECISIONS_ENABLED','true')
    monkeypatch.setenv('OPENAI_API_KEY','synthetic-test-key')
    monkeypatch.setattr(main,'suggest_openai_category',lambda *_:(_ for _ in ()).throw(OpenAIUnavailable('private detail')))
    payload={**PAYLOAD,'request_id':'openai-failed-0001','error_code':'C_STORE_FAILURE'}
    body=client.post('/api/v1/decisions/evaluate',json=payload,headers=bearer(private)).json()
    assert body['provider']=='RULES' and body['model_suggestion'] is None
    assert body['status']=='NEEDS_REVIEW' and body['execution_allowed'] is False
    with Session() as db:
        event=db.query(DecisionAuditEvent).filter_by(decision_id=body['decision_id'],
            event_type='OPENAI_DECISIONS_UNAVAILABLE').one()
        assert event.details=={'provider':'OPENAI_DECISIONS','reason_code':'PROVIDER_UNAVAILABLE'}

def test_auto_selects_first_enabled_credentialed_provider_and_audits_selection(api,monkeypatch):
    client,private,Session=api
    from app import main
    from app.providers.openai_decisions import OpenAISuggestion
    monkeypatch.setenv('DECISION_PROVIDER','auto')
    monkeypatch.setenv('DECISION_PROVIDER_ORDER','jev,openai')
    monkeypatch.setenv('JEV_ENABLED','true')
    monkeypatch.setenv('JEV_API_KEY','')
    monkeypatch.setenv('OPENAI_DECISIONS_ENABLED','true')
    monkeypatch.setenv('OPENAI_API_KEY','synthetic-test-key')
    calls=[]
    monkeypatch.setattr(main,'suggest_openai_category',lambda code,retries:(calls.append((code,retries)) or
        OpenAISuggestion('TRANSFER',0.9,'gpt-6-luna',30,3)))
    payload={**PAYLOAD,'request_id':'auto-router-0001','error_code':'C_STORE_FAILURE'}
    body=client.post('/api/v1/decisions/evaluate',json=payload,headers=bearer(private)).json()
    assert calls==[('C_STORE_FAILURE',1)]
    assert body['provider']=='OPENAI_DECISIONS' and body['model_suggestion']=='TRANSFER'
    with Session() as db:
        events=db.query(DecisionAuditEvent).filter_by(decision_id=body['decision_id']).all()
        request_event=next(event for event in events if event.event_type=='PROVIDER_REQUESTED')
        assert request_event.details=={'provider':'OPENAI_DECISIONS','policy_mode':'auto'}

def test_auto_rejects_invalid_provider_order_and_remains_rules_only(api,monkeypatch):
    client,private,_=api
    from app import main
    monkeypatch.setenv('DECISION_PROVIDER','auto')
    monkeypatch.setenv('DECISION_PROVIDER_ORDER','jev,unknown')
    monkeypatch.setenv('JEV_ENABLED','true')
    monkeypatch.setenv('JEV_API_KEY','synthetic-test-key')
    calls=[]
    monkeypatch.setattr(main,'suggest_category',lambda *args:calls.append(args))
    payload={**PAYLOAD,'request_id':'auto-invalid-order-0001','error_code':'C_STORE_FAILURE'}
    body=client.post('/api/v1/decisions/evaluate',json=payload,headers=bearer(private)).json()
    assert body['provider']=='RULES' and body['model_suggestion'] is None
    assert calls==[]
