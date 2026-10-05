from datetime import datetime, timedelta
from uuid import uuid4
import json
from types import SimpleNamespace
import pytest


@pytest.fixture
def queue_cases(app_ctx, monkeypatch):
    m=app_ctx
    key='CODEX-UAT-QUEUE-'+uuid4().hex[:8].upper()
    branch=m.Branch(code=key[:20],name=key)
    other=m.Branch(code=(key+'X')[:19]+'X',name=key+' other')
    m.db.session.add_all([branch,other]);m.db.session.flush()
    role=m.Role(code=key,name=key,permissions_json=json.dumps(['technician.worklist']))
    m.db.session.add(role);m.db.session.flush()
    user=m.User(username=key,full_name=key,password_hash='not-a-login-password',role_id=role.id,branch_id=branch.id)
    patient=m.Patient(patient_id=key,name=key)
    m.db.session.add_all([user,patient]);m.db.session.flush()
    cases={}
    for label,status,exam in [('waiting','SCHEDULED','ORDERED'),('progress','IN_PROGRESS','IN_PROGRESS'),
                              ('complete','COMPLETED','EXAM_COMPLETED'),('final','FINAL','EXAM_COMPLETED'),
                              ('returned','COMPLETED','EXAM_COMPLETED'),('other','SCHEDULED','ORDERED')]:
        cases[label]=m.Order(accession=key+'-'+label,patient_id=patient.id,branch_id=other.id if label=='other' else branch.id,
             modality='DX',procedure=key,scheduled=datetime(2037,2,3,12),status=status,exam_status=exam)
    m.db.session.add_all(cases.values());m.db.session.flush()
    event=m.CaseWorkflowEvent(order_id=cases['returned'].id,event_type='RETURNED',owner_role='TECHNICIAN',
        reason_code='MISSING_HISTORY',note='Add history before review',created_by=user.id)
    m.db.session.add(event);m.db.session.commit()
    client=m.app.test_client()
    with client.session_transaction() as session:session['uid']=user.id
    captured={}
    def render(template,**kwargs):captured.clear();captured.update(kwargs);return 'rendered'
    monkeypatch.setattr(m,'render_template',render)
    yield SimpleNamespace(m=m,key=key,user=user,role=role,cases=cases,event=event,client=client,captured=captured)
    m.db.session.rollback()


def get_queue(f,url):
    response=f.client.get(url,base_url='https://localhost')
    assert response.status_code==200
    return {o.id for o in f.captured['orders']}


def test_default_only_not_started_and_branch_scoped(queue_cases):
    f=queue_cases
    ids=get_queue(f,'/technician?date_from=2037-02-03&date_to=2037-02-03')
    assert f.cases['waiting'].id in ids
    assert not ids.intersection({f.cases[k].id for k in ['progress','complete','final','returned','other']})
    assert f.captured['queue_view']=='waiting'


def test_progress_separate_completed_and_returned_hidden(queue_cases):
    f=queue_cases;ids=get_queue(f,'/technician?view=in_progress')
    assert f.cases['progress'].id in ids
    assert not ids.intersection({f.cases[k].id for k in ['waiting','complete','returned','final','other']})


def test_returned_disappears_only_after_later_resolution(queue_cases):
    f=queue_cases
    assert f.cases['returned'].id in get_queue(f,'/technician?view=returned')
    f.m.db.session.add(f.m.CaseWorkflowEvent(order_id=f.cases['returned'].id,event_type='RESOLUTION_RECHECK_FAILED',owner_role='TECHNICIAN'))
    f.m.db.session.commit()
    assert f.cases['returned'].id in get_queue(f,'/technician?view=returned')
    f.m.db.session.add(f.m.CaseWorkflowEvent(order_id=f.cases['returned'].id,event_type='READY_FOR_REREVIEW',owner_role='ASSIGNMENT'))
    f.m.db.session.commit()
    assert f.cases['returned'].id not in get_queue(f,'/technician?view=returned')


def test_search_includes_completed_and_final_but_never_other_branch(queue_cases):
    f=queue_cases;ids=get_queue(f,'/technician?q='+f.key)
    assert {f.cases[k].id for k in ['complete','final','returned','waiting','progress']} <= ids
    assert f.cases['other'].id not in ids
    assert f.captured['queue_search']


