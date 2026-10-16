from web.source_contract import get_source as _get_source

def test_advanced_search_context_and_route():
    import app as m, inspect
    rules={r.rule for r in m.app.url_map.iter_rules()}
    assert "/search/advanced" in rules
    src=_get_source(m.advanced_search)
    assert "CaseReadiness=CaseReadiness" in src
    assert "CaseAssignment=CaseAssignment" in src
    assert "Report=Report" in src

def test_core_feature_routes_preserved():
    import app as m
    rules={r.rule for r in m.app.url_map.iter_rules()}
    required={
      "/intake/smart",
      "/admin/ocr-settings",
      "/operations/assignment-dashboard",
      "/operations/assignment-reports",
      "/operations/case-readiness",
      "/operations/tat",
      "/reports/<int:order_id>/imaging-ai",
      "/assignment/offers",
      "/studio",
      "/admin/communications",
      "/orders/<int:order_id>/actions",
      "/admin/label-templates",
    }
    assert required <= rules

def test_booking_hotfixes_preserved():
    import app as m,inspect
    src=_get_source(m.device_booking_reason)
    assert "active=True" not in src
    sig=inspect.signature(m.device_booking_reason)
    assert sig.parameters["start_at"].default is None
    assert sig.parameters["end_at"].default is None
    assert hasattr(m,"and_")
