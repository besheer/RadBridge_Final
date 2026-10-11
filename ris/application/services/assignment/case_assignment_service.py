"""Transactional safety boundary for RadBridge case assignment.

All assignment writers must call this module while the caller owns the
transaction.  The service deliberately never commits: assignment, offer state,
audit rows, and any caller-owned lifecycle work must succeed or roll back as one
unit.
"""

from dataclasses import dataclass
from datetime import datetime


ASSIGNABLE_ROLE_CODES = frozenset({"RADIOLOGIST", "DOCTOR"})
TERMINAL_ORDER_STATUSES = frozenset({"FINAL", "CANCELLED"})
NON_EDITABLE_REPORT_STATUSES = frozenset({"VERIFIED", "FINAL"})


class CaseAssignmentServiceError(Exception):
    """Stable, UI-safe failure raised by the assignment safety boundary."""

    def __init__(self, code, message=None):
        self.code = str(code or "CASE_ASSIGNMENT_FAILED")
        super().__init__(message or self.code)


@dataclass(frozen=True)
class AssignmentResult:
    order: object
    doctor: object
    assignment: object
    idempotent: bool = False


def _upper(value):
    return str(value or "").upper().strip()


def _lock_order(session, Order, order_id):
    order = (
        session.query(Order)
        .filter(Order.id == int(order_id))
        .populate_existing()
        .with_for_update()
        .one_or_none()
    )
    if order is None:
        raise CaseAssignmentServiceError("ORDER_NOT_FOUND")
    return order


def _assert_assignable_lifecycle(session, Report, order):
    if _upper(getattr(order, "status", "")) in TERMINAL_ORDER_STATUSES:
        raise CaseAssignmentServiceError("CASE_LIFECYCLE_LOCKED")

    report = None
    if Report is not None:
        report = (
            session.query(Report)
            .filter(Report.order_id == int(order.id))
            .populate_existing()
            .with_for_update()
            .one_or_none()
        )
    else:
        report = getattr(order, "report", None)
    if report is not None and _upper(getattr(report, "status", "")) in (
        NON_EDITABLE_REPORT_STATUSES
    ):
        raise CaseAssignmentServiceError("CASE_REPORT_LOCKED")

    from reception_readiness import receiving
    if receiving(order):
        raise CaseAssignmentServiceError('PACS_RECEIVING')


def _load_assignable_doctor(session, User, doctor_user_id):
    doctor = (
        session.query(User)
        .filter(User.id == int(doctor_user_id))
        .populate_existing()
        .with_for_update()
        .one_or_none()
    )

    if doctor is None:
        raise CaseAssignmentServiceError("ASSIGNMENT_DOCTOR_NOT_FOUND")
    if not bool(getattr(doctor, "active", False)):
        raise CaseAssignmentServiceError("ASSIGNMENT_DOCTOR_INACTIVE")

    role = getattr(doctor, "role", None)
    role_code = _upper(getattr(role, "code", ""))
    if role_code not in ASSIGNABLE_ROLE_CODES:
        raise CaseAssignmentServiceError("ASSIGNMENT_DOCTOR_ROLE_INVALID")

    return doctor


def _locked_active_assignments(session, CaseAssignment, order_id):
    return (
        session.query(CaseAssignment)
        .filter(
            CaseAssignment.order_id == int(order_id),
            CaseAssignment.active.is_(True),
        )
        .order_by(CaseAssignment.id)
        .populate_existing()
        .with_for_update()
        .all()
    )


def _cancel_pending_offers(
    session,
    AssignmentOffer,
    order_id,
    now,
    accepted_offer_id=None,
):
    if AssignmentOffer is None:
        return

    rows = (
        session.query(AssignmentOffer)
        .filter(
            AssignmentOffer.order_id == int(order_id),
            AssignmentOffer.status == "PENDING",
        )
        .populate_existing()
        .with_for_update()
        .all()
    )

    for row in rows:
        if accepted_offer_id is not None and row.id == int(accepted_offer_id):
            continue
        row.status = "CANCELLED"
        row.responded_at = now
        if not str(getattr(row, "response_note", "") or "").strip():
            row.response_note = "Cancelled because the case was assigned"


