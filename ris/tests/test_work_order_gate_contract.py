from web.source_contract import get_source as _get_source
from web.source_contract import read_source as _read_source
import inspect
from pathlib import Path


def test_easy_registration_does_not_send_mwl_or_assign_doctor():
    import app as m
    source=_get_source(m.new_order)
    assert "ORDER_MWL_CREATE" not in source
    assert "ORDER_SMART_ASSIGNMENT" not in source
    assert "send_mwl(" not in source
    assert "offer_next_doctor(" not in source


def test_full_registration_does_not_send_mwl_or_assign_doctor():
    import app as m
    source=_get_source(m.schedule_unified_submit)
    assert "ORDER_MWL_CREATE" not in source
    assert "ORDER_SMART_ASSIGNMENT" not in source
    assert "send_mwl(" not in source


def test_appointment_checkin_creates_registered_order_without_mwl():
    import app as m
    source=_get_source(m.appointment_action)
    assert "status='REGISTERED'" in source
    assert "send_mwl(order)" not in source


def test_work_order_conversion_preserves_financial_gate():
    import app as m
    source=_get_source(m.convert_to_work_order)
    assert "order_balance(order) > 0.01" in source
    assert "order.device_id" in source
    assert "order.station_ae" in source


def test_work_order_records_pending_state_before_external_mwl_call():
    import app as m
    source=_get_source(m.convert_to_work_order)
    pending=source.index("order.status='MWL_PENDING'")
    first_commit=source.index("db.session.commit()",pending)
    send=source.index("send_mwl(order)")
    assert pending < first_commit < send


def test_work_order_closes_outbox_success_and_failure_states():
    import app as m
    source=_get_source(m.convert_to_work_order)
    assert "mwl_event.status='PROCESSED'" in source
    assert "mwl_event.status='FAILED'" in source
    assert "order.status='SCHEDULED'" in source
    assert "order.status='MWL_ERROR'" in source


def test_registered_and_pending_orders_cannot_use_resend():
    import app as m
    source=_get_source(m.resend_mwl)
    assert "current_status == 'REGISTERED'" in source
    assert "current_status == 'MWL_PENDING'" in source


def test_work_order_button_remains_permission_and_balance_gated():
    import app as m
    template=_read_source(Path(m.__file__).resolve().parent
        / "templates"
        / "order_detail.html", encoding="utf-8")
    assert "has_perm('orders.create')" in template
    assert "work_order_balance <= 0.01" in template
    assert "convert_to_work_order" in template
