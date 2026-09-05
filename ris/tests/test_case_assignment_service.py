from datetime import datetime, timedelta

import pytest

import app as m
from case_assignment_service import (
    CaseAssignmentServiceError,
    accept_offer_atomically,
    assign_case_atomically,
)


def _role(code):
    row = m.Role.query.filter_by(code=code).first()
    if row is None:
        row = m.Role(code=code, name=code, permissions_json="[]")
        m.db.session.add(row)
        m.db.session.flush()
    return row


def _doctor(username, role="RADIOLOGIST", active=True):
    row = m.User(
        username=username,
        full_name=username,
        role=_role(role),
        active=active,
        password_hash="test",
    )
    m.db.session.add(row)
    m.db.session.flush()
    return row


def _order(accession, status="IMAGES_RECEIVED", report_status="UNREPORTED"):
    patient = m.Patient(patient_id=f"P-{accession}", name="Assignment Test")
    m.db.session.add(patient)
    m.db.session.flush()
    order = m.Order(
        accession=accession,
        patient_id=patient.id,
        modality="CT",
        procedure="CT Brain",
        scheduled=datetime.utcnow(),
        status=status,
    )
    m.db.session.add(order)
    m.db.session.flush()
    if report_status:
        m.db.session.add(m.Report(order_id=order.id, status=report_status))
        m.db.session.flush()
    return order


def _assign(order, doctor, **kwargs):
    return assign_case_atomically(
        db=m.db,
        Order=m.Order,
        User=m.User,
        CaseAssignment=m.CaseAssignment,
        Report=m.Report,
        AssignmentOffer=m.AssignmentOffer,
        order_id=order.id,
        doctor_user_id=doctor.id,
        **kwargs,
    )


@pytest.fixture(autouse=True)
def clean_assignment_rows(app_ctx):
    yield
    m.db.session.rollback()
    m.db.session.remove()


def test_model_declares_one_active_assignment_index(app_ctx):
    indexes = {index.name: index for index in m.CaseAssignment.__table__.indexes}
    assert "uq_case_assignment_one_active_per_order" in indexes
    assert indexes["uq_case_assignment_one_active_per_order"].unique is True


def test_assign_keeps_order_and_active_row_synchronized(app_ctx):
    doctor = _doctor("assignment-doctor-1")
    order = _order("ASSIGN-SAFE-1")

    result = _assign(
        order,
        doctor,
        assigned_by=doctor.id,
        assignment_type="OPEN_POOL",
        require_unassigned=True,
    )

    assert result.idempotent is False
    assert order.assigned_doctor_id == doctor.id
    assert order.assigned_at == result.assignment.assigned_at
    assert m.CaseAssignment.query.filter_by(order_id=order.id, active=True).count() == 1


def test_same_doctor_retry_is_idempotent(app_ctx):
    doctor = _doctor("assignment-doctor-2")
    order = _order("ASSIGN-SAFE-2")

    first = _assign(order, doctor, assigned_by=doctor.id)
    second = _assign(order, doctor, assigned_by=doctor.id)

    assert second.idempotent is True
    assert second.assignment.id == first.assignment.id
    assert m.CaseAssignment.query.filter_by(order_id=order.id, active=True).count() == 1


def test_open_pool_race_loser_cannot_replace_assignment(app_ctx):
    first_doctor = _doctor("assignment-doctor-3")
    second_doctor = _doctor("assignment-doctor-4")
    order = _order("ASSIGN-SAFE-3")
    _assign(order, first_doctor, require_unassigned=True)

    with pytest.raises(CaseAssignmentServiceError) as caught:
        _assign(order, second_doctor, require_unassigned=True)

    assert caught.value.code == "CASE_ALREADY_ASSIGNED"
    assert order.assigned_doctor_id == first_doctor.id


def test_controlled_reassignment_deactivates_old_row(app_ctx):
    first_doctor = _doctor("assignment-doctor-5")
    second_doctor = _doctor("assignment-doctor-6")
    order = _order("ASSIGN-SAFE-4")
    first = _assign(order, first_doctor)

    second = _assign(order, second_doctor, assignment_type="MANUAL")

    assert first.assignment.active is False
    assert first.assignment.unassigned_at is not None
    assert second.assignment.active is True
    assert order.assigned_doctor_id == second_doctor.id
    assert m.CaseAssignment.query.filter_by(order_id=order.id, active=True).count() == 1


def test_assignment_cancels_pending_offers(app_ctx):
    doctor = _doctor("assignment-doctor-7")
    offered = _doctor("assignment-doctor-8")
    order = _order("ASSIGN-SAFE-5")
    pending = m.AssignmentOffer(
        order_id=order.id,
        doctor_user_id=offered.id,
        status="PENDING",
        expires_at=datetime.utcnow() + timedelta(minutes=5),
    )
    m.db.session.add(pending)
    m.db.session.flush()

    _assign(order, doctor)

    assert pending.status == "CANCELLED"
    assert pending.responded_at is not None


@pytest.mark.parametrize(
    "order_status,report_status,expected",
    [
        ("FINAL", "FINAL", "CASE_LIFECYCLE_LOCKED"),
        ("IMAGES_RECEIVED", "VERIFIED", "CASE_REPORT_LOCKED"),
    ],
)
def test_terminal_or_verified_case_cannot_be_assigned(
    app_ctx, order_status, report_status, expected
):
    doctor = _doctor(f"assignment-doctor-{expected}")
    order = _order(
        f"ASSIGN-{expected}",
        status=order_status,
        report_status=report_status,
    )

    with pytest.raises(CaseAssignmentServiceError) as caught:
        _assign(order, doctor)

    assert caught.value.code == expected


@pytest.mark.parametrize("role,active", [("RECEPTION", True), ("RADIOLOGIST", False)])
def test_invalid_assignment_target_is_rejected(app_ctx, role, active):
    doctor = _doctor(f"assignment-target-{role}-{active}", role=role, active=active)
    order = _order(f"ASSIGN-TARGET-{role}-{active}")

    with pytest.raises(CaseAssignmentServiceError):
        _assign(order, doctor)


def test_offer_acceptance_is_atomic_and_cancels_competing_offer(app_ctx):
    doctor = _doctor("assignment-offer-doctor")
    other = _doctor("assignment-offer-other")
    order = _order("ASSIGN-OFFER-1")
    now = datetime.utcnow()
    accepted = m.AssignmentOffer(
        order_id=order.id,
        doctor_user_id=doctor.id,
        status="PENDING",
        expires_at=now + timedelta(minutes=5),
    )
    competing = m.AssignmentOffer(
        order_id=order.id,
        doctor_user_id=other.id,
        status="PENDING",
        expires_at=now + timedelta(minutes=5),
    )
    m.db.session.add_all([accepted, competing])
    m.db.session.flush()

    result, offer = accept_offer_atomically(
        db=m.db,
        Order=m.Order,
        User=m.User,
        CaseAssignment=m.CaseAssignment,
        Report=m.Report,
        AssignmentOffer=m.AssignmentOffer,
        offer_id=accepted.id,
        actor_user_id=doctor.id,
        now=now,
    )

    assert result.order.assigned_doctor_id == doctor.id
    assert offer.status == "ACCEPTED"
    assert competing.status == "CANCELLED"
