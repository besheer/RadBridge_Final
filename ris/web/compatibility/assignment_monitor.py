"""Monitoring runtime composition; legacy snapshot API is unchanged."""
from datetime import datetime
from application.legacy_runtime import resolve_runtime
from application.services.assignment.monitoring_queries import AssignmentMonitoring
from infrastructure.adapters.assignment.monitor_repository import SqlAlchemyMonitorRepository


def snapshot(now=None):
    from assignment_distribution import policy_snapshot, case_capacity, AUTO_TYPES
    m=resolve_runtime()
    repository=SqlAlchemyMonitorRepository(m.db.session,Profile=m.DoctorAssignmentProfile,
        Presence=m.DoctorAvailabilityState,Assignment=m.CaseAssignment,Order=m.Order,
        Report=m.Report,Offer=m.AssignmentOffer)
    return AssignmentMonitoring(repository,doctors=m.assignable_doctors,policy=policy_snapshot,
        capacity=case_capacity,auto_types=AUTO_TYPES,clock=datetime.utcnow).snapshot(now)
