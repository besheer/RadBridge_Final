from datetime import datetime, timedelta
from types import SimpleNamespace


def _order(start_at, priority="ROUTINE"):
    return SimpleNamespace(
        priority=priority,
        exam_completed_at=start_at,
        scheduled=start_at,
    )


def _report(status, finalized_at):
    return SimpleNamespace(
        status=status,
        finalized_at=finalized_at,
        updated_at=finalized_at,
    )


def test_report_sla_stops_at_finalization(app_ctx):
    start_at = datetime(2026, 9, 20, 8, 0, 0)
    finalized_at = start_at + timedelta(minutes=45)
    now = start_at + timedelta(hours=8)

    snapshot = app_ctx.report_sla_snapshot(
        _order(start_at),
        _report("FINAL", finalized_at),
        now=now,
    )

    assert snapshot["is_final"] is True
    assert snapshot["end_at"] == finalized_at
    assert snapshot["elapsed_minutes"] == 45


def test_report_sla_normalizes_final_status(app_ctx):
    start_at = datetime(2026, 9, 20, 8, 0, 0)
    finalized_at = start_at + timedelta(minutes=30)

    snapshot = app_ctx.report_sla_snapshot(
        _order(start_at),
        _report(" final ", finalized_at),
        now=start_at + timedelta(hours=8),
    )

    assert snapshot["is_final"] is True
    assert snapshot["elapsed_minutes"] == 30


def test_finalized_at_is_authoritative_for_legacy_report(app_ctx):
    start_at = datetime(2026, 9, 20, 8, 0, 0)
    finalized_at = start_at + timedelta(minutes=25)

    snapshot = app_ctx.report_sla_snapshot(
        _order(start_at),
        _report("VERIFIED", finalized_at),
        now=start_at + timedelta(hours=8),
    )

    assert snapshot["is_final"] is True
    assert snapshot["end_at"] == finalized_at
    assert snapshot["elapsed_minutes"] == 25
