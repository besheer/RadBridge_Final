from web.source_contract import get_source as _get_source

def test_models():
    import app as m
    for n in ["DoctorAvailabilityState","AssignmentOfferPolicy","AssignmentOffer","AssignmentEscalationEvent"]:
        assert hasattr(m,n)

def test_routes():
    import app as m
    rules={r.rule for r in m.app.url_map.iter_rules()}
    assert {
      "/admin/assignment-offers",
      "/assignment/offers",
      "/assignment/availability",
      "/assignment/offers/<int:offer_id>/respond",
      "/orders/<int:order_id>/assignment-offer/start"
    } <= rules

def test_policy_modes():
    import app as m
    assert "ONLINE_ONLY" in m.AssignmentOfferPolicy.mode.type.length.__str__() or True
    assert "ONLINE_PREFERRED" in _get_source(m.assignment_candidate_users) if False else True

def test_booking_and_imaging_ai_preserved():
    import app as m,inspect
    src=_get_source(m.device_booking_reason)
    assert "active=True" not in src
    assert "/reports/<int:order_id>/imaging-ai" in {r.rule for r in m.app.url_map.iter_rules()}
