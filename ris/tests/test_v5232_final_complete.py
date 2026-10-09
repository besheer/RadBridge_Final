
def test_final_routes():
    import app as m
    rules={r.rule for r in m.app.url_map.iter_rules()}
    for r in ["/search/advanced","/orders/<int:order_id>/actions","/orders/<int:order_id>/label-print",
              "/admin/label-templates","/operations/assignment-dashboard","/operations/assignment-reports",
              "/operations/assignment-report.csv"]:
        assert r in rules

def test_previous_features_preserved():
    import app as m,inspect
    rules={r.rule for r in m.app.url_map.iter_rules()}
    for r in ["/reports/<int:order_id>/imaging-ai","/assignment/offers","/studio",
              "/operations/case-readiness","/operations/tat","/admin/communications"]:
        assert r in rules
    assert "active=True" not in inspect.getsource(m.device_booking_reason)
