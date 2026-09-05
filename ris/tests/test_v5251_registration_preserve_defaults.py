
def test_model_routes_and_preserve_helpers():
    import app as m, inspect
    assert hasattr(m,"RegistrationDefault")
    rules={r.rule for r in m.app.url_map.iter_rules()}
    assert "/my/registration-defaults" in rules
    assert "/admin/registration-defaults" in rules
    src=inspect.getsource(m.new_order)
    assert "registration_validation_error" in src
    assert "return redirect(url_for('new_order'))" not in src

def test_existing_regressions_preserved():
    import app as m,inspect
    assert "CaseReadiness=CaseReadiness" in inspect.getsource(m.advanced_search)
    assert "active=True" not in inspect.getsource(m.device_booking_reason)
    rules={r.rule for r in m.app.url_map.iter_rules()}
    for r in ["/admin/printer-profiles","/orders/<int:order_id>/print-center",
              "/doctor/case/<int:order_id>/workspace","/orders/<int:order_id>/attachments"]:
        assert r in rules

def test_templates_use_form_data_and_defaults():
    from pathlib import Path
    root=Path(__file__).parents[1]/"templates"
    for name in ("order_form.html","order_form_classic.html","order_form_compact.html"):
        s=(root/name).read_text()
        assert "form_data" in s
        assert "registration_defaults" in s
