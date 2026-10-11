from web.source_contract import read_source as _read_source
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP = _read_source(ROOT / "app.py", encoding="utf-8")
SERVICE = "\n".join((ROOT / path).read_text(encoding="utf-8") for path in (
    "web/compatibility/case_operations_dashboard_service.py",
    "application/services/readiness/operations_snapshot.py",
    "infrastructure/adapters/readiness/snapshot_repository.py"))
BASE = _read_source(ROOT / "templates" / "base.html", encoding="utf-8")
TEMPLATE = _read_source(ROOT / "templates" / "case_operations_control_center.html", encoding="utf-8")


def test_control_center_route_is_read_only_get():
    assert APP.count(
        "@app.get('/operations/case-control-center')"
    ) == 1
    assert APP.count("def case_operations_control_center():") == 1
    assert "@require_perm('orders.view')\ndef case_operations_control_center" in APP


def test_dashboard_service_contains_no_mutation_or_commit():
    forbidden = (
        ".commit(",
        ".flush(",
        ".add(",
        ".delete(",
        "UPDATE ",
        "INSERT ",
        "DELETE FROM",
    )
    for token in forbidden:
        assert token not in SERVICE


def test_navigation_has_one_control_center_link():
    assert BASE.count("url_for('case_operations_control_center')") == 1


def test_template_reuses_existing_workflow_routes():
    for endpoint in (
        "assignment_dashboard",
        "case_readiness_dashboard",
        "pacs_reconciliation",
        "admin_assignment_strategies",
        "admin_assignment",
        "unassigned_cases",
        "escalation_board",
        "admin_audit",
        "admin_qa_control",
    ):
        assert f"url_for('{endpoint}')" in TEMPLATE


def test_template_has_guidance_and_no_mutating_forms():
    assert TEMPLATE.count("action_info(") >= 3
    assert "method=\"post\"" not in TEMPLATE.lower()
    assert "<form" not in TEMPLATE.lower()

