from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.py").read_text(encoding="utf-8")


def block(start, end):
    return APP.split(start, 1)[1].split(end, 1)[0]


def test_offer_engine_has_central_idempotency_guards():
    body = block("def offer_next_doctor(order,created_by=None):", "def expire_assignment_offers():")
    for marker in (
        "with_for_update()", "ALREADY_ASSIGNED", "ACTIVE_ASSIGNMENT_EXISTS",
        "PENDING_OFFER_EXISTS", "RETURNED_FOR_CORRECTION",
    ):
        assert marker in body


def test_coordinator_requires_completed_exam_and_images():
    body = block("def coordinate_post_exam_assignment(", "def expire_assignment_offers():")
    assert "EXAM_NOT_COMPLETED" in body
    assert "IMAGES_NOT_COMPLETE" in body
    assert "case_return_is_open" in body


def test_post_exam_triggers_use_coordinator():
    exam = block("def order_exam_status(order_id):", "def order_exam_status_override(order_id):")
    pacs = block("def pacs_tracking_refresh():", "def doctor_workspace():")
    assert "trigger='END_EXAM'" in exam
    assert "trigger='PACS_REFRESH'" in pacs


def test_return_clears_ownership_and_pending_offers():
    body = block("def return_case_to_workflow(order_id):", "def return_case_form(order_id):")
    assert "a.active=False" in body
    assert "offer.status='CANCELLED'" in body
    assert "o.assigned_doctor_id=None" in body


def test_resolution_rechecks_and_routes_correctly():
    body = block("def resolve_returned_case(event_id):", "def report_portal_download(order_id):")
    assert "evaluate_case_readiness(o)" in body
    assert "RESOLUTION_RECHECK_FAILED" in body
    assert "READY_FOR_REREVIEW" in body
    assert "RETURNED_TO_PREVIOUS_DOCTOR" in body
    assert "OUTSIDE_SPECIALTY" in body
    assert "trigger='RETURN_RESOLVED'" in body
