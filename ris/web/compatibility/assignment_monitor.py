"""Monitoring runtime composition using explicit application bindings."""
from datetime import datetime
from application.services.assignment.monitoring_queries import AssignmentMonitoring
from infrastructure.adapters.assignment.monitor_repository import SqlAlchemyMonitorRepository


def snapshot(now=None, *, runtime=None):
    from assignment_distribution import policy_snapshot, case_capacity, AUTO_TYPES
    if runtime is None:
        # Preserve the legacy direct-call API; web routes pass explicit bindings.
        from application.legacy_runtime import resolve_runtime
        runtime=resolve_runtime()
    m=runtime
    repository=SqlAlchemyMonitorRepository(m.db.session,Profile=m.DoctorAssignmentProfile,
        Presence=m.DoctorAvailabilityState,Assignment=m.CaseAssignment,Order=m.Order,
        Report=m.Report,Offer=m.AssignmentOffer)
    return AssignmentMonitoring(repository,doctors=m.assignable_doctors,
        policy=lambda: policy_snapshot(runtime=m),
        capacity=lambda doctor, policy: case_capacity(doctor, policy, runtime=m),
        auto_types=AUTO_TYPES,clock=datetime.utcnow).snapshot(now)
