
def test_procedure_branch_model():
    import app as m
    assert hasattr(m,"ProcedureBranch")

def test_booking_restriction_helpers():
    import app as m
    assert callable(m.procedure_available_in_branch)
    assert callable(m.allowed_procedures_for_branch)
    assert callable(m.booking_restriction_reason)

def test_booking_availability_routes():
    import app as m
    rules={r.rule for r in m.app.url_map.iter_rules()}
    assert "/admin/booking-availability" in rules
    assert "/admin/booking-availability/seed" in rules
    assert "/api/booking/procedures" in rules

def test_booking_v2_submit_uses_central_restriction():
    import app as m, inspect
    src=inspect.getsource(m.schedule_v2_book_submit)
    assert "booking_restriction_reason" in src
