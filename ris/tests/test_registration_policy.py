import json
from datetime import datetime
import pytest
from werkzeug.datastructures import MultiDict
import app as m
import registration_policy as policy
from test_assignment_distribution import doctor
from test_registration_calendar_and_guidance import _entities

@pytest.fixture(autouse=True)
def isolated(app_ctx, monkeypatch):
    monkeypatch.setattr(m.db.session, 'commit', m.db.session.flush)
    yield
    m.db.session.rollback()
    m.db.session.remove()

def setup(monkeypatch):
    admin = doctor('registration-policy-admin', 'SUPER_ADMIN')
    user, branch, device, proc, patient = _entities(m)
    import uuid
    patient=m.Patient(patient_id='CODEX-UAT-'+uuid.uuid4().hex[:8],name='CODEX UAT Registration',phone='01012345678')
    m.db.session.add(patient);m.db.session.flush()
    monkeypatch.setattr(m, 'current_user', lambda: admin)
    monkeypatch.setattr(m, 'acquire_booking_slot_lock', lambda *a: None)
    monkeypatch.setattr(m, 'booking_restriction_reason', lambda *a: None)
    monkeypatch.setattr(m, 'procedure_available_in_branch', lambda *a: True)
    monkeypatch.setattr(m, 'ensure_journey', lambda *a: None)
    return (admin, branch, device, proc, patient)

def rule(key='patient.phone', **kwargs):
    row = m.FieldRule.query.filter_by(field_key=key).first()
    if not row:
        row = m.FieldRule(field_key=key, label_en=key, label_ar=key)
        m.db.session.add(row)
    row.visible = True
    row.required = True
    row.data_type = 'NUMBERS'
    row.exact_length = 11
    for k, v in kwargs.items():
        setattr(row, k, v)
    m.db.session.flush()
    return row

def test_shared_rule_rejects_missing_and_invalid_required_mobile():
    rule()
    with m.app.test_request_context('/'):
        for phone in ['', 'abc', '123']:
            with pytest.raises(ValueError):
                policy.validate_patient_fields(dict(phone=phone))
        policy.validate_patient_fields(dict(phone='01012345678'))

def test_calendar_patient_creation_enforces_policy_and_persists_email_nationality():
    rule()
    form = MultiDict({'new_first_name': 'CODEX-UAT', 'new_middle_name': 'Policy', 'new_dob': '2000-01-01'})
    before = m.Patient.query.count()
    with m.app.test_request_context('/'):
        with pytest.raises(ValueError):
            m._rb_registration_v2_create_patient(form)
        assert m.Patient.query.count() == before
        form.update(dict(new_phone='01012345678', new_email='synthetic@example.invalid', new_nationality='Synthetic'))
        p = m._rb_registration_v2_create_patient(form)
        assert p.email == 'synthetic@example.invalid'
        assert m.PatientDemographicsExtra.query.filter_by(patient_id=p.id).first().nationality == 'Synthetic'

def test_manual_registration_assigns_entire_visit_and_excludes_auto(monkeypatch):
    admin, branch, device, proc, patient = setup(monkeypatch)
    u = doctor('registration-manual-doctor')
    second = m.Procedure(code='REGPOL2', name='CODEX-UAT second CT', modality='CT', duration_min=10, active=True)
    m.db.session.add(second)
    m.db.session.flush()
    client = m.app.test_client()
    with client.session_transaction() as s:
        s['uid'] = admin.id
    response = client.post('/schedule/unified-submit', data=MultiDict([('registration_action', 'REGISTER'), ('scheduled', '2037-02-03T10:00:00'), ('branch_id', str(branch.id)), ('device_id', str(device.id)), ('patient_mode', 'existing'), ('patient_id', str(patient.id)), ('procedure_ids', str(proc.id)), ('procedure_ids', str(second.id)), ('assignment_mode', 'MANUAL'), ('selected_doctor_id', str(u.id))]))
    assert response.status_code == 302
    orders = m.Order.query.filter_by(patient_id=patient.id).all()
    assert len(orders) == 2 and all((o.assigned_doctor_id == u.id for o in orders))
    assert len({o.assignment_visit_id for o in orders}) == 1
    assignments = m.CaseAssignment.query.filter(m.CaseAssignment.order_id.in_([o.id for o in orders])).all()
    assert len(assignments) == 2 and all((a.assignment_type == 'MANUAL' and (not a.start_deadline_at) for a in assignments))
    from assignment_visit_grouping import visit_ready_for_offer
    assert visit_ready_for_offer(orders[0])[1] == 'VISIT_MANUAL_RESERVATION'

def test_manual_booking_survives_checkin_without_auto(monkeypatch):
    admin, branch, device, proc, patient = setup(monkeypatch)
    u = doctor('registration-booked-doctor')
    client = m.app.test_client()
    with client.session_transaction() as s:
        s['uid'] = admin.id
    client.post('/schedule/unified-submit', data=dict(registration_action='BOOK', scheduled='2037-02-03T10:00:00', branch_id=branch.id, device_id=device.id, patient_mode='existing', patient_id=patient.id, procedure_ids=proc.id, assignment_mode='MANUAL', selected_doctor_id=u.id))
    a = m.Appointment.query.filter_by(patient_id=patient.id).one()
    assert m.Order.query.filter_by(patient_id=patient.id).count() == 0
    response = client.post(f'/appointments/{a.id}/checkin')
    assert response.status_code == 302
    o = m.Order.query.filter_by(patient_id=patient.id).one()
    assert o.assigned_doctor_id == u.id and a.order_id == o.id
    assert m.CaseAssignment.query.filter_by(order_id=o.id).one().assignment_type == 'MANUAL'

