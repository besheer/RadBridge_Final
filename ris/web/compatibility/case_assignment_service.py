"""Transactional safety boundary for RadBridge case assignment.

All assignment writers must call this module while the caller owns the
transaction.  The service deliberately never commits: assignment, offer state,
audit rows, and any caller-owned lifecycle work must succeed or roll back as one
unit.
"""

from datetime import datetime


ASSIGNABLE_ROLE_CODES = frozenset({"RADIOLOGIST", "DOCTOR"})
TERMINAL_ORDER_STATUSES = frozenset({"FINAL", "CANCELLED"})
NON_EDITABLE_REPORT_STATUSES = frozenset({"VERIFIED", "FINAL"})


from application.services.assignment.assignment_transaction import (
    CaseAssignmentServiceError, AssignmentResult, AssignmentPolicies,
    assert_assignable_lifecycle, assert_assignable_order, assert_assignable_doctor,
    cancel_pending_offers, assign_case_atomically as _assign_core,
    accept_offer_atomically as _accept_core,
)
from infrastructure.adapters.assignment.transaction_repository import SqlAlchemyAssignmentRepository

def _upper(value):
    return str(value or "").upper().strip()


def _lock_order(session, Order, order_id):
    return SqlAlchemyAssignmentRepository(session=session, Order=Order, User=None, Assignment=None).lock_order(order_id)


def _assert_assignable_lifecycle(session, Report, order):
    assert_assignable_order(order)
    repository = SqlAlchemyAssignmentRepository(session=session, Order=None, User=None, Assignment=None, Report=Report)
    return assert_assignable_lifecycle(order, repository.lock_report(order))


def _load_assignable_doctor(session, User, doctor_user_id):
    repository = SqlAlchemyAssignmentRepository(session=session, Order=None, User=User, Assignment=None)
    return assert_assignable_doctor(repository.lock_doctor(doctor_user_id))


def _locked_active_assignments(session, CaseAssignment, order_id):
    return SqlAlchemyAssignmentRepository(session=session, Order=None, User=None, Assignment=CaseAssignment).active_assignments(order_id)


def _cancel_pending_offers(session, AssignmentOffer, order_id, now, accepted_offer_id=None):
    repository = SqlAlchemyAssignmentRepository(session=session, Order=None, User=None, Assignment=None, Offer=AssignmentOffer)
    return cancel_pending_offers(repository, order_id, now, accepted_offer_id)


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
    from assignment_distribution import validate_special_doctor, prepare_auto_assignment, AUTO_TYPES
    from application.legacy_runtime import resolve_runtime
    def automatic_visit_allowed(order):
        m = resolve_runtime()
        visit = m.AssignmentVisit.query.filter_by(id=order.assignment_visit_id).first()
        return not (visit and (visit.assignment_mode == 'MANUAL' or visit.registration_open))
    policies = AssignmentPolicies(validate_special_doctor, prepare_auto_assignment, automatic_visit_allowed, AUTO_TYPES)
    repository = SqlAlchemyAssignmentRepository(session=db.session, Order=Order, User=User,
        Assignment=CaseAssignment, Report=Report, Offer=AssignmentOffer)
    return _assign_core(repository=repository, policies=policies, order_id=order_id,
        doctor_user_id=doctor_user_id, assigned_by=assigned_by, assignment_type=assignment_type,
        notes=notes, require_unassigned=require_unassigned, accepted_offer_id=accepted_offer_id, now=now)


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
    from assignment_visit_grouping import group_members, assign_visit_atomically
    repository = SqlAlchemyAssignmentRepository(session=db.session, Order=Order, User=User,
        Assignment=CaseAssignment, Report=Report, Offer=AssignmentOffer)
    def assign_visit(**values):
        return assign_visit_atomically(db=db, Order=Order, User=User, CaseAssignment=CaseAssignment,
            Report=Report, AssignmentOffer=AssignmentOffer, **values)
    return _accept_core(repository=repository, group_members=group_members, assign_visit=assign_visit,
        offer_id=offer_id, actor_user_id=actor_user_id, note=note, now=now)
