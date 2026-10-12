from web.source_contract import read_source as _read_source
from web.source_contract import get_source as _get_source
from datetime import datetime, timedelta
from pathlib import Path
import importlib.util
import inspect

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations


ROOT = Path(__file__).resolve().parents[1]


def _entities(m):
    role = m.Role.query.filter_by(code="SUPER_ADMIN").first()
    user = m.User.query.filter_by(username="calendar_contract_admin").first()
    if not user:
        user = m.User(
            username="calendar_contract_admin",
            full_name="Calendar Contract Admin",
            password_hash="not-used",
            role_id=role.id,
            active=True,
        )
        m.db.session.add(user)
    branch = m.Branch.query.filter_by(code="CALCONTRACT").first()
    if not branch:
        branch = m.Branch(code="CALCONTRACT", name="Calendar Contract", active=True)
        m.db.session.add(branch)
        m.db.session.flush()
    device = m.Device.query.filter_by(ae_title="CALCONTRACT_AE").first()
    if not device:
        device = m.Device(
            branch_id=branch.id,
            name="Calendar Contract CT",
            modality="CT",
            ae_title="CALCONTRACT_AE",
            active=True,
            operational_status="ACTIVE",
            booking_enabled=True,
            workday_start="08:00",
            workday_end="22:00",
        )
        m.db.session.add(device)
    procedure = m.Procedure.query.filter_by(code="CALCONTRACT_PROC").first()
    if not procedure:
        procedure = m.Procedure(
            code="CALCONTRACT_PROC",
            name="Calendar Contract CT",
            modality="CT",
            duration_min=35,
            active=True,
        )
        m.db.session.add(procedure)
    patient = m.Patient.query.filter_by(patient_id="CALCONTRACT_PAT").first()
    if not patient:
        patient = m.Patient(
            patient_id="CALCONTRACT_PAT",
            name="Calendar Contract Patient",
            dob_estimated=False,
        )
        m.db.session.add(patient)
    m.db.session.commit()
    return user, branch, device, procedure, patient


def test_register_creates_linked_calendar_appointment_and_uses_lock(app_ctx, monkeypatch):
    m = app_ctx
    user, branch, device, procedure, patient = _entities(m)
    scheduled = datetime(2036, 2, 3, 10, 0)
    m.Appointment.query.filter_by(
        patient_id=patient.id,
        procedure_id=procedure.id,
        scheduled=scheduled,
    ).delete(synchronize_session=False)
    existing_orders = m.Order.query.filter_by(
        patient_id=patient.id,
        procedure_id=procedure.id,
        scheduled=scheduled,
    ).all()
    for order in existing_orders:
        m.db.session.delete(order)
    m.db.session.commit()

    lock_calls = []
    monkeypatch.setattr(m, "acquire_booking_slot_lock", lambda device_id, start: lock_calls.append((device_id, start)))
    monkeypatch.setattr(m, "new_accession", lambda: "CALCONTRACT_ACC")
    monkeypatch.setattr(m, "price_order", lambda *args: (100.0, 100.0, 100.0, 0.0, None))
    monkeypatch.setattr(m, "audit", lambda *args, **kwargs: None)
    monkeypatch.setattr(m, "ensure_journey", lambda *args, **kwargs: None)
    monkeypatch.setattr(m, "enqueue_event", lambda *args, **kwargs: None)
    monkeypatch.setattr(m, "send_mwl", lambda order: None)

    with m.app.test_client() as client:
        with client.session_transaction() as session:
            session["uid"] = user.id
        response = client.post(
            "/schedule/unified-submit",
            data={
                "registration_action": "REGISTER",
                "scheduled": scheduled.isoformat(),
                "branch_id": str(branch.id),
                "device_id": str(device.id),
                "procedure_ids": str(procedure.id),
                "patient_mode": "existing",
                "patient_id": str(patient.id),
                "priority": "ROUTINE",
            },
        )

    assert response.status_code == 302
    order = m.Order.query.filter_by(accession="CALCONTRACT_ACC").one()
    appointment = m.Appointment.query.filter_by(order_id=order.id).one()
    assert appointment.patient_id == patient.id
    assert appointment.device_id == device.id
    assert appointment.scheduled == scheduled
    assert appointment.duration_min == 35
    assert appointment.status == "REGISTERED"
    assert lock_calls == [(device.id, scheduled)]


