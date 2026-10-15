from datetime import datetime,timedelta
from types import SimpleNamespace
from uuid import uuid4
import pytest
import coordinator_bulk_assignment as bulk


@pytest.fixture
def bulk_cases(app_ctx,monkeypatch):
    import assignment_distribution as distribution
    m=app_ctx;key='BUAT'+uuid4().hex[:10].upper()
    coord=m.Role.query.filter_by(code='CASE_COORDINATOR').one();old=coord.permissions_json
    coord.permissions_json='["reports.coordinate"]'
    branch=m.Branch(code=key,name=key);other=m.Branch(code=key+'X',name=key+'X')
    m.db.session.add_all([branch,other]);m.db.session.flush()
    actor=m.User(username=key,full_name='CODEX UAT COORDINATOR',password_hash='not-a-login-password',role_id=coord.id,branch_id=branch.id)
    doctor=m.User(username=key+'DOC',full_name='CODEX UAT DOCTOR',password_hash='not-a-login-password',role_id=m.Role.query.filter_by(code='RADIOLOGIST').one().id,branch_id=branch.id)
    patient=m.Patient(patient_id=key,name='CODEX UAT BULK TEST')
    m.db.session.add_all([actor,doctor,patient]);m.db.session.flush()
    profile=m.DoctorAssignmentProfile(user_id=doctor.id,modalities='DX,CT',branches=str(branch.id),max_active_cases=20,available=True,auto_assign=False)
    m.db.session.add(profile)
    orders=[]
    for i in range(3):
        o=m.Order(accession=key+str(i),patient_id=patient.id,branch_id=branch.id,modality='DX' if i!=1 else 'CT',procedure=key,
            scheduled=datetime.utcnow(),status='COMPLETED',exam_status='EXAM_COMPLETED',pacs_status='IMAGES_COMPLETE',pacs_study_id=key+str(i),pacs_image_count=3)
        m.db.session.add(o);m.db.session.flush();orders.append(o)
        m.db.session.add(m.CaseReadiness(order_id=o.id,status='READY',checked_at=datetime.utcnow(),facts_sha256=key))
    m.db.session.commit()
    monkeypatch.setattr(m,'pacs_demographic_gate',lambda o:(True,''))
    monkeypatch.setattr(m,'assignment_readiness_decision',lambda *a,**k:{'allowed':True})
    monkeypatch.setattr(m,'quality_rule_for',lambda o:None)
    monkeypatch.setattr(distribution,'policy_snapshot',lambda:{'max_active_cases':20,'special_rules':[],'version_no':0})
    client=m.app.test_client()
    with client.session_transaction() as s:s['uid']=actor.id;s['coordinator_assignment_csrf']='CODEX-UAT-CSRF'
    captured={}
    def render(template,**kwargs):captured.clear();captured.update(kwargs);return 'rendered'
    monkeypatch.setattr(m,'render_template',render)
    yield SimpleNamespace(m=m,key=key,actor=actor,doctor=doctor,orders=orders,profile=profile,branch=branch,other=other,client=client,captured=captured)
    m.db.session.rollback();coord.permissions_json=old;m.db.session.commit()


def preview(f,ids=None):
    return f.client.post('/coordinator/manual-assignment',base_url='https://localhost',
        data={'assignment_csrf':'CODEX-UAT-CSRF','action':'preview','doctor_id':f.doctor.id,'order_ids':[str(o.id) for o in (ids or f.orders)],'note':'CODEX UAT manual assignment'})


def confirm(f,token):
    return f.client.post('/coordinator/manual-assignment',base_url='https://localhost',data={'assignment_csrf':'CODEX-UAT-CSRF','action':'confirm','preview_token':token,'acknowledge':'1'})


def test_preview_is_read_only_and_confirm_assigns_all_with_audit(bulk_cases):
    f=bulk_cases
    assert preview(f).status_code==200
    token=f.captured['preview_token'];assert token
    assert len(f.captured['preview']['accepted'])==3
    assert all(o.assigned_doctor_id is None for o in f.orders)
    assert not f.m.CaseAssignment.query.filter(f.m.CaseAssignment.order_id.in_([o.id for o in f.orders])).first()
    assert confirm(f,token).status_code==302
    assert all(o.assigned_doctor_id==f.doctor.id for o in f.orders)
    assignments=f.m.CaseAssignment.query.filter(f.m.CaseAssignment.order_id.in_([o.id for o in f.orders]),f.m.CaseAssignment.active.is_(True)).all()
    assert len(assignments)==3 and all(a.assignment_type=='MANUAL' and a.start_deadline_at is None for a in assignments)
    claims=bulk.serializer(f.m).loads(token)
    assert f.m.AuditLog.query.filter_by(action='BULK_MANUAL_ASSIGNMENT',entity_id=claims['batch']).count()==1
    assert confirm(f,token).status_code==409


