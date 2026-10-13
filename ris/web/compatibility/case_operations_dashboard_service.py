"""Compatibility composition for read-only operational aggregation."""
from datetime import datetime, timezone
from domain.readiness_checks import view
from application.services.readiness.operations_snapshot import build_case_operations_snapshot as _snapshot
from application.services.readiness.operations_snapshot import (
    _upper, _utc_now_naive, TERMINAL_ORDER_STATUSES, TERMINAL_REPORT_STATUSES,
)
from infrastructure.adapters.readiness.snapshot_repository import SqlAlchemyOperationsSnapshotRepository

def build_case_operations_snapshot(
    *,
    db,
    Order,
    Report,
    CaseAssignment,
    AssignmentOffer,
    AssignmentStrategy,
    AssignmentEscalationEvent,
    CaseReadiness,
    PacsStudyInbox,
    PacsExamLink,
    PacsResolutionEvent,
    limit=300,
    now=None,
    branch_ids=None,
):
    return _snapshot(repository=SqlAlchemyOperationsSnapshotRepository(db.session, Order, Report, CaseAssignment, AssignmentOffer, AssignmentStrategy, AssignmentEscalationEvent, CaseReadiness, PacsStudyInbox, PacsExamLink, PacsResolutionEvent),
        readiness_view=view, clock=_utc_now_naive,limit=limit,now=now,branch_ids=branch_ids)
