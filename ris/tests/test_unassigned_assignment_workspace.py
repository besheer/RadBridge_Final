import inspect
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]


def _queue_order(m, suffix, *, readiness_status="READY", **flags):
    branch = m.Branch(code=f"Q{suffix}", name=f"Queue {suffix}", active=True)
    procedure = m.Procedure(
        code=f"QPROC{suffix}", name=f"Queue Procedure {suffix}",
        category="NEURO", modality="CT", active=True,
    )
    patient = m.Patient(
        patient_id=f"QP{suffix}", name=f"Queue Patient {suffix}",
    )
    m.db.session.add_all([branch, procedure, patient])
    m.db.session.flush()
    order = m.Order(
        accession=f"QACC{suffix}", patient_id=patient.id,
        procedure_id=procedure.id, procedure=procedure.name,
        branch_id=branch.id, modality="CT",
        scheduled=datetime.utcnow(), created_at=datetime.utcnow()-timedelta(minutes=9),
        priority="URGENT", status="REGISTERED",
    )
    m.db.session.add(order)
    m.db.session.flush()
    readiness = m.CaseReadiness(order_id=order.id, status=readiness_status)
    for field, value in flags.items():
        setattr(readiness, field, value)
    m.db.session.add(readiness)
    m.db.session.commit()
    return order, readiness


def test_unassigned_queue_route_and_filter_contract(app_ctx):
    m = app_ctx
    rule = next(x for x in m.app.url_map.iter_rules() if x.endpoint == "unassigned_cases")
    assert rule.rule == "/assignment/unassigned"
    source = inspect.getsource(m.unassigned_cases)
    for field in ("branch_id", "specialty", "modality", "priority", "readiness", "sla", "q"):
        assert f"request.args.get('{field}'" in source
    assert "unassigned_case_snapshot" in source


def test_queue_snapshot_exposes_waiting_sla_and_ready_state(app_ctx):
    m = app_ctx
    order, readiness = _queue_order(m, "READY")
    try:
        policy = SimpleNamespace(
            priority="URGENT", modality="CT", ready_to_assign_min=10,
        )
        row = m.unassigned_case_snapshot(order, readiness, [policy], datetime.utcnow())
        assert row["assignable"] is True
        assert row["readiness_status"] == "READY"
        assert row["sla"]["status"] == "NEAR_SLA"
        assert row["waiting_minutes"] >= 8
        assert row["specialty"] == "NEURO"
    finally:
        m.CaseReadiness.query.filter_by(order_id=order.id).delete()
        m.Order.query.filter_by(id=order.id).delete()
        m.Patient.query.filter_by(patient_id="QPREADY").delete()
        m.Procedure.query.filter_by(code="QPROCREADY").delete()
        m.Branch.query.filter_by(code="QREADY").delete()
        m.db.session.commit()


def test_queue_snapshot_maps_blocking_flags(app_ctx):
    m = app_ctx
    order, readiness = _queue_order(
        m, "BLOCK", readiness_status="BLOCKED",
        incomplete_images=True, missing_documents=True, missing_notes=True,
    )
    try:
        row = m.unassigned_case_snapshot(order, readiness, [], datetime.utcnow())
        codes = {item["code"] for item in row["flags"]}
        assert row["assignable"] is False
        assert {"MISSING_IMAGES", "MISSING_DOCUMENTS", "NOTES_REQUIRED"} <= codes
    finally:
        m.CaseReadiness.query.filter_by(order_id=order.id).delete()
        m.Order.query.filter_by(id=order.id).delete()
        m.Patient.query.filter_by(patient_id="QPBLOCK").delete()
        m.Procedure.query.filter_by(code="QPROCBLOCK").delete()
        m.Branch.query.filter_by(code="QBLOCK").delete()
        m.db.session.commit()


def test_manual_and_auto_assignment_share_readiness_gate(app_ctx):
    source = inspect.getsource(app_ctx.assign_case)
    gate = source.index("assignment_readiness_decision(order)")
    mode = source.index("if mode=='auto'")
    assert gate < mode
    assert "if not readiness_decision['allowed']" in source
    assert "Resolve the readiness items first" in source


def test_unassigned_workspace_is_compact_responsive_and_theme_safe():
    template = (ROOT / "templates" / "unassigned_cases.html").read_text(encoding="utf-8")
    css = (ROOT / "static" / "app.css").read_text(encoding="utf-8")
    for marker in (
        'name="branch_id"', 'name="specialty"', 'name="modality"',
        'name="priority"', 'name="readiness"', 'name="sla"',
        "Manage Assignment",
        "rb-assignment-drawer", "popovertarget", "Open Resolution",
    ):
        assert marker in template
    assert template.count("rb-manage-assignment") == 1
    assert "R8_UNASSIGNED_ASSIGNMENT_WORKSPACE_V1" in css
    assert "var(--rb-card" in css
    assert "var(--rb-text-main" in css
    assert "@media(max-width:720px)" in css
