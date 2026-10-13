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


from typing import Callable


@dataclass(frozen=True)
class AssignmentPolicies:
    validate_doctor: Callable
    prepare_deadline: Callable
    automatic_visit_allowed: Callable
    automatic_types: frozenset

def _upper(value):
    return str(value or "").upper().strip()


def assert_assignable_order(order):
    if _upper(getattr(order, "status", "")) in TERMINAL_ORDER_STATUSES:
        raise CaseAssignmentServiceError("CASE_LIFECYCLE_LOCKED")


def assert_assignable_lifecycle(order, report):
    assert_assignable_order(order)

    if report is not None and _upper(getattr(report, "status", "")) in (
        NON_EDITABLE_REPORT_STATUSES
    ):
        raise CaseAssignmentServiceError("CASE_REPORT_LOCKED")

    from domain.readiness_checks import receiving
    if receiving(order):
        raise CaseAssignmentServiceError('PACS_RECEIVING')


def assert_assignable_doctor(doctor):
    if doctor is None:
        raise CaseAssignmentServiceError("ASSIGNMENT_DOCTOR_NOT_FOUND")
    if not bool(getattr(doctor, "active", False)):
        raise CaseAssignmentServiceError("ASSIGNMENT_DOCTOR_INACTIVE")

    role = getattr(doctor, "role", None)
    role_code = _upper(getattr(role, "code", ""))
    if role_code not in ASSIGNABLE_ROLE_CODES:
        raise CaseAssignmentServiceError("ASSIGNMENT_DOCTOR_ROLE_INVALID")

    return doctor


def assign_case_atomically(
    *,
    repository,
    policies,
    order_id,
    doctor_user_id,
    assigned_by=None,
    assignment_type="MANUAL",
    notes="",
    require_unassigned=False,
    accepted_offer_id=None,
    now=None,
):
    """Assign a case under one transaction and one per-order row lock.

    The partial unique database index is the final race-condition backstop.
    Same-doctor retries are idempotent only when Order and CaseAssignment are
    already synchronized.
    """

    now = now or datetime.utcnow()
    order = repository.lock_order(order_id)
    assert_assignable_order(order)
    assert_assignable_lifecycle(order, repository.lock_report(order))
    doctor = assert_assignable_doctor(repository.lock_doctor(doctor_user_id))
    policies.validate_doctor(order, doctor)
    active_rows = repository.active_assignments(order.id)

    synchronized = (
        len(active_rows) == 1
        and active_rows[0].doctor_user_id == doctor.id
        and getattr(order, "assigned_doctor_id", None) == doctor.id
    )
    if synchronized:
        if _upper(assignment_type) == 'MANUAL':
            active_rows[0].assignment_type = 'MANUAL'
            active_rows[0].start_deadline_at = None
        cancel_pending_offers(
            repository,
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

    if _upper(assignment_type) in policies.automatic_types and order.assignment_visit_id:
        if not policies.automatic_visit_allowed(order):
            raise CaseAssignmentServiceError('VISIT_AUTOMATIC_ASSIGNMENT_DISABLED')
    deadline = policies.prepare_deadline(order, doctor, _upper(assignment_type), now)

    cancel_pending_offers(
        repository,
        order.id,
        now,
        accepted_offer_id=accepted_offer_id,
    )

    for old in active_rows:
        old.active = False
        old.unassigned_at = now

    assignment = repository.new_assignment(
        order_id=order.id,
        doctor_user_id=doctor.id,
        assigned_by=assigned_by,
        assignment_type=_upper(assignment_type) or "MANUAL",
        active=True,
        assigned_at=now,
        notes=str(notes or "")[:500],
        **deadline,
    )

    order.assigned_doctor_id = doctor.id
    order.assigned_at = now
    repository.flush()

    return AssignmentResult(
        order=order,
        doctor=doctor,
        assignment=assignment,
        idempotent=False,
    )


def cancel_pending_offers(
    repository,
    order_id,
    now,
    accepted_offer_id=None,
):
    rows = repository.pending_offers(order_id)

    for row in rows:
        if accepted_offer_id is not None and row.id == int(accepted_offer_id):
            continue
        row.status = "CANCELLED"
        row.responded_at = now
        if not str(getattr(row, "response_note", "") or "").strip():
            row.response_note = "Cancelled because the case was assigned"


def accept_offer_atomically(
    *,
    repository,
    group_members,
    assign_visit,
    offer_id,
    actor_user_id,
    note="",
    now=None,
):
    """Accept one pending offer and assign its case in the same transaction."""

    now = now or datetime.utcnow()

    # Resolve the order id, then acquire locks in the global order-first order.
    probe = repository.offer_probe(offer_id)
    if probe is None:
        raise CaseAssignmentServiceError("ASSIGNMENT_OFFER_NOT_FOUND")

    group_members(repository.order_for_offer(probe), lock=True)
    order = repository.lock_order(probe.order_id)
    offer = repository.lock_offer(offer_id)

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

    result = assign_visit(
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
    repository.flush()
    return result, offer
