"""Read-only aggregation for the Case Operations Control Center.

The service deliberately contains no workflow mutations and no transaction
commit.  Existing RadBridge routes remain the authority for every action.
"""

from datetime import datetime, timezone




TERMINAL_ORDER_STATUSES = {"FINAL", "CANCELLED"}
TERMINAL_REPORT_STATUSES = {"VERIFIED", "FINAL"}


def _upper(value, default=""):
    return str(value or default).upper().strip()


def _utc_now_naive():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def build_case_operations_snapshot(*, repository, readiness_view, clock, limit=300, now=None):
    """Return a unified, read-only operational snapshot.

    ``limit`` bounds all worklists.  The function never calls flush/commit and
    never evaluates readiness or assignment policy; it only reports persisted
    authoritative state.
    """

    now = now or clock()
    limit = max(1, min(int(limit or 300), 1000))

    orders = repository.orders(limit)
    order_ids = [row.id for row in orders]

    reports = {row.order_id: row for row in repository.reports(order_ids)}
    readiness = {row.order_id: row for row in repository.readiness(order_ids)}
    assignments = {row.order_id: row for row in repository.assignments(order_ids)}

    pending_offers = {}
    if order_ids:
        for row in repository.pending_offers(order_ids):
            pending_offers.setdefault(row.order_id, []).append(row)

    current_leases = {}
    expired_lease_count = 0
    lease_rows = repository.leases()
    for lease in lease_rows:
        expires_at = lease["expires_at"]
        comparable = expires_at
        if comparable is not None and comparable.tzinfo is not None:
            comparable = comparable.astimezone(timezone.utc).replace(tzinfo=None)
        if comparable is not None and comparable > now:
            current_leases.setdefault(lease["order_id"], lease)
        else:
            expired_lease_count += 1

    cases = []
    attention = []

    for order in orders:
        report = reports.get(order.id)
        ready = readiness_view(order, readiness.get(order.id))
        assignment = assignments.get(order.id)
        offers = pending_offers.get(order.id, [])
        lease = current_leases.get(order.id)
        order_status = _upper(order.status)
        report_status = _upper(
            getattr(report, "status", None),
            "UNREPORTED",
        )
        terminal = (
            order_status in TERMINAL_ORDER_STATUSES
            or report_status in TERMINAL_REPORT_STATUSES
        )

        reasons = []
        if not terminal:
            readiness_status = _upper(
                getattr(ready, "status", None),
                "NOT_CHECKED",
            )
            if readiness_status == "BLOCKED":
                reasons.append("READINESS_BLOCKED")
            elif readiness_status == "NOT_CHECKED":
                reasons.append("READINESS_NOT_CHECKED")
            if ready and getattr(ready, "missing_pacs", False):
                reasons.append("MISSING_PACS")
            if ready and getattr(ready, "incomplete_images", False):
                reasons.append("INCOMPLETE_IMAGES")
            if ready and getattr(ready, "missing_series", False):
                reasons.append("MISSING_SERIES")
            if ready and getattr(ready, "missing_history", False):
                reasons.append("MISSING_HISTORY")
            if assignment is None:
                reasons.append("UNASSIGNED")
            if offers:
                reasons.append("PENDING_OFFER")
            if lease:
                reasons.append("ACTIVE_EDITOR")

        item = {
            "order": order,
            "report": report,
            "readiness": ready,
            "assignment": assignment,
            "pending_offers": offers,
            "lease": lease,
            "terminal": terminal,
            "attention_reasons": reasons,
        }
        cases.append(item)
        if reasons:
            attention.append(item)

    review_required = repository.inbox("REVIEW_REQUIRED", limit)
    quarantined = repository.inbox("QUARANTINED", limit)
    active_exam_links = repository.active_links(limit)
    enabled_strategies = repository.strategies()

    recent_escalations = repository.recent_escalations()
    recent_pacs_events = repository.recent_pacs_events()

    open_cases = [item for item in cases if not item["terminal"]]
    metrics = {
        "open_cases": len(open_cases),
        "attention_cases": len(attention),
        "ready_cases": sum(
            1 for item in open_cases
            if _upper(
                getattr(item["readiness"], "status", None)
            ) == "READY"
        ),
        "blocked_cases": sum(
            1 for item in open_cases
            if _upper(
                getattr(item["readiness"], "status", None)
            ) == "BLOCKED"
        ),
        "unassigned_cases": sum(
            1 for item in open_cases
            if item["assignment"] is None
        ),
        "pending_offers": sum(
            len(item["pending_offers"])
            for item in open_cases
        ),
        "pacs_review": len(review_required),
        "pacs_quarantine": len(quarantined),
        "active_editors": len(current_leases),
        "expired_leases": expired_lease_count,
        "active_exam_links": len(active_exam_links),
        "enabled_strategies": len(enabled_strategies),
    }

    return {
        "generated_at": now,
        "metrics": metrics,
        "attention": attention,
        "cases": cases,
        "pacs_review": review_required,
        "pacs_quarantine": quarantined,
        "active_exam_links": active_exam_links,
        "enabled_strategies": enabled_strategies,
        "recent_escalations": recent_escalations,
        "recent_pacs_events": recent_pacs_events,
    }
