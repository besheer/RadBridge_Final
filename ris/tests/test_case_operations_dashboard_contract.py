from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.py").read_text(encoding="utf-8")
SERVICE = (
    ROOT / "case_operations_dashboard_service.py"
).read_text(encoding="utf-8")
BASE = (ROOT / "templates" / "base.html").read_text(
    encoding="utf-8"
)
TEMPLATE = (
    ROOT / "templates" / "case_operations_control_center.html"
).read_text(encoding="utf-8")


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