def test_missing_branch_fails_closed(queue_cases):
    f=queue_cases;f.user.branch_id=None;f.m.db.session.commit()
    assert not get_queue(f,'/technician?q='+f.key)
    assert f.client.get('/technician/'+str(f.cases['returned'].id),base_url='https://localhost').status_code==403


@pytest.mark.parametrize('kind',['HISTORY','TECHNICAL'])
def test_returned_notes_audited_without_changing_report_or_status(queue_cases,kind):
    f=queue_cases;o=f.cases['returned']
    response=f.client.post(f'/technician/{o.id}/returned-note',data={'note_type':kind,'text':'Clinical test correction'},base_url='https://localhost')
    assert response.status_code==302
    note=f.m.ClinicalNote.query.filter_by(order_id=o.id,note_type=kind).one()
    assert note.text=='Clinical test correction' and note.author_user_id==f.user.id
    assert f.m.AuditLog.query.filter_by(action='RETURNED_CASE_NOTE_ADDED',entity_id=str(o.id)).count()==1
    assert o.exam_status=='EXAM_COMPLETED' and o.report is None
    assert f.m.case_return_is_open(o.id)


def test_image_request_creates_review_record_and_notification_no_pacs_call(queue_cases,monkeypatch):
    f=queue_cases;o=f.cases['returned']
    for method in ('post','delete','put'):
        monkeypatch.setattr(f.m.requests,method,lambda *a,**k:pytest.fail('A request must never mutate PACS'))
    response=f.client.post(f'/technician/{o.id}/image-replacement-request',data={'reason':'Wrong images require supervisor review'},base_url='https://localhost')
    assert response.status_code==302
    request=f.m.CorrectionRequest.query.filter_by(order_id=o.id,request_type='WRONG_IMAGES').one()
    assert request.status=='NEW' and request.branch_id==f.user.branch_id and request.requested_by==f.user.id
    assert f.m.AuditLog.query.filter_by(action='CORRECTION_REQUEST_CREATED',entity_id=str(request.id)).count()==1
    notification=f.m.RISNotification.query.filter_by(order_id=o.id,event_type='IMAGE_REPLACEMENT_REQUESTED').one()
    assert notification.role_code=='CASE_COORDINATOR' and notification.branch_id==f.user.branch_id
    assert f.client.post(f'/technician/{o.id}/image-replacement-request',data={'reason':'Duplicate request'},base_url='https://localhost').status_code==409


@pytest.mark.parametrize('label,code',[('other',403),('waiting',409),('final',409)])
def test_request_not_allowed_outside_return_scope(queue_cases,label,code):
    f=queue_cases
    for action,data in [('image-replacement-request',{'reason':'Wrong test images'}),('returned-note',{'note_type':'HISTORY','text':'Test history'})]:
        assert f.client.post(f'/technician/{f.cases[label].id}/{action}',data=data,base_url='https://localhost').status_code==code


def test_verified_report_blocks_return_notes_and_image_requests(queue_cases):
    f=queue_cases;o=f.cases['returned']
    f.m.db.session.add(f.m.Report(order_id=o.id,status='VERIFIED',verified_at=datetime.utcnow()));f.m.db.session.commit()
    assert f.client.post(f'/technician/{o.id}/returned-note',data={'text':'Clinical correction'},base_url='https://localhost').status_code==409
    assert f.client.post(f'/technician/{o.id}/image-replacement-request',data={'reason':'Wrong images'},base_url='https://localhost').status_code==409


def test_open_image_request_blocks_resubmission_before_any_pacs_access(queue_cases,monkeypatch):
    f=queue_cases;o=f.cases['returned']
    f.user.role=f.m.Role.query.filter_by(code='TECHNICIAN').one();f.m.db.session.commit()
    f.m.db.session.add(f.m.CorrectionRequest(order_id=o.id,branch_id=o.branch_id,request_type='WRONG_IMAGES',status='APPROVED',reason='Test approval pending execution',requested_by=f.user.id));f.m.db.session.commit()
    monkeypatch.setattr(f.m,'pacs_lookup_order',lambda *a,**k:pytest.fail('Pending request must block before PACS lookup'))
    response=f.client.post(f'/returned-cases/{f.event.id}/resolve',data={'note':'Ready'},base_url='https://localhost')
    assert response.status_code==302 and f.m.case_return_is_open(o.id)