def test_queue_search_uses_accession_injected_query_adapter(bulk_cases):
    f=bulk_cases
    response=f.client.get('/coordinator/manual-assignment?q='+f.orders[1].accession,
        base_url='https://localhost')
    assert response.status_code==200
    assert [order.id for order in f.captured['orders']]==[f.orders[1].id]


def test_confirm_rejects_changed_case_without_any_partial_assignment(bulk_cases):
    f=bulk_cases;preview(f);token=f.captured['preview_token']
    f.orders[1].pacs_image_count=4;f.m.db.session.commit()
    assert confirm(f,token).status_code==409
    assert all(o.assigned_doctor_id is None for o in f.orders)


def test_transaction_rolls_back_all_cases_when_writer_fails(bulk_cases,monkeypatch):
    f=bulk_cases;preview(f);token=f.captured['preview_token'];original=f.m.manual_assign_order
    calls=[]
    def fail_second(*a,**k):
        calls.append(1)
        if len(calls)==2:raise RuntimeError('Synthetic transaction failure')
        return original(*a,**k)
    monkeypatch.setattr(f.m,'manual_assign_order',fail_second)
    assert confirm(f,token).status_code==409
    assert all(o.assigned_doctor_id is None for o in f.orders)
    assert not f.m.CaseAssignment.query.filter(f.m.CaseAssignment.order_id.in_([o.id for o in f.orders])).first()


def test_linked_visit_expands_once_and_moves_as_a_whole(bulk_cases):
    f=bulk_cases
    visit=f.m.AssignmentVisit(id=str(uuid4()),patient_id=f.orders[0].patient_id,branch_id=f.branch.id,visit_date=datetime.utcnow().date(),registration_open=False)
    f.m.db.session.add(visit);f.m.db.session.flush()
    for o in f.orders[:2]:o.assignment_visit_id=visit.id
    f.m.db.session.commit()
    assert preview(f,f.orders[:2]).status_code==200
    assert len(f.captured['preview']['accepted'])==1 and len(f.captured['preview']['accepted'][0])==2
    assert confirm(f,f.captured['preview_token']).status_code==302
    assert all(o.assigned_doctor_id==f.doctor.id for o in f.orders[:2]) and f.orders[2].assigned_doctor_id is None


def test_ineligible_member_blocks_entire_visit(bulk_cases):
    f=bulk_cases;f.profile.modalities='DX'
    visit=f.m.AssignmentVisit(id=str(uuid4()),patient_id=f.orders[0].patient_id,branch_id=f.branch.id,visit_date=datetime.utcnow().date())
    f.m.db.session.add(visit);f.m.db.session.flush()
    for o in f.orders[:2]:o.assignment_visit_id=visit.id
    f.m.db.session.commit();preview(f,[f.orders[0]])
    assert not f.captured['preview_token'] and f.captured['preview']['blocked'][0]['reason']=='QUALIFICATION'


def test_capacity_reserves_whole_visit_and_no_partial_split(bulk_cases):
    f=bulk_cases;f.profile.max_active_cases=1;f.m.db.session.commit();preview(f)
    assert len(f.captured['preview']['accepted'])==1 and len(f.captured['preview']['blocked'])==2
    assert confirm(f,f.captured['preview_token']).status_code==302
    assert sum(o.assigned_doctor_id==f.doctor.id for o in f.orders)==1


@pytest.mark.parametrize('problem,expected',[('final','LOCKED'),('verified','LOCKED'),('reading','READING'),('draft','READING'),('returned','RETURNED'),('correction','CORRECTION'),('images','IMAGES'),('stale','READINESS')])
def test_blocked_case_is_excluded_with_reason(bulk_cases,problem,expected):
    f=bulk_cases;o=f.orders[0]
    if problem=='final':o.status='FINAL'
    if problem=='verified':f.m.db.session.add(f.m.Report(order_id=o.id,status='VERIFIED'))
    if problem=='draft':f.m.db.session.add(f.m.Report(order_id=o.id,status='DRAFT',findings='Started report'))
    if problem=='reading':f.m.db.session.add(f.m.CaseAssignment(order_id=o.id,doctor_user_id=f.doctor.id,active=True,reading_started_at=datetime.utcnow()))
    if problem=='returned':f.m.db.session.add(f.m.CaseWorkflowEvent(order_id=o.id,event_type='RETURNED',owner_role='TECHNICIAN'))
    if problem=='correction':f.m.db.session.add(f.m.CorrectionRequest(order_id=o.id,branch_id=o.branch_id,request_type='WRONG_IMAGES',status='NEW',reason='Test review',requested_by=f.actor.id))
    if problem=='images':o.pacs_image_count=0
    if problem=='stale':f.m.CaseReadiness.query.filter_by(order_id=o.id).one().checked_at=datetime.utcnow()-timedelta(minutes=6)
    f.m.db.session.commit();assert preview(f,[o]).status_code==200
    assert not f.captured['preview_token'] and f.captured['preview']['blocked'][0]['reason']==expected


