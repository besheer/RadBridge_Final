
def test_i18n_helpers():
    import app as m
    assert callable(m.current_ui_language)
    assert callable(m.ui_text)
    assert callable(m.status_text)
    assert callable(m.seed_full_ui_dictionary)

def test_i18n_routes():
    import app as m
    rules={r.rule for r in m.app.url_map.iter_rules()}
    assert "/ui/language" in rules
    assert "/admin/dictionary/<int:entry_id>/reset" in rules

def test_dictionary_keys():
    import app as m
    keys={x[0] for x in m.DEFAULT_UI_DICTIONARY}
    for k in ["patient.name","exam.title","cashier.refund","booking.maintenance","status.SCHEDULED","status.FINAL"]:
        assert k in keys
