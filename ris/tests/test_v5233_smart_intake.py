from web.source_contract import get_source as _get_source

def test_models():
    import app as m
    for n in ["SmartIntakeSession","SmartIntakeDocument","OCRProviderSetting"]:
        assert hasattr(m,n)

def test_routes():
    import app as m
    rules={r.rule for r in m.app.url_map.iter_rules()}
    for r in ["/intake/smart","/intake/smart/<int:intake_id>",
              "/intake/smart/<int:intake_id>/upload",
              "/intake/smart/<int:intake_id>/ocr-all",
              "/admin/ocr-settings"]:
        assert r in rules

def test_previous_features_preserved():
    import app as m,inspect
    rules={r.rule for r in m.app.url_map.iter_rules()}
    for r in ["/search/advanced","/operations/assignment-dashboard",
              "/operations/case-readiness","/reports/<int:order_id>/imaging-ai",
              "/assignment/offers","/studio","/admin/communications"]:
        assert r in rules
    assert "active=True" not in _get_source(m.device_booking_reason)
