
def test_models():
    import app as m
    for n in ['ClinicalNote','UserProfile','DictionaryEntry','RibbonAction','UserRibbonAction','BookingBlock']:
        assert hasattr(m,n)

def test_routes():
    import app as m
    rules={r.rule for r in m.app.url_map.iter_rules()}
    for r in ['/orders/<int:order_id>/clinical-notes','/my/profile','/admin/dictionary','/admin/booking-control']:
        assert r in rules
