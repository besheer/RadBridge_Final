
def test_v520_models():
    import app as m
    for n in ["PatientDocument","DocumentMatch","TelephonyExtension","CallLog"]:
        assert hasattr(m,n)
def test_v520_routes():
    import app as m
    rules={r.rule for r in m.app.url_map.iter_rules()}
    required={"/patients/<int:patient_id>/documents","/patients/<int:patient_id>/timeline",
    "/documents/<int:document_id>/review","/api/telephony/incoming","/telephony/calls",
    "/telephony/caller/<int:call_id>"}
    assert required <= rules
def test_v519_routes_preserved():
    import app as m
    rules={r.rule for r in m.app.url_map.iter_rules()}
    assert {"/operations/journey","/operations/booking-board","/operations/dashboard","/chat"} <= rules
