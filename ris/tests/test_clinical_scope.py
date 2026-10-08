import json
from datetime import datetime
import pytest
import app as m
import clinical_scope as s
from sqlalchemy import select, func
from sqlalchemy.orm import aliased


@pytest.fixture(autouse=True)
def isolated(app_ctx, monkeypatch):
    monkeypatch.setattr(m.db.session, 'commit', m.db.session.flush)
    yield
    m.db.session.rollback()
    m.db.session.remove()


@pytest.fixture
def setup_scope(monkeypatch):
    branch = m.Branch(code='CSV-UAT', name='Synthetic branch')
    m.db.session.add(branch)
    m.db.session.flush()
    devices = [m.Device(branch_id=branch.id, name='Synthetic CT %s'%i, modality=mod, ae_title='UAT_%s'%i, room=room)
               for i,mod,room in [(1,'CT','Room 1'),(2,'MR','Room 2'),(3,'CT','Room 3')]]
    m.db.session.add_all(devices)
    role=m.Role.query.filter_by(code='TECHNICIAN').one()
    role.permissions_json=json.dumps(['technician.worklist','orders.view','reports.view','attachments.view','attachments.upload','nursing.worklist','consumables.use'])
    user=m.User(username='SCOPE-UAT',full_name='Scoped Synthetic Technician',password_hash='not-a-secret',role_id=role.id,branch_id=branch.id,active=True)
    m.db.session.add(user)
    patient=m.Patient(patient_id='SCOPE-UAT-PATIENT',name='Synthetic Scope Patient')
    m.db.session.add(patient)
    m.db.session.flush()
    orders=[m.Order(patient_id=patient.id,branch_id=branch.id,device_id=d.id,modality=d.modality,procedure='Synthetic study',
                    accession='SCOPE-UAT-%s'%i,status='SCHEDULED',exam_status='ORDERED',scheduled=datetime.utcnow(),assigned_doctor_id=user.id)
            for i,d in enumerate(devices)]
    m.db.session.add_all(orders)
    m.db.session.flush()
    monkeypatch.setattr(m,'current_user',lambda:user)
    c=m.app.test_client()
    with c.session_transaction() as sess:sess['uid']=user.id
    return c,user,devices,orders,patient


def restrict(user, **kw):
    raw=dict(scope_enabled='true',modalities='CT',device_keys='',room_keys='')
    raw.update(kw)
    scope=s.parse(m,raw,user.role)
    s.save(m,user,scope)
    m.db.session.flush()
    return scope


def test_sql_filtered_worklists_counts_aliases_and_direct_urls(setup_scope):
    c,user,devices,orders,p=setup_scope
    restrict(user,room_keys='CSV-UAT/Room 1')
    response=c.get('/technician')
    assert response.status_code==200
    assert orders[0].accession.encode() in response.data
    assert orders[1].accession.encode() not in response.data and orders[2].accession.encode() not in response.data
    assert c.get('/nursing').status_code==200
    for order in orders[1:]:
        for path in ['/orders/%s','/technician/%s','/nursing/%s','/orders/%s/study-thumbnail','/doctor/cases/%s/open','/api/reporting/cases/'+order.accession]:
            assert c.get(path%order.id if '%s' in path else path).status_code==403
        assert c.post('/technician/%s/note'%order.id,data={'text':'Forbidden mutation'}).status_code==403
        assert c.post('/nursing/%s'%order.id,data={}).status_code==403
    assert m.ClinicalNote.query.filter_by(text='Forbidden mutation').count()==0
    with m.app.test_request_context('/technician'):
        for guard in m.app.before_request_funcs[None]:guard()
        assert m.Order.query.count()==1
        alias=aliased(m.Order)
        assert m.db.session.execute(select(func.count(alias.id))).scalar()==1
        assert m.db.session.get(m.Order,orders[1].id) is not None  # identity map may already have it
        assert not m.doctor_case_access_allowed(user,orders[1])


def test_related_attachment_report_and_patient_queries_scoped(setup_scope):
    c,user,devices,orders,p=setup_scope
    restrict(user)
    for o in orders:
        m.db.session.add(m.Attachment(order_id=o.id,patient_id=p.id,original_name='synthetic.txt',stored_path='/nonexistent',category='OTHER'))
        m.db.session.add(m.Report(order_id=o.id,status='DRAFT'))
    m.db.session.flush()
    bad=m.Attachment.query.filter_by(order_id=orders[1].id).one()
    assert c.get('/attachments/%s'%bad.id).status_code==403
    assert c.post('/attachments/upload',data={'order_id':orders[1].id}).status_code==403
    assert c.post('/attachments/upload',data={'patient_id':p.id}).status_code==403
    with m.app.test_request_context('/technician'):
        for guard in m.app.before_request_funcs[None]:guard()
        assert m.Report.query.count()==2 and m.Attachment.query.count()==2
        assert m.Patient.query.one().id == p.id
        assert m.Order.query.filter_by(patient_id=p.id).count()==2


