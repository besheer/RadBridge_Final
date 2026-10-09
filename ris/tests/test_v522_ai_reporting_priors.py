
def test_v522_models():
    import app as m
    for n in ["AIProviderSetting","AIDraftReport","ExternalPriorStudy","PriorStudySelection"]:
        assert hasattr(m,n)

def test_v522_routes():
    import app as m
    rules={r.rule for r in m.app.url_map.iter_rules()}
    assert {"/admin/ai-reporting","/reports/<int:order_id>/ai-assistant",
            "/reports/<int:order_id>/ai-assistant/generate",
            "/reports/<int:order_id>/priors/select",
            "/patients/<int:patient_id>/external-priors"} <= rules

def test_ai_draft_is_not_finalizer():
    import app as m,inspect
    src=inspect.getsource(m.generate_ai_draft_payload)
    assert "Do not claim to have reviewed images" in src
    assert "Never finalize" in src

def test_booking_hotfixes_preserved():
    import app as m,inspect
    src=inspect.getsource(m.device_booking_reason)
    assert "active=True" not in src
    sig=inspect.signature(m.device_booking_reason)
    assert sig.parameters["start_at"].default is None
    assert hasattr(m,"and_")
