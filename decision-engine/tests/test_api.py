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