def test_coordinator_return_notifies_technician_without_report_edit_permission(queue_cases):
    f=queue_cases;o=f.cases['complete']
    f.user.role=f.m.Role.query.filter_by(code='CASE_COORDINATOR').one();f.m.db.session.add(f.m.CaseReturnReason(code=f.key,label='Missing history',route_to='TECHNICIAN',active=True));f.m.db.session.commit()
    response=f.client.post(f'/reports/{o.id}/return-case',data={'reason_code':f.key,'note':'Please add clinical history'},base_url='https://localhost')
    assert response.status_code==302
    state=f.m.case_return_snapshot(o.id)
    assert state['open'] and state['owner']=='TECHNICIAN'
    notice=f.m.RISNotification.query.filter_by(order_id=o.id,event_type='RETURNED_TO_TECH').one()
    assert notice.role_code=='TECHNICIAN' and notice.branch_id==o.branch_id
    assert f.m.AuditLog.query.filter_by(action='CASE_RETURNED_FOR_ACTION',entity_id=str(o.id)).count()==1


def test_technician_cannot_return_as_doctor(queue_cases):
    f=queue_cases
    assert f.client.get(f'/reports/{f.cases["complete"].id}/return-case',base_url='https://localhost').status_code==403


def test_latest_return_owner_overrides_old_technician_return(queue_cases):
    f=queue_cases
    f.m.db.session.add(f.m.CaseWorkflowEvent(order_id=f.cases['returned'].id,event_type='RETURNED',owner_role='SUPERVISOR',created_at=f.event.created_at+timedelta(seconds=1)))
    f.m.db.session.commit()
    assert f.cases['returned'].id not in get_queue(f,'/technician?view=returned')


def test_unconverted_booking_does_not_enter_start_queue(queue_cases):
    f=queue_cases;f.cases['waiting'].status='REGISTERED';f.m.db.session.commit()
    assert f.cases['waiting'].id not in get_queue(f,'/technician')


@pytest.mark.parametrize('kind',[None,'TECHNICAL','HISTORY'])
def test_resubmission_requires_history_not_just_a_technical_note(queue_cases,monkeypatch,kind):
    f=queue_cases;o=f.cases['returned']
    f.user.role=f.m.Role.query.filter_by(code='TECHNICIAN').one();o.pacs_status='IMAGES_COMPLETE'
    if kind:f.m.db.session.add(f.m.ClinicalNote(order_id=o.id,author_user_id=f.user.id,note_type=kind,text='Clinical test history'))
    f.m.db.session.commit()
    monkeypatch.setattr(f.m,'pacs_lookup_order',lambda o:None)
    monkeypatch.setattr(f.m,'technician_completion_evidence',lambda o:({'allowed':True},None))
    monkeypatch.setattr(f.m,'evaluate_case_readiness',lambda o,**k:SimpleNamespace(status='READY'))
    monkeypatch.setattr(f.m,'assignment_readiness_decision',lambda *a,**k:{'allowed':True})
    monkeypatch.setattr(f.m,'coordinate_post_exam_assignment',lambda *a,**k:(None,'READY_FOR_ASSIGNMENT'))
    assert f.client.post(f'/returned-cases/{f.event.id}/resolve',data={'note':'Corrected history'},base_url='https://localhost').status_code==302
    assert f.m.case_return_is_open(o.id)==(kind!='HISTORY')


def test_resubmission_cannot_bypass_strict_image_policy_with_warning_strategy(queue_cases,monkeypatch):
    f=queue_cases;o=f.cases['returned']
    f.user.role=f.m.Role.query.filter_by(code='TECHNICIAN').one();o.pacs_status='IMAGES_COMPLETE'
    f.m.db.session.add(f.m.ClinicalNote(order_id=o.id,author_user_id=f.user.id,note_type='HISTORY',text='Clinical test history'));f.m.db.session.commit()
    monkeypatch.setattr(f.m,'pacs_lookup_order',lambda o:None)
    monkeypatch.setattr(f.m,'technician_completion_evidence',lambda o:({'allowed':False},None))
    monkeypatch.setattr(f.m,'evaluate_case_readiness',lambda o,**k:SimpleNamespace(status='READY'))
    monkeypatch.setattr(f.m,'assignment_readiness_decision',lambda *a,**k:{'allowed':True})
    assert f.client.post(f'/returned-cases/{f.event.id}/resolve',base_url='https://localhost').status_code==302
    assert f.m.case_return_is_open(o.id)
