from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "templates"


def text(name):
    return (TEMPLATES / name).read_text(encoding="utf-8")


def test_guidance_macro_is_bilingual_and_backward_compatible():
    source = text("_action_guidance.html")
    assert "lang='en'" in source
    assert "متى يُستخدم:" in source
    assert "المتطلبات:" in source
    assert "التأثير:" in source
    assert "تحذير:" in source


def test_assignment_batch_has_action_guidance():
    minimums = {
        "unassigned_cases.html": 2,
        "my_assignment_offers.html": 2,
        "admin_assignment_offers.html": 2,
        "admin_assignment.html": 1,
        "admin_assignment_strategies.html": 4,
        "open_pool_cases.html": 1,
        "doctor_workspace.html": 3,
    }
    for name, minimum in minimums.items():
        source = text(name)
        assert 'from "_action_guidance.html" import action_info' in source
        assert source.count("action_info(") >= minimum
        assert "ui_lang" in source


def test_clinical_and_pacs_guidance_is_present():
    minimums = {
        "ai_report_assistant.html": 4,
        "pacs_reconciliation.html": 5,
        "case_operations_control_center.html": 3,
    }
    for name, minimum in minimums.items():
        source = text(name)
        assert source.count("action_info(") >= minimum
        assert "ui_lang" in source


def test_guidance_templates_do_not_define_backend_routes():
    names = [
        "_action_guidance.html", "unassigned_cases.html",
        "my_assignment_offers.html", "admin_assignment_offers.html",
        "admin_assignment.html", "admin_assignment_strategies.html",
        "open_pool_cases.html", "doctor_workspace.html",
        "ai_report_assistant.html", "pacs_reconciliation.html",
        "case_operations_control_center.html",
    ]
    for name in names:
        source = text(name)
        assert "@app.route" not in source
        assert "@app.post" not in source