def test_cross_branch_selection_is_denied(bulk_cases):
    f=bulk_cases;f.orders[0].branch_id=f.other.id;f.m.db.session.commit()
    assert preview(f,[f.orders[0]]).status_code==403


def test_foreign_branch_doctor_is_hidden_and_cannot_be_selected(bulk_cases):
    f=bulk_cases
    foreign=f.m.User(
        username=f.key+'FOREIGN', full_name='CODEX UAT FOREIGN DOCTOR',
        password_hash='not-a-login-password', role_id=f.doctor.role_id,
        branch_id=f.other.id,
    )
    f.m.db.session.add(foreign);f.m.db.session.flush()
    f.m.db.session.add(f.m.DoctorAssignmentProfile(
        user_id=foreign.id, modalities='DX,CT', branches=str(f.other.id),
        max_active_cases=20, available=True, auto_assign=False,
    ))
    f.m.db.session.commit()

    assert f.client.get('/coordinator/manual-assignment',base_url='https://localhost').status_code==200
    assert [doctor.id for doctor in f.captured['doctors']]==[f.doctor.id]
    response=f.client.post('/coordinator/manual-assignment',base_url='https://localhost',data={
        'assignment_csrf':'CODEX-UAT-CSRF', 'action':'preview',
        'doctor_id':foreign.id, 'order_ids':[str(f.orders[0].id)],
        'note':'CODEX UAT foreign doctor must be denied',
    })
    assert response.status_code==409
    assert not f.captured.get('preview_token')
    assert all(order.assigned_doctor_id is None for order in f.orders)


def test_token_is_bound_to_actor_and_cannot_be_tampered(bulk_cases):
    f=bulk_cases;preview(f);token=f.captured['preview_token']
    assert confirm(f,token+'tampered').status_code==409
    claims=bulk.serializer(f.m).loads(token);claims['actor']=f.actor.id+1000
    assert confirm(f,bulk.serializer(f.m).dumps(claims)).status_code==409
    assert all(o.assigned_doctor_id is None for o in f.orders)


def test_technician_denied_even_if_role_has_generic_assignment_permission(bulk_cases):
    f=bulk_cases;role=f.m.Role.query.filter_by(code='TECHNICIAN').one();old=role.permissions_json
    try:
        role.permissions_json='["assignment.manage"]';f.actor.role=role;f.m.db.session.commit()
        assert f.client.get('/coordinator/manual-assignment',base_url='https://localhost').status_code==403
    finally:
        role.permissions_json=old;f.m.db.session.commit()


def test_missing_branch_denied_for_coordinator(bulk_cases):
    f=bulk_cases;f.actor.branch_id=None;f.m.db.session.commit()
    assert f.client.get('/coordinator/manual-assignment',base_url='https://localhost').status_code==403


def test_pending_offers_reserve_doctor_capacity(bulk_cases):
    f=bulk_cases;f.profile.max_active_cases=2
    f.m.db.session.add(f.m.AssignmentOffer(order_id=f.orders[2].id,doctor_user_id=f.doctor.id,status='PENDING',expires_at=datetime.utcnow()+timedelta(minutes=5)))
    f.m.db.session.commit();preview(f,f.orders[:2])
    assert len(f.captured['preview']['accepted'])==1 and f.captured['preview']['blocked'][0]['reason']=='CAPACITY'


def test_expired_preview_is_rejected(bulk_cases,monkeypatch):
    from itsdangerous.timed import TimestampSigner
    f=bulk_cases;preview(f);token=f.captured['preview_token'];original=TimestampSigner.get_timestamp
    monkeypatch.setattr(TimestampSigner,'get_timestamp',lambda self:original(self)+601)
    assert confirm(f,token).status_code==409
    assert all(o.assigned_doctor_id is None for o in f.orders)


def test_reassign_unstarted_case_replaces_active_assignment_safely(bulk_cases):
    f=bulk_cases;o=f.orders[0]
    previous=f.m.User(username=f.key+'OLD',full_name='CODEX UAT PREVIOUS DOCTOR',password_hash='not-a-login-password',role_id=f.doctor.role_id,branch_id=f.branch.id)
    f.m.db.session.add(previous);f.m.db.session.flush()
    old=f.m.CaseAssignment(order_id=o.id,doctor_user_id=previous.id,assignment_type='AUTO',active=True)
    f.m.db.session.add(old);o.assigned_doctor_id=previous.id;f.m.db.session.commit()
    preview(f,[o]);assert confirm(f,f.captured['preview_token']).status_code==302
    assert not old.active and old.unassigned_at is not None
    active=f.m.CaseAssignment.query.filter_by(order_id=o.id,active=True).one()
    assert active.doctor_user_id==f.doctor.id and active.assignment_type=='MANUAL'


