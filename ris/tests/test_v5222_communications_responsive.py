
def test_communication_models():
    import app as m
    for n in ["CommunicationChannelSetting","CommunicationTemplate","PatientCommunication"]:
        assert hasattr(m,n)

def test_communication_routes():
    import app as m
    rules={r.rule for r in m.app.url_map.iter_rules()}
    assert {
      "/admin/communications",
      "/admin/communication-templates",
      "/patients/<int:patient_id>/communications",
      "/communications/<int:comm_id>/retry"
    } <= rules

def test_studio_visibility_routes_preserved():
    import app as m
    rules={r.rule for r in m.app.url_map.iter_rules()}
    assert "/studio" in rules
    assert "/studio/templates/<template_type>" in rules
    assert "/admin/field-rules" in rules
    assert "/admin/company-legal" in rules
    assert "/admin/ai-reporting" in rules

def test_ai_and_priors_preserved():
    import app as m
    rules={r.rule for r in m.app.url_map.iter_rules()}
    assert "/reports/<int:order_id>/ai-assistant" in rules
    assert "/patients/<int:patient_id>/external-priors" in rules

def test_booking_hotfixes_preserved():
    import app as m,inspect
    src=inspect.getsource(m.device_booking_reason)
    assert "active=True" not in src
    sig=inspect.signature(m.device_booking_reason)
    assert sig.parameters["start_at"].default is None
    assert hasattr(m,"and_")
