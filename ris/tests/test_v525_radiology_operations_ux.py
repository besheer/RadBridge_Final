
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
    assert "CaseReadiness=CaseReadiness" in inspect.getsource(m.advanced_search)
    assert "active=True" not in inspect.getsource(m.device_booking_reason)

def test_command_bar_and_dictation_templates():
    from pathlib import Path
    root=Path(__file__).parents[1]/"templates"
    actions=(root/"order_actions.html").read_text()
    for x in ["Receipt","Sticker","Print","Documents","PACS / AI","Report"]:
        assert x in actions
    report=(root/"report_editor.html").read_text()
    assert "radiology-dictation-controls" in report
    assert "SpeechRecognition" in report
