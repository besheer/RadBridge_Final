from datetime import datetime, timedelta
import inspect


def _clear_booking_test_rows(m):
    m.BookingBlock.query.filter(
        m.BookingBlock.reason_code.like("LOCK_TEST_%")
    ).delete(synchronize_session=False)
    m.User.query.filter(
        m.User.username.like("booking_lock_test_%")
    ).delete(synchronize_session=False)
    m.Device.query.filter(
        m.Device.ae_title.like("LOCKTEST%")
    ).delete(synchronize_session=False)
    m.Procedure.query.filter(
        m.Procedure.code.like("LOCKTEST%")
    ).delete(synchronize_session=False)
    m.Branch.query.filter(
        m.Branch.code.like("LOCKTEST%")
    ).delete(synchronize_session=False)
    m.db.session.commit()


def _booking_entities(m):
    role = m.Role.query.filter_by(code="TECHNICIAN").first()
    branch = m.Branch(code="LOCKTEST_BRANCH", name="Booking Lock Test Branch", active=True)
    m.db.session.add(branch)
    m.db.session.flush()
    device = m.Device(
        branch_id=branch.id,
        name="Booking Lock Test Device",
        modality="DX",
        ae_title="LOCKTEST_AE",
        active=True,
        operational_status="ACTIVE",
        booking_enabled=True,
        workday_start="08:00",
        workday_end="22:00",
    )
    procedure = m.Procedure(
        code="LOCKTEST_PROC",
        name="Booking Lock Test Procedure",
        modality="DX",
        duration_min=20,
        active=True,
    )
    user = m.User(
        username="booking_lock_test_technician",
        full_name="Booking Lock Test Technician",
        password_hash="not-used",
        role_id=role.id,
        branch_id=branch.id,
        active=True,
    )
    m.db.session.add_all([device, procedure, user])
    m.db.session.commit()
    return branch, device, procedure, user


def test_device_block_still_blocks_booking(app_ctx):
    m = app_ctx
    _clear_booking_test_rows(m)
    branch, device, procedure, _ = _booking_entities(m)
    start_at = datetime(2035, 1, 10, 10, 0)
    try:
        m.db.session.add(m.BookingBlock(
            block_type="DEVICE",
            device_id=device.id,
            start_at=start_at,
            end_at=start_at + timedelta(hours=1),
            reason_code="LOCK_TEST_DEVICE",
            reason_text="Device unavailable",
            active=True,
        ))
        m.db.session.commit()
        assert m.booking_control_reason(
            branch, procedure, device, start_at,
            start_at + timedelta(minutes=20),
        ) == "Device unavailable"
    finally:
        _clear_booking_test_rows(m)


def test_staff_availability_block_does_not_block_patient_booking(app_ctx):
    m = app_ctx
    _clear_booking_test_rows(m)
    branch, device, procedure, user = _booking_entities(m)
    start_at = datetime(2035, 1, 10, 11, 0)
    try:
        m.db.session.add(m.BookingBlock(
            block_type="TECHNICIAN",
            user_id=user.id,
            start_at=start_at,
            end_at=start_at + timedelta(hours=1),
            reason_code="LOCK_TEST_TECHNICIAN",
            reason_text="Technician unavailable",
            active=True,
        ))
        m.db.session.commit()
        assert m.booking_control_reason(
            branch, procedure, device, start_at,
            start_at + timedelta(minutes=20),
        ) == ""
    finally:
        _clear_booking_test_rows(m)


def test_booking_block_scope_and_time_validation_contract(app_ctx):
    m = app_ctx
    assert callable(m.validate_booking_block_scope)
    start_at = datetime(2035, 1, 10, 12, 0)
    assert m.validate_booking_block_scope(
        block_type="DEVICE", device_id=None,
        start_at=start_at, end_at=start_at + timedelta(hours=1),
    )
    assert m.validate_booking_block_scope(
        block_type="DOCTOR", user_id=None,
        start_at=start_at, end_at=start_at + timedelta(hours=1),
    )
    assert m.validate_booking_block_scope(
        block_type="DEVICE", device_id=1,
        start_at=start_at, end_at=start_at,
    )
    assert m.validate_booking_block_scope(
        block_type="DEVICE", device_id=1,
        start_at=start_at, end_at=start_at + timedelta(hours=1),
    ) == ""


def test_atomic_booking_lock_contract(app_ctx):
    m = app_ctx
    assert callable(m.acquire_booking_slot_lock)
    assert "acquire_booking_slot_lock" in inspect.getsource(m.schedule_book)
    assert "acquire_booking_slot_lock" in inspect.getsource(m.appointment_reschedule)


def test_booking_control_template_has_safe_management_contract():
    from pathlib import Path
    template = (
        Path(__file__).resolve().parents[1]
        / "templates" / "admin_booking_control.html"
    ).read_text(encoding="utf-8")
    for expected in (
        'name="block_type"', 'name="start_at"', 'name="end_at"',
        'name="reason_text"', "Create Block",
    ):
        assert expected in template
    assert "active" in template.lower()
    assert "cancel" in template.lower() or "deactivate" in template.lower()
