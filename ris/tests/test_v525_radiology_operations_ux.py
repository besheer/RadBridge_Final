from web.source_contract import read_source as _read_source
from web.source_contract import get_source as _get_source

def test_v525_routes_and_golden_regression():
    import app as m, inspect
    rules={r.rule for r in m.app.url_map.iter_rules()}
    required=[
      "/admin/printer-profiles",
      "/orders/<int:order_id>/print-center",
      "/orders/<int:order_id>/actions",
      "/search/advanced",
      "/orders/<int:order_id>/attachments",
      "/doctor/case/<int:order_id>/workspace",
      "/operations/assignment-dashboard",
      "/reports/<int:order_id>/imaging-ai",
      "/assignment/offers",
      "/studio",
    ]
    for r in required: assert r in rules
    assert hasattr(m,"PrinterProfile")
    assert hasattr(m,"order_visual_state")
    assert "CaseReadiness=CaseReadiness" in _get_source(m.advanced_search)
    assert "active=True" not in _get_source(m.device_booking_reason)

def test_command_bar_and_dictation_templates():
    from pathlib import Path
    root=Path(__file__).parents[1]/"templates"
    actions=_read_source(root/"order_actions.html")
    for x in ["Receipt","Sticker","Print","Documents","PACS / AI","Report"]:
        assert x in actions
    report=_read_source(root/"report_editor.html")
    assert "radiology-dictation-controls" in report
    assert "SpeechRecognition" in report
