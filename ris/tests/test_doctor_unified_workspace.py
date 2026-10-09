"""Behavior tests against SQLite, no PACS/network or production database."""
import json
import uuid
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest
import app as m


@pytest.fixture
def workspace(app_ctx, monkeypatch):
    def no_network(*args,**kwargs):
        raise m.requests.ConnectionError('Network disabled in workspace tests')
    monkeypatch.setattr(m.requests.sessions.Session,'request',no_network)
    suffix=uuid.uuid4().hex[:10]
    def user(code):
        role=m.Role(code=code, name=code+suffix,
                    permissions_json=json.dumps(['reports.view','reports.edit']))
        u=m.User(username=code+suffix, full_name='UAT Doctor', password_hash='test', role=role, active=True)
        m.db.session.add(u); m.db.session.flush()
        return u
    # Reuse role records to respect the unique role code.
    def existing_user(code):
        role=m.Role.query.filter_by(code=code).first()
        if role is None:
            return user(code)
        monkeypatch.setattr(role, 'permissions_json', json.dumps(['reports.view','reports.edit']))
        u=m.User(username=code+suffix+str(len(m.db.session.new)), full_name='UAT Doctor', password_hash='test',role=role,active=True)
        m.db.session.add(u); m.db.session.flush(); return u
    doctor=existing_user('RADIOLOGIST')
    other=m.User(username='other'+suffix,full_name='Other UAT Doctor',password_hash='test',role=doctor.role,active=True)
    m.db.session.add(other); m.db.session.flush()
    admin=existing_user('SUPER_ADMIN')
    tech=existing_user('TECHNICIAN')
    patient=m.Patient(patient_id='W'+suffix,name='Synthetic Workspace')
    m.db.session.add(patient); m.db.session.flush()
    def order(label,owner):
        o=m.Order(accession=label+suffix,patient_id=patient.id,modality='DX',procedure='UAT',
                  status='COMPLETED',scheduled=datetime.utcnow(),assigned_doctor_id=owner)
        m.db.session.add(o);m.db.session.flush();return o
    mine=order('MINE',doctor.id); foreign=order('OTHER',other.id); free=order('FREE',None)
    def offer(o,owner,status='PENDING',delta=300):
        x=m.AssignmentOffer(order_id=o.id,doctor_user_id=owner,status=status,
            offered_at=datetime.utcnow(),expires_at=datetime.utcnow()+timedelta(seconds=delta),attempt_no=1)
        m.db.session.add(x);m.db.session.flush();return x
    pending=offer(free,doctor.id)
    foreign_offer=offer(foreign,other.id)
    expired=offer(mine,doctor.id,delta=-1)
    m.db.session.commit()
    monkeypatch.setattr(m,'expire_assignment_offers',lambda: [])
    monkeypatch.setattr(m,'offer_next_doctor',lambda *a,**k:(None,'COORDINATOR'))
    monkeypatch.setattr(m,'ohif_url_for_order',lambda o:'https://viewer.invalid/study')
    client=m.app.test_client()
    def login(u):
        with client.session_transaction() as session: session['uid']=u.id
    login(doctor)
    yield SimpleNamespace(**locals())
    m.db.session.rollback();m.db.session.remove()


def test_personal_feed_hides_other_and_unassigned_cases(workspace):
    w=workspace; r=w.client.get('/api/doctor/workspace')
    assert r.status_code==200
    assert [c['id'] for c in r.json['cases']]==[w.mine.id]
    assert [o['id'] for o in r.json['offers']]==[w.pending.id]
    assert r.headers['Cache-Control']=='no-store'


def test_inactive_and_technician_denied(workspace):
    w=workspace; w.login(w.tech)
    assert w.client.get('/api/doctor/workspace').status_code==403
    w.login(w.doctor);w.doctor.active=False;m.db.session.commit()
    assert w.client.get('/api/doctor/workspace').status_code==403


def test_anonymous_feed_requires_login(workspace):
    assert m.app.test_client().get('/api/doctor/workspace').status_code==302


