from web.source_contract import get_source as _get_source

import inspect

def test_deviceblock_query_does_not_use_missing_active_column():
    import app as m
    src = _get_source(m.device_booking_reason)
    assert "DeviceBlock.query.filter_by(device_id=device.id,active=True)" not in src
    assert "DeviceBlock.query.filter_by(device_id=device.id).all()" in src

def test_device_booking_reason_accepts_schedule_v2_call_style():
    import app as m
    sig = inspect.signature(m.device_booking_reason)
    assert sig.parameters["start_at"].default is None
    assert sig.parameters["end_at"].default is None

def test_and_is_imported_for_booking_board():
    import app as m
    assert hasattr(m, "and_")

def test_critical_routes_preserved():
    import app as m
    rules={r.rule for r in m.app.url_map.iter_rules()}
    required={
      "/orders/new","/cashier","/schedule/v2",
      "/operations/booking-board","/operations/dashboard",
      "/pacs/tracking","/pacs/reconciliation",
      "/chat","/telephony/calls","/admin/field-rules",
      "/studio","/doctor/templates"
    }
    assert required <= rules