def test_reading_started_after_preview_invalidates_the_batch(bulk_cases):
    f=bulk_cases;o=f.orders[0]
    f.m.db.session.add(f.m.CaseAssignment(order_id=o.id,doctor_user_id=f.doctor.id,active=True,assignment_type='AUTO'))
    o.assigned_doctor_id=f.doctor.id;f.m.db.session.commit()
    preview(f);token=f.captured['preview_token'];assert token
    f.m.CaseAssignment.query.filter_by(order_id=o.id,active=True).one().reading_started_at=datetime.utcnow();f.m.db.session.commit()
    assert confirm(f,token).status_code==409
    assert f.orders[1].assigned_doctor_id is None and f.orders[2].assigned_doctor_id is None


def test_reassignment_notifies_previous_and_new_doctor_once(bulk_cases):
    f=bulk_cases;old=f.m.User(username=f.key+'OLD',full_name='CODEX UAT previous doctor',password_hash='disabled',role_id=f.doctor.role_id,branch_id=f.branch.id)
    f.m.db.session.add(old);f.m.db.session.flush()
    o=f.orders[0];o.assigned_doctor_id=old.id
    f.m.db.session.add(f.m.CaseAssignment(order_id=o.id,doctor_user_id=old.id,active=True))
    f.m.db.session.commit();preview(f,[o]);token=f.captured['preview_token']
    assert confirm(f,token).status_code==302
    notices=f.m.RISNotification.query.filter_by(order_id=o.id).filter(f.m.RISNotification.event_type.in_(['CASE_REASSIGNED_AWAY','CASE_MANUALLY_ASSIGNED'])).all()
    assert {(n.user_id,n.event_type) for n in notices}=={(old.id,'CASE_REASSIGNED_AWAY'),(f.doctor.id,'CASE_MANUALLY_ASSIGNED')}
    assert all('CODEX UAT manual assignment' in n.body and n.branch_id==o.branch_id for n in notices)
    assert confirm(f,token).status_code==409
    assert f.m.RISNotification.query.filter_by(order_id=o.id).count()==2


def test_same_doctor_retry_does_not_send_transfer_notice(bulk_cases):
    f=bulk_cases;o=f.orders[0];o.assigned_doctor_id=f.doctor.id
    f.m.db.session.add(f.m.CaseAssignment(order_id=o.id,doctor_user_id=f.doctor.id,active=True));f.m.db.session.commit()
    preview(f,[o]);assert confirm(f,f.captured['preview_token']).status_code==302
    assert f.m.RISNotification.query.filter_by(order_id=o.id).count()==0


def editor_lease(f,expires):
    o=f.orders[0];r=f.m.Report(order_id=o.id,status='UNREPORTED');f.m.db.session.add(r);f.m.db.session.flush()
    now=datetime.utcnow()
    f.m.db.session.add(f.m.ReportEditLease(order_id=o.id,report_id=r.id,user_id=f.doctor.id,editor_type='ONLYOFFICE',lease_token_hash='CODEX-UAT',acquired_at=now,renewed_at=now,expires_at=expires))
    f.m.db.session.commit()


def test_active_editor_without_saved_text_blocks_reassignment(bulk_cases):
    f=bulk_cases;editor_lease(f,datetime.utcnow()+timedelta(minutes=2))
    preview(f,[f.orders[0]])
    assert not f.captured['preview_token'] and f.captured['preview']['blocked'][0]['reason']=='READING'


def test_editor_opened_after_preview_denies_entire_batch(bulk_cases):
    f=bulk_cases;preview(f);token=f.captured['preview_token']
    editor_lease(f,datetime.utcnow()+timedelta(minutes=2))
    assert confirm(f,token).status_code==409
    assert all(o.assigned_doctor_id is None for o in f.orders)
    assert f.m.RISNotification.query.filter(f.m.RISNotification.order_id.in_([o.id for o in f.orders])).count()==0


def test_expired_empty_editor_lease_does_not_block_assignment(bulk_cases):
    f=bulk_cases;editor_lease(f,datetime.utcnow()-timedelta(minutes=1))
    preview(f,[f.orders[0]]);assert confirm(f,f.captured['preview_token']).status_code==302


def test_assignment_requires_session_csrf(bulk_cases):
    f=bulk_cases
    assert f.client.post('/coordinator/manual-assignment',base_url='https://localhost',data={'action':'preview','doctor_id':f.doctor.id,'order_ids':[str(f.orders[0].id)],'note':'CODEX UAT rejected CSRF'}).status_code==403
    assert all(o.assigned_doctor_id is None for o in f.orders)