def test_foreign_report_and_viewer_denied_before_creation(workspace):
    w=workspace
    assert w.client.get(f'/reports/{w.foreign.id}').status_code==403
    assert w.client.get(f'/doctor/cases/{w.foreign.id}/open').status_code==403
    assert m.Report.query.filter_by(order_id=w.foreign.id).count()==0


def test_viewer_only_for_owned_linked_case(workspace):
    w=workspace
    feed=w.client.get('/api/doctor/workspace').json['cases']
    assert feed[0]['has_linked_study'] is False
    assert w.client.get(f'/doctor/cases/{w.mine.id}/open').status_code==409
    w.mine.pacs_study_id='synthetic';m.db.session.commit()
    feed=w.client.get('/api/doctor/workspace').json['cases']
    assert feed[0]['has_linked_study'] is True
    r=w.client.get(f'/doctor/cases/{w.mine.id}/open')
    assert r.status_code==302 and r.location=='https://viewer.invalid/study'


def test_admin_can_open_foreign_case_but_feed_is_personal(workspace):
    w=workspace;w.login(w.admin);w.foreign.pacs_study_id='synthetic';m.db.session.commit()
    assert w.client.get(f'/doctor/cases/{w.foreign.id}/open').status_code==302
    assert w.client.get('/api/doctor/workspace').json['cases']==[]


def test_foreign_offer_denied_even_for_admin_workspace(workspace):
    w=workspace
    for user in (w.doctor,w.admin):
        w.login(user)
        r=w.client.post(f'/assignment/offers/{w.foreign_offer.id}/respond',
            data={'action':'REJECT'},headers={'X-RadBridge-Workspace':'doctor'})
        assert r.status_code==403
    assert w.foreign_offer.status=='PENDING'


@pytest.mark.parametrize('action',['REJECT','BUSY'])
def test_non_accept_stays_in_workspace(workspace,action):
    w=workspace
    m.db.session.add(m.AssignmentOfferPolicy(enabled=True));m.db.session.commit()
    r=w.client.post(f'/assignment/offers/{w.pending.id}/respond',data={'action':action},
        headers={'X-RadBridge-Workspace':'doctor'})
    assert r.status_code==200 and r.json['ok'] is True
    assert r.json['open_url'] is None
    assert w.free.assigned_doctor_id is None
    assert w.pending.status==('BUSY' if action=='BUSY' else 'REJECTED')


def test_accept_uses_atomic_service_and_returns_guarded_link(workspace):
    w=workspace
    r=w.client.post(f'/assignment/offers/{w.pending.id}/respond',data={'action':'ACCEPT'},
        headers={'X-RadBridge-Workspace':'doctor'})
    assert r.status_code==200, r.get_data(as_text=True)
    assert r.json['open_url']==f'/doctor/cases/{w.free.id}/open'
    assert w.free.assigned_doctor_id==w.doctor.id
    assert m.CaseAssignment.query.filter_by(order_id=w.free.id,active=True).count()==1
    duplicate=w.client.post(f'/assignment/offers/{w.pending.id}/respond',data={'action':'ACCEPT'},
        headers={'X-RadBridge-Workspace':'doctor'})
    assert duplicate.status_code==409


def test_expired_and_invalid_action_are_not_accepted(workspace):
    w=workspace
    for offer,action,code in [(w.expired,'ACCEPT',409),(w.pending,'INVALID',400)]:
        r=w.client.post(f'/assignment/offers/{offer.id}/respond',data={'action':action},
            headers={'X-RadBridge-Workspace':'doctor'})
        assert r.status_code==code


def test_signed_identity_denied_after_reassignment(workspace):
    w=workspace
    token=m.create_ohif_doctor_identity(w.doctor,w.mine)
    assert m.verify_ohif_doctor_identity(token,w.mine.id)[1] is None
    w.mine.assigned_doctor_id=w.other.id;m.db.session.commit()
    assert m.verify_ohif_doctor_identity(token,w.mine.id)[1]=='DOCTOR_ASSIGNMENT_REQUIRED'


def test_workspace_template_renders(workspace):
    w=workspace
    with m.app.test_request_context('/doctor'):
        m.session['uid']=w.doctor.id
        html=m.render_template('doctor_unified_workspace.html')
    assert 'rbUnifiedDoctorWorkspace' in html
    assert 'doctor-workspace.js' in html