def test_modality_room_device_intersection_and_no_device_denied(setup_scope):
    c,user,devices,orders,p=setup_scope
    restrict(user,modalities='CT|MR',device_keys='CSV-UAT/UAT_1|CSV-UAT/UAT_2',room_keys='CSV-UAT/Room 1')
    assert s.allowed(m,user,orders[0])
    assert not s.allowed(m,user,orders[1]) and not s.allowed(m,user,orders[2])
    orders[0].device_id=None
    m.db.session.flush()
    assert not s.allowed(m,user,orders[0])
    assert c.get('/orders/%s'%orders[0].id).status_code==403


def test_scope_save_preserves_prefs_immediate_revocation_and_assignment(setup_scope):
    c,user,devices,orders,p=setup_scope
    user.role=m.Role.query.filter_by(code='RADIOLOGIST').one()
    profile=m.get_user_profile(user)
    profile.settings_json=json.dumps({'image_viewer':'WEASIS','contacts':{'email':'synthetic@example.test'}})
    restrict(user)
    assert s.allowed(m,user,orders[0]) and not s.allowed(m,user,orders[1])
    from assignment_distribution import validate_special_doctor
    from case_assignment_service import CaseAssignmentServiceError
    with pytest.raises(CaseAssignmentServiceError,match='DOCTOR_CLINICAL_SCOPE_DENIED'):
        validate_special_doctor(orders[1],user)
    restrict(user,modalities='MR')
    assert not s.allowed(m,user,orders[0]) and s.allowed(m,user,orders[1])
    assert m.user_profile_settings(profile)['image_viewer']=='WEASIS'
    s.save(m,user,None)
    assert s.allowed(m,user,orders[0])


@pytest.mark.parametrize('change',[dict(modalities='UNKNOWN'),dict(device_keys='BAD'),dict(room_keys='BAD'),dict(modalities=''),dict(scope_enabled='wat')])
def test_invalid_scope_rejected(setup_scope,change):
    c,user,devices,orders,p=setup_scope
    with pytest.raises(ValueError):restrict(user,**change)


def test_corrupt_scope_fail_closed_and_no_admin_bypass(setup_scope):
    c,user,devices,orders,p=setup_scope
    profile=m.get_user_profile(user)
    profile.settings_json=json.dumps({'clinical_scope':{'enabled':True}})
    assert not s.allowed(m,user,orders[0])
    assert c.get('/technician').status_code==200
    assert orders[0].accession.encode() not in c.get('/technician').data
    user.role.permissions_json='["*"]'
    assert c.get('/admin/users').status_code==403
    assert c.get('/pacs').status_code==403


def test_csv_scope_create_and_export_roundtrip(setup_scope):
    from test_user_csv_transfer import row,preview,apply,token
    c,user,devices,orders,p=setup_scope
    user.role=m.Role.query.filter_by(code='SUPER_ADMIN').one()
    with c.session_transaction() as sess:sess['user_csv_csrf']='synthetic-csrf'
    response=preview(c,row(scope_enabled='true',modalities='CT',device_keys='CSV-UAT/UAT_1',room_keys='CSV-UAT/Room 1'))
    assert response.status_code==200 and token(response)
    assert apply(c,token(response)).status_code==302
    new=m.User.query.filter_by(username='CSV-NEW').one()
    exported=s.export_values(m,new)
    assert exported['room_keys']=='CSV-UAT/Room 1' and exported['modalities']=='CT'
    assert s.allowed(m,new,orders[0]) and not s.allowed(m,new,orders[1])


def test_admin_scope_csrf_and_creation_validation(setup_scope):
    c,user,devices,orders,p=setup_scope
    target_role=user.role
    admin=m.User(username='SCOPE-ADMIN',full_name='Synthetic Admin',password_hash='none',role_id=m.Role.query.filter_by(code='SUPER_ADMIN').one().id,active=True)
    m.db.session.add(admin);m.db.session.flush()
    # Fixture's current_user closure remains the same object; promote it after saving a target account.
    target=m.User(username='SCOPE-TARGET',full_name='Synthetic Target',password_hash='none',role_id=target_role.id,active=True)
    m.db.session.add(target);m.db.session.flush()
    user.role=admin.role
    path='/admin/users/%s/clinical-scope'%target.id
    assert c.get(path).status_code==200
    assert c.post(path,data={'scope_enabled':'true','modalities':'CT'}).status_code==403
    with c.session_transaction() as sess:csrf=sess['clinical_scope_csrf']
    assert c.post(path,data={'scope_csrf':csrf,'scope_enabled':'true','modalities':['CT'],'room_keys':['CSV-UAT/Room 1']}).status_code==302
    assert s.read(m,target)['modalities']==['CT']
    payload=dict(username='SCOPE-CREATE',full_name='Synthetic New Technician',password='Synthetic-Only-Password',role_id=target_role.id,branch_id='',scope_present='1',scope_csrf=csrf,scope_enabled='true',modalities=['CT'],device_keys=['CSV-UAT/UAT_1'])
    assert c.post('/admin/users',data=payload).status_code==200
    new=m.User.query.filter_by(username='SCOPE-CREATE').one()
    assert s.read(m,new)['device_keys']==['CSV-UAT/UAT_1']
    payload.update(username='SCOPE-BAD-CREATE',modalities=['UNKNOWN'])
    assert c.post('/admin/users',data=payload).status_code==302
    assert not m.User.query.filter_by(username='SCOPE-BAD-CREATE').first()