def test_calendar_cells_cover_full_duration_and_free_cancelled_slots(app_ctx):
    m = app_ctx
    _, branch, device, procedure, patient = _entities(m)
    start = datetime(2036, 2, 3, 10, 0)
    appointment = m.Appointment(
        patient_id=patient.id,
        branch_id=branch.id,
        procedure_id=procedure.id,
        device_id=device.id,
        scheduled=start,
        duration_min=35,
        status="REGISTERED",
    )
    slots = [start + timedelta(minutes=15 * value) for value in range(4)]
    cells = m.build_calendar_cells([appointment], slots)
    assert cells[f"{device.id}|{slots[0].isoformat()}"]["starts"] == [appointment]
    assert cells[f"{device.id}|{slots[1].isoformat()}"]["occupied"] is True
    assert cells[f"{device.id}|{slots[2].isoformat()}"]["occupied"] is True
    assert f"{device.id}|{slots[3].isoformat()}" not in cells
    appointment.status = "CANCELLED"
    assert m.build_calendar_cells([appointment], slots) == {}


def test_appointment_order_model_and_migration_contract(app_ctx):
    m = app_ctx
    assert hasattr(m.Appointment, "order_id")
    assert hasattr(m.Order, "appointment")
    migration_path = ROOT / "migrations" / "versions" / "20260908_002_appointment_order_link.py"
    source = _read_source(migration_path, encoding="utf-8")
    assert 'down_revision = "20260908_001"' in source
    assert "uq_appointment_order_id" in source
    assert "fk_appointment_order_id_order" in source
    assert "ORDER_BACKFILL" in source

    spec = importlib.util.spec_from_file_location("appointment_order_migration", migration_path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = sa.create_engine("sqlite:///:memory:")
    with engine.begin() as connection:
        connection.execute(sa.text('CREATE TABLE "order" (id INTEGER PRIMARY KEY)'))
        connection.execute(sa.text("CREATE TABLE appointment (id INTEGER PRIMARY KEY)"))
        migration.op = Operations(MigrationContext.configure(connection))
        migration.upgrade()
        columns = {item["name"] for item in sa.inspect(connection).get_columns("appointment")}
        assert "order_id" in columns
        migration.downgrade()
        columns = {item["name"] for item in sa.inspect(connection).get_columns("appointment")}
        assert "order_id" not in columns


def test_calendar_and_unified_registration_source_contract(app_ctx):
    m = app_ctx
    unified_source = _get_source(m.schedule_unified_submit)
    assert "acquire_booking_slot_lock" in unified_source
    assert "order_id=o.id" in unified_source
    template = _read_source(ROOT / "templates" / "schedule_calendar.html", encoding="utf-8")
    assert "calendar_cells" in template
    assert "rb-occupied-tail" in template
    assert "order_detail" in template


def test_action_guidance_is_top_layer_responsive_and_theme_safe():
    macro = _read_source(ROOT / "templates" / "_action_guidance.html", encoding="utf-8")
    css = _read_source(ROOT / "static" / "app.css", encoding="utf-8")
    javascript = _read_source(ROOT / "static" / "action-guidance.js", encoding="utf-8")
    base = _read_source(ROOT / "templates" / "base.html", encoding="utf-8")
    page = _read_source(ROOT / "templates" / "unassigned_cases.html", encoding="utf-8")
    assert "popover" in macro
    assert "<details" not in macro
    assert "popovertarget" in javascript
    assert "hidePopover" in javascript
    assert "action-guidance.js" in base
    assert "rb-guidance-popover::backdrop" in css
    assert "var(--rb-card" in css
    assert "var(--rb-text-main" in css
    assert "@media(max-width:640px)" in css
    assert "التعيين اليدوي" in page
    assert "التعيين التلقائي" in page
