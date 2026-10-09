
def test_multi_attachment_registration_backend():
    import app as m,inspect
    src=inspect.getsource(m.new_order)
    assert "request.files.getlist('attachment_files')" in src
    assert "request.form.getlist('attachment_categories')" in src
    assert "request.form.getlist('attachment_notes')" in src

def test_attachment_routes():
    import app as m
    rules={r.rule for r in m.app.url_map.iter_rules()}
    assert "/attachments/upload" in rules
    assert "/attachments/<int:attachment_id>" in rules
    assert "/attachments/<int:attachment_id>/preview" in rules
    assert "/attachments/<int:attachment_id>/delete" in rules

def test_previous_stable_features_preserved():
    import app as m,inspect
    rules={r.rule for r in m.app.url_map.iter_rules()}
    for r in ["/intake/smart","/search/advanced","/operations/assignment-dashboard",
              "/operations/case-readiness","/reports/<int:order_id>/imaging-ai",
              "/assignment/offers","/studio","/admin/communications"]:
        assert r in rules
    assert "CaseReadiness=CaseReadiness" in inspect.getsource(m.advanced_search)
    assert "active=True" not in inspect.getsource(m.device_booking_reason)
