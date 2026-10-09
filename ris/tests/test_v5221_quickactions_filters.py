
def test_v5221_routes():
    import app as m
    rules={r.rule for r in m.app.url_map.iter_rules()}
    assert {"/my/quick-actions","/search","/studio","/admin/ai-reporting"} <= rules

def test_role_presets_exist():
    import app as m
    for role in ["RECEPTION","CASHIER","TECHNICIAN","NURSING","DOCTOR","MANAGEMENT"]:
        assert role in m.ROLE_QUICK_ACTION_PRESETS
        assert len(m.ROLE_QUICK_ACTION_PRESETS[role]) >= 4

def test_ai_studio_priors_preserved():
    import app as m
    rules={r.rule for r in m.app.url_map.iter_rules()}
    assert "/studio/templates/<template_type>" in rules
    assert "/reports/<int:order_id>/ai-assistant" in rules
    assert "/patients/<int:patient_id>/external-priors" in rules

def test_booking_hotfixes_preserved():
    import app as m,inspect
    src=inspect.getsource(m.device_booking_reason)
    assert "active=True" not in src
    sig=inspect.signature(m.device_booking_reason)
    assert sig.parameters["start_at"].default is None
    assert hasattr(m,"and_")
