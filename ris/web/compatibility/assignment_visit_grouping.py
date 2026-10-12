"""Legacy visit entry points; composition of explicit application ports."""
from application.legacy_runtime import resolve_runtime
from application.services.assignment.visit_assignment import VisitAssignmentService, VisitPolicies
from infrastructure.adapters.assignment.visit_repository import SqlAlchemyVisitRepository


def _service(assign_case=None):
    m = resolve_runtime()
    from assignment_distribution import active_case_count, case_capacity, validate_special_doctor, AUTO_TYPES
    if assign_case is None:
        from case_assignment_service import assign_case_atomically
        assign_case = assign_case_atomically
    repository = SqlAlchemyVisitRepository(session=m.db.session, Order=m.Order, User=m.User,
        Assignment=m.CaseAssignment, Report=m.Report, Offer=m.AssignmentOffer, Visit=m.AssignmentVisit,
        External=m.ExternalIntakeCase, Appointment=m.Appointment, Profile=m.DoctorAssignmentProfile)
    policies = VisitPolicies(m.case_return_is_open, m.assignment_readiness_decision,
        active_case_count, case_capacity, validate_special_doctor, assign_case, AUTO_TYPES)
    return VisitAssignmentService(repository, policies)


def create_visit(patient_id, branch_id, scheduled):
    return _service().create_visit(patient_id, branch_id, scheduled)


def group_members(order, lock=False):
    return _service().group_members(order, lock)


def visit_ready_for_offer(order):
    return _service().visit_ready_for_offer(order)


def prefer_visit_doctor(order, candidates):
    return _service().prefer_visit_doctor(order, candidates)


def assign_visit_atomically(**kwargs):
    from case_assignment_service import assign_case_atomically
    return _service(assign_case_atomically).assign_visit_atomically(**kwargs)
