
def test_booking_v2_routes_present():
    import app as m
    rules={r.rule for r in m.app.url_map.iter_rules()}
    assert "/schedule/v2" in rules
    assert "/schedule/v2/book" in rules
    assert "/devices/<int:device_id>/booking-status" in rules

def test_device_booking_helpers():
    import app as m
    assert callable(m.device_booking_reason)
    assert callable(m.device_available_for_booking)
    assert callable(m.booking_v2_slots)

def test_device_statuses():
    import app as m
    for x in ["ACTIVE","OUT_OF_SERVICE","MAINTENANCE","DISABLED"]:
        assert x in m.DEVICE_BOOKING_STATUSES

def test_booking_v2_template_is_backend_link_based():
    from pathlib import Path
    root=Path(__file__).resolve().parents[1]
    s=(root/"templates"/"schedule_v2.html").read_text(encoding="utf-8")
    assert "schedule_v2_book_form" in s
    assert "Book Slot" in s