def assign_case_atomically(
    *,
    db,
    Order,
    User,
    CaseAssignment,
    Report=None,
    order_id,
    doctor_user_id,
    assigned_by=None,
    assignment_type="MANUAL",
    notes="",
    require_unassigned=False,
    AssignmentOffer=None,
    accepted_offer_id=None,
    now=None,
):
    """Assign a case under one transaction and one per-order row lock.

    The partial unique database index is the final race-condition backstop.
    Same-doctor retries are idempotent only when Order and CaseAssignment are
    already synchronized.
    """

    session = db.session
    now = now or datetime.utcnow()
    order = _lock_order(session, Order, order_id)
    _assert_assignable_lifecycle(session, Report, order)
    doctor = _load_assignable_doctor(session, User, doctor_user_id)
    from assignment_distribution import validate_special_doctor
    validate_special_doctor(order,doctor)
    active_rows = _locked_active_assignments(session, CaseAssignment, order.id)

    synchronized = (
        len(active_rows) == 1
        and active_rows[0].doctor_user_id == doctor.id
        and getattr(order, "assigned_doctor_id", None) == doctor.id
    )
    if synchronized:
        if _upper(assignment_type) == 'MANUAL':
            active_rows[0].assignment_type = 'MANUAL'
            active_rows[0].start_deadline_at = None
        _cancel_pending_offers(
            session,
            AssignmentOffer,
            order.id,
            now,
            accepted_offer_id=accepted_offer_id,
        )
        return AssignmentResult(
            order=order,
            doctor=doctor,
            assignment=active_rows[0],
            idempotent=True,
        )

    occupied = bool(active_rows or getattr(order, "assigned_doctor_id", None))
    if require_unassigned and occupied:
        raise CaseAssignmentServiceError("CASE_ALREADY_ASSIGNED")

    from assignment_distribution import prepare_auto_assignment, AUTO_TYPES
    if _upper(assignment_type) in AUTO_TYPES and order.assignment_visit_id:
        from application.legacy_runtime import resolve_runtime as _rb_runtime; m = _rb_runtime()
        visit=m.AssignmentVisit.query.filter_by(id=order.assignment_visit_id).first()
        if visit and (visit.assignment_mode=='MANUAL' or visit.registration_open):
            raise CaseAssignmentServiceError('VISIT_AUTOMATIC_ASSIGNMENT_DISABLED')
    deadline = prepare_auto_assignment(order, doctor, _upper(assignment_type), now)

    _cancel_pending_offers(
        session,
        AssignmentOffer,
        order.id,
        now,
        accepted_offer_id=accepted_offer_id,
    )

    for old in active_rows:
        old.active = False
        old.unassigned_at = now

    assignment = CaseAssignment(
        order_id=order.id,
        doctor_user_id=doctor.id,
        assigned_by=assigned_by,
        assignment_type=_upper(assignment_type) or "MANUAL",
        active=True,
        assigned_at=now,
        notes=str(notes or "")[:500],
        **deadline,
    )
    session.add(assignment)

    order.assigned_doctor_id = doctor.id
    order.assigned_at = now
    session.flush()

    return AssignmentResult(
        order=order,
        doctor=doctor,
        assignment=assignment,
        idempotent=False,
    )


def accept_offer_atomically(
    *,
    db,
    Order,
    User,
    CaseAssignment,
    AssignmentOffer,
    Report=None,
    offer_id,
    actor_user_id,
    note="",
    now=None,
):
    """Accept one pending offer and assign its case in the same transaction."""

    session = db.session
    now = now or datetime.utcnow()

    # Resolve the order id, then acquire locks in the global order-first order.
    probe = session.query(AssignmentOffer).filter(AssignmentOffer.id == int(offer_id)).one_or_none()
    if probe is None:
        raise CaseAssignmentServiceError("ASSIGNMENT_OFFER_NOT_FOUND")

    from assignment_visit_grouping import group_members
    group_members(session.query(Order).filter(Order.id == probe.order_id).one(), lock=True)
    order = _lock_order(session, Order, probe.order_id)
    offer = (
        session.query(AssignmentOffer)
        .filter(AssignmentOffer.id == int(offer_id))
        .populate_existing()
        .with_for_update()
        .one_or_none()
    )

    if offer is None:
        raise CaseAssignmentServiceError("ASSIGNMENT_OFFER_NOT_FOUND")
    if int(offer.doctor_user_id) != int(actor_user_id):
        raise CaseAssignmentServiceError("ASSIGNMENT_OFFER_FORBIDDEN")
    if _upper(offer.status) != "PENDING":
        raise CaseAssignmentServiceError("ASSIGNMENT_OFFER_NOT_PENDING")
    if offer.expires_at is not None and now > offer.expires_at:
        offer.status = "TIMEOUT"
        offer.responded_at = now
        raise CaseAssignmentServiceError("ASSIGNMENT_OFFER_EXPIRED")

    from assignment_visit_grouping import assign_visit_atomically
    result = assign_visit_atomically(
        db=db,
        Order=Order,
        User=User,
        CaseAssignment=CaseAssignment,
        Report=Report,
        AssignmentOffer=AssignmentOffer,
        order_id=order.id,
        doctor_user_id=offer.doctor_user_id,
        assigned_by=actor_user_id,
        assignment_type="AUTO_OFFER",
        notes="Accepted assignment offer",
        require_unassigned=True,
        accepted_offer_id=offer.id,
        now=now,
    )

    offer.status = "ACCEPTED"
    offer.responded_at = now
    offer.response_note = str(note or "")[:500]
    session.flush()
    return result, offer
