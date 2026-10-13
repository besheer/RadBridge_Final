from web.source_contract import get_source as _get_source

def test_functional_routes():
    import app as m
    rules={r.rule for r in m.app.url_map.iter_rules()}
    assert {
      "/my/registration-style",
      "/admin/field-rules",
      "/studio",
      "/studio/templates/<template_type>",
      "/studio/templates/<int:template_id>/preview",
      "/receipts/<int:receipt_id>/studio-print",
      "/reports/<int:order_id>/word-template/<int:template_id>",
      "/patients/<int:patient_id>/alerts"
    } <= rules

def test_registration_helpers():
    import app as m
    assert callable(m.registration_style_for)
    assert callable(m.registration_template_for)
    assert callable(m.validate_registration_value)

def test_production_hotfixes_still_present():
    import app as m,inspect
    src=_get_source(m.device_booking_reason)
    assert "active=True" not in src
    sig=inspect.signature(m.device_booking_reason)
    assert sig.parameters["start_at"].default is None
    assert hasattr(m,"and_")
