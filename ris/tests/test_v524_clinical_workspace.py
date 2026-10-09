
def test_models():
    import app as m
    for n in ["ClinicalAssessment","VitalSign","ClinicalDiagnosis","ClinicalMedication","ClinicalLabItem"]:
        assert hasattr(m,n)

def test_route():
    import app as m
    rules={r.rule for r in m.app.url_map.iter_rules()}
    assert "/doctor/case/<int:order_id>/workspace" in rules

def test_golden_features_preserved():
    import app as m,inspect
    rules={r.rule for r in m.app.url_map.iter_rules()}
    for r in ["/search/advanced","/orders/<int:order_id>/attachments","/operations/assignment-dashboard",
              "/reports/<int:order_id>/imaging-ai","/assignment/offers","/studio"]:
        assert r in rules
    assert "CaseReadiness=CaseReadiness" in inspect.getsource(m.advanced_search)
    assert "active=True" not in inspect.getsource(m.device_booking_reason)
