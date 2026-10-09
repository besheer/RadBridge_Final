
def test_generated_attachment_names():
    import app as m
    a=m.generated_attachment_filename(100,"PRESCRIPTION","same.jpg")
    b=m.generated_attachment_filename(100,"PRESCRIPTION","same.jpg")
    assert a.startswith("ATT_100_PRESCRIPTION_")
    assert a.endswith(".jpg")
    assert a != b
    assert "same" not in a

def test_golden_routes_and_hotfixes():
    import app as m, inspect
    rules={r.rule for r in m.app.url_map.iter_rules()}
    assert "/orders/<int:order_id>/attachments" in rules
    assert "/attachments/<int:attachment_id>/preview" in rules
    assert "/attachments/<int:attachment_id>/delete" in rules
    assert "/search/advanced" in rules
    assert "CaseReadiness=CaseReadiness" in inspect.getsource(m.advanced_search)
    assert "active=True" not in inspect.getsource(m.device_booking_reason)

def test_both_registration_styles_keep_multi_attachment():
    from pathlib import Path
    root=Path(__file__).parents[1]/"templates"
    for name in ("order_form.html","order_form_classic.html"):
        s=(root/name).read_text()
        assert "addAttachmentRow" in s
        assert "attachment_files" in s
        assert "attachment_categories" in s
