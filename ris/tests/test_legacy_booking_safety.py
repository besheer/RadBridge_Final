from datetime import datetime,timedelta
from types import SimpleNamespace
from uuid import uuid4
from unittest.mock import Mock
import pytest


@pytest.fixture
def booking_case(app_ctx,monkeypatch):
    m=app_ctx;key='CODEX-UAT-'+uuid4().hex[:12]
    branch=m.Branch(code=key,name=key,active=True)
    p=m.Patient(patient_id=key,name='CODEX UAT Booking',dob='19900101',sex='M')
    proc=m.Procedure(code=key,name=key,modality='DX',duration_min=30,active=True)
    m.db.session.add_all([branch,p,proc]);m.db.session.flush()
    d=m.Device(branch_id=branch.id,name=key,modality='DX',ae_title='CODEX_UAT',active=True)
    m.db.session.add(d);m.db.session.add(m.ProcedureBranch(branch_id=branch.id,procedure_id=proc.id,active=True));m.db.session.flush()
    u=SimpleNamespace(id=99500,active=True,username=key,branch_id=branch.id,
        role=SimpleNamespace(code='SUPER_ADMIN',permissions=lambda:['*']))
    monkeypatch.setattr(m,'current_user',lambda:u)
    monkeypatch.setattr(m,'render_template',lambda *a,**k:'CODEX UAT')
    monkeypatch.setattr(m.db.session,'commit',m.db.session.flush)
    lock=Mock(wraps=m.acquire_booking_slot_lock);monkeypatch.setattr(m,'acquire_booking_slot_lock',lock)
    yield SimpleNamespace(m=m,branch=branch,p=p,proc=proc,d=d,user=u,lock=lock)
    m.db.session.rollback();m.db.session.remove()


def book(c,when='2037-02-03T10:00',**kw):
    values={'patient_id':c.p.id,'branch_id':c.branch.id,'procedure_id':c.proc.id,
            'device_id':c.d.id,'scheduled':when};values.update(kw)
    return c.m.app.test_client().post('/appointments',data=values)


@pytest.mark.parametrize('start',['2037-02-03T10:00','2037-02-03T10:15','2037-02-03T09:45'])
def test_same_device_overlap_is_blocked_without_overwriting_first_booking(booking_case,start):
    c=booking_case
    assert book(c).status_code==302
    row=c.m.Appointment.query.filter_by(device_id=c.d.id).one()
    assert row.duration_min==30
    assert book(c,start).status_code==302
    assert c.m.Appointment.query.filter_by(device_id=c.d.id).count()==1
    assert c.m.AuditLog.query.filter_by(action='APPOINTMENT_CREATE',entity_id=str(row.id)).count()==1
    assert c.lock.call_count==2


def test_adjacent_and_other_device_bookings_are_allowed(booking_case):
    c=booking_case;book(c);book(c,'2037-02-03T10:30')
    d=c.m.Device(branch_id=c.branch.id,name='CODEX UAT second',modality='DX',ae_title='CODEX_UAT2')
    c.m.db.session.add(d);c.m.db.session.flush();book(c,device_id=d.id)
    assert c.m.Appointment.query.filter_by(branch_id=c.branch.id).count()==3


@pytest.mark.parametrize('status',['CANCELLED','NO_SHOW'])
def test_cancelled_or_no_show_slot_can_be_rebooked(booking_case,status):
    c=booking_case;book(c)
    c.m.Appointment.query.filter_by(device_id=c.d.id).one().status=status
    book(c)
    assert c.m.Appointment.query.filter_by(device_id=c.d.id).count()==2


@pytest.mark.parametrize('boundary',['inactive','disabled','maintenance','wrong_modality','wrong_branch','outside_hours','bad_date'])
def test_device_and_time_constraints_prevent_creation(booking_case,boundary):
    c=booking_case;when='2037-02-03T10:00'
    if boundary=='inactive':c.d.active=False
    if boundary=='disabled':c.d.booking_enabled=False
    if boundary=='maintenance':c.d.operational_status='MAINTENANCE'
    if boundary=='wrong_modality':c.d.modality='CT'
    if boundary=='wrong_branch':c.d.branch_id=999999
    if boundary=='outside_hours':when='2037-02-03T07:00'
    if boundary=='bad_date':when='bad-date'
    assert book(c,when).status_code==302
    assert c.m.Appointment.query.filter_by(branch_id=c.branch.id).count()==0


def test_device_block_prevents_booking(booking_case):
    c=booking_case
    row=c.m.DeviceBlock(device_id=c.d.id,start_at=datetime(2037,2,3,9),end_at=datetime(2037,2,3,11),reason='CODEX UAT maintenance')
    c.m.db.session.add(row);c.m.db.session.flush()
    assert book(c).status_code==302
    assert c.m.Appointment.query.filter_by(device_id=c.d.id).count()==0


def test_missing_device_can_use_existing_branch_route(booking_case):
    c=booking_case
    assert book(c,device_id='').status_code==302
    assert c.m.Appointment.query.filter_by(device_id=c.d.id).count()==1
