import json
import pytest
import app as m
import patient_correction_policy as policy
from test_assignment_distribution import doctor,order

@pytest.fixture(autouse=True)
def isolated(app_ctx,monkeypatch):
    monkeypatch.setattr(m.db.session,'commit',m.db.session.flush)
    yield
    m.db.session.rollback();m.db.session.remove()

def setup(monkeypatch):
    b=m.Branch(code='UAT-CORRECT',name='CODEX UAT Corrections',active=True)
    m.db.session.add(b);m.db.session.flush()
    u=doctor('CODEX-UAT-REQUESTER','RECEPTION');u.branch_id=b.id;u.role.permissions_json=json.dumps(['correction.request'])
    reviewer=doctor('CODEX-UAT-REVIEWER','CASE_COORDINATOR');reviewer.role.permissions_json=json.dumps(['correction.review'])
    o=order('CODEX-UAT-CORRECT');o.branch_id=b.id;o.patient.dob='19900101';o.patient.sex='M'
    m.db.session.flush();monkeypatch.setattr(m,'current_user',lambda:u)
    c=m.app.test_client()
    with c.session_transaction() as s:s['uid']=u.id
    return c,u,reviewer,o

def submit(c,o,field='name',value='CODEX UAT Corrected'):
    return c.post('/correction-center/orders/'+str(o.id)+'/demographics',data={'field_name':field,'proposed_value':value,'reason':'CODEX UAT correction reason','snapshot_hash':policy.snapshot(o.patient,runtime=m)})

def test_structured_request_stores_values_and_impact_without_patient_change(monkeypatch):
    c,u,reviewer,o=setup(monkeypatch);original=o.patient.name
    assert c.get('/correction-center/orders/'+str(o.id)+'/demographics').status_code==200
    assert submit(c,o).status_code==302
    detail=m.PatientDemographicsCorrection.query.one()
    assert detail.old_value==original and detail.proposed_value=='CODEX UAT Corrected'
    assert json.loads(detail.impact_json)['identity_change'] and o.patient.name==original
    assert c.get('/correction-center/requests/'+str(detail.correction_request_id)+'/demographics').status_code==200

@pytest.mark.parametrize('field,value',[('name','Two Names'),('dob','2039-02-31'),('dob','2999-01-01'),('sex','X'),('email','invalid'),('patient_id','CHANGED'),('address','x'*256)])
def test_invalid_or_system_fields_rejected(monkeypatch,field,value):
    setup(monkeypatch)
    with m.app.test_request_context('/'):
        with pytest.raises(ValueError):policy.normalize(field,value,runtime=m)

def test_registration_required_rule_applies_to_correction(monkeypatch):
    c,u,reviewer,o=setup(monkeypatch)
    rule=m.FieldRule(field_key='patient.phone',label_en='Phone',required=True,visible=True)
    m.db.session.add(rule);m.db.session.flush()
    with m.app.test_request_context('/'):
        with pytest.raises(ValueError):policy.normalize('phone','',runtime=m)

def test_stale_preview_blocks_request(monkeypatch):
    c,u,reviewer,o=setup(monkeypatch)
    before=policy.snapshot(o.patient,runtime=m);o.patient.phone='01000000000';m.db.session.flush()
    with m.app.test_request_context('/'):
        with pytest.raises(ValueError):policy.submit(o,'name','CODEX UAT Corrected','Valid reason',before,runtime=m)
    assert m.CorrectionRequest.query.filter_by(order_id=o.id).count()==0

def test_requester_cannot_approve_own_request(monkeypatch):
    c,u,reviewer,o=setup(monkeypatch);u.role.permissions_json=json.dumps(['correction.request','correction.review'])
    submit(c,o);row=m.CorrectionRequest.query.filter_by(order_id=o.id).one()
    assert c.post('/correction-center/requests/'+str(row.id)+'/action',data={'action':'APPROVE','note':'Reviewed synthetic change'}).status_code==409
    assert row.status=='NEW'

def test_second_reviewer_approves_without_mutating_final_report_or_patient(monkeypatch):
    c,u,reviewer,o=setup(monkeypatch)
    report=m.Report(order_id=o.id,status='FINAL',findings='CODEX UAT immutable final')
    m.db.session.add(report);m.db.session.flush()
    original=o.patient.name;submit(c,o);row=m.CorrectionRequest.query.filter_by(order_id=o.id).one()
    monkeypatch.setattr(m,'current_user',lambda:reviewer)
    assert c.post('/correction-center/requests/'+str(row.id)+'/action',data={'action':'APPROVE','note':'Reviewed synthetic change'}).status_code==302
    assert row.status=='APPROVED' and o.patient.name==original and report.findings=='CODEX UAT immutable final'

def test_patient_change_after_submission_blocks_approval(monkeypatch):
    c,u,reviewer,o=setup(monkeypatch);submit(c,o);row=m.CorrectionRequest.query.filter_by(order_id=o.id).one()
    o.patient.dob='19910101';m.db.session.flush();monkeypatch.setattr(m,'current_user',lambda:reviewer)
    assert c.post('/correction-center/requests/'+str(row.id)+'/action',data={'action':'APPROVE','note':'Reviewed synthetic change'}).status_code==409
    assert row.status=='NEW'

def test_cross_branch_request_and_other_user_view_denied(monkeypatch):
    c,u,reviewer,o=setup(monkeypatch);submit(c,o);row=m.CorrectionRequest.query.filter_by(order_id=o.id).one()
    outsider=doctor('CODEX-UAT-OTHER-REQUESTER','TECHNICIAN');outsider.branch_id=u.branch_id;outsider.role.permissions_json=json.dumps(['correction.request'])
    monkeypatch.setattr(m,'current_user',lambda:outsider)
    assert c.get('/correction-center/requests/'+str(row.id)+'/demographics').status_code==403
    outsider.branch_id=None
    assert c.get('/correction-center/orders/'+str(o.id)+'/demographics').status_code==403

def test_legacy_unstructured_request_cannot_be_approved(monkeypatch):
    c,u,reviewer,o=setup(monkeypatch)
    row=m.CorrectionRequest(order_id=o.id,branch_id=o.branch_id,request_type='WRONG_DEMOGRAPHICS',reason='Legacy synthetic request',requested_by=u.id,status='NEW')
    m.db.session.add(row);m.db.session.flush();monkeypatch.setattr(m,'current_user',lambda:reviewer)
    assert c.post('/correction-center/requests/'+str(row.id)+'/action',data={'action':'APPROVE','note':'Reviewed synthetic change'}).status_code==409

def test_duplicate_open_request_rejected(monkeypatch):
    c,u,reviewer,o=setup(monkeypatch);submit(c,o)
    with m.app.test_request_context('/'):
        with pytest.raises(ValueError):policy.submit(o,'sex','F','Valid reason',policy.snapshot(o.patient,runtime=m),runtime=m)
    assert m.CorrectionRequest.query.filter_by(order_id=o.id).count()==1