def test_open_visit_blocks_auto_and_same_visit_can_link_another_device(monkeypatch):
    admin, branch, device, proc, patient = setup(monkeypatch)
    with m.app.test_request_context('/'):
        vid = policy.select_visit(patient, branch, datetime(2037, 2, 3, 10), [proc], MultiDict({'visit_registration_open': '1'}))
        o = m.Order(accession='CODEX-UAT-POLICY', patient_id=patient.id, branch_id=branch.id, modality='CT', procedure='Synthetic', scheduled=datetime(2037, 2, 3, 10), status='REGISTERED', assignment_visit_id=vid)
        m.db.session.add(o)
        m.db.session.flush()
        from assignment_visit_grouping import visit_ready_for_offer
        assert visit_ready_for_offer(o)[1] == 'VISIT_REGISTRATION_OPEN'
        assert policy.select_visit(patient, branch, datetime(2037, 2, 3, 11), [proc], MultiDict({'assignment_visit_id': vid})) == vid
        assert not m.AssignmentVisit.query.filter_by(id=vid).one().registration_open

@pytest.mark.parametrize('mismatch', ['patient', 'branch', 'date'])
def test_visit_link_mismatch_fails_closed(monkeypatch, mismatch):
    admin, branch, device, proc, patient = setup(monkeypatch)
    with m.app.test_request_context('/'):
        vid = policy.select_visit(patient, branch, datetime(2037, 2, 3), [proc], MultiDict())
        visit = m.AssignmentVisit.query.filter_by(id=vid).one()
        if mismatch == 'patient':
            visit.patient_id += 1
        if mismatch == 'branch':
            visit.branch_id += 1
        if mismatch == 'date':
            visit.visit_date = datetime(2037, 2, 4).date()
        m.db.session.flush()
        with pytest.raises(ValueError, match='same patient, branch and date'):
            policy.select_visit(patient, branch, datetime(2037, 2, 3), [proc], MultiDict({'assignment_visit_id': vid}))

def test_no_doctor_override_without_assignment_permission(monkeypatch):
    admin, branch, device, proc, patient = setup(monkeypatch)
    monkeypatch.setattr(m, 'has_perm', lambda perm: False)
    from werkzeug.exceptions import Forbidden
    with m.app.test_request_context('/'):
        with pytest.raises(Forbidden):
            policy.select_visit(patient, branch, datetime(2037, 2, 3), [proc], MultiDict({'assignment_mode': 'MANUAL', 'selected_doctor_id': admin.id}))

def test_admin_cannot_make_required_field_hidden(monkeypatch):
    admin, *_ = setup(monkeypatch)
    row = rule()
    client = m.app.test_client()
    with client.session_transaction() as s:
        s['uid'] = admin.id
    client.post('/admin/field-rules', data=dict(rule_id=row.id, data_type='NUMBERS', required='1', visible='0'))
    assert row.visible and row.required

def test_auto_writer_cannot_bypass_manual_reservation(monkeypatch):
    admin, branch, device, proc, patient = setup(monkeypatch)
    u = doctor('registration-auto-bypass')
    with m.app.test_request_context('/'):
        vid = policy.select_visit(patient, branch, datetime(2037, 2, 3), [proc], MultiDict({'assignment_mode': 'MANUAL', 'selected_doctor_id': u.id}))
        o = m.Order(accession='CODEX-UAT-BYPASS', patient_id=patient.id, branch_id=branch.id, modality='CT', procedure='Synthetic', scheduled=datetime(2037, 2, 3), status='REGISTERED', assignment_visit_id=vid)
        m.db.session.add(o)
        m.db.session.flush()
        from case_assignment_service import assign_case_atomically, CaseAssignmentServiceError
        with pytest.raises(CaseAssignmentServiceError, match='AUTOMATIC_ASSIGNMENT_DISABLED'):
            assign_case_atomically(db=m.db, Order=m.Order, User=m.User, CaseAssignment=m.CaseAssignment, Report=m.Report, AssignmentOffer=m.AssignmentOffer, order_id=o.id, doctor_user_id=u.id, assignment_type='AUTO_DIRECT')

def test_selected_doctor_must_cover_whole_visit(monkeypatch):
    admin, branch, device, proc, patient = setup(monkeypatch)
    u = doctor('registration-mr-only')
    m.db.session.add(m.DoctorAssignmentProfile(user_id=u.id, modalities='MR', max_active_cases=20))
    m.db.session.flush()
    with m.app.test_request_context('/'):
        with pytest.raises(ValueError, match='qualify for every'):
            policy.select_visit(patient, branch, datetime(2037, 2, 3), [proc], MultiDict({'assignment_mode': 'MANUAL', 'selected_doctor_id': u.id}))
