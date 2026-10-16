from web.source_contract import read_source as _read_source
from web.source_contract import get_source as _get_source
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
    source = _get_source(m.unassigned_cases)
    for field in ("branch_id", "specialty", "modality", "priority", "readiness", "sla", "q"):
        assert f"request.args.get('{field}'" in source
    assert "unassigned_case_snapshot" in source
    assert "allowed_registration_branches()" in source
    assert "branch_id not in allowed_branches" in source


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
    source = _get_source(app_ctx.assign_case)
    gate = source.index("assignment_readiness_decision(order)")
    mode = source.index("if mode=='auto'")
    assert gate < mode
    assert "if not readiness_decision['allowed']" in source
    assert "Resolve the readiness items first" in source


def test_unassigned_workspace_is_compact_responsive_and_theme_safe():
    template = _read_source(ROOT / "templates" / "unassigned_cases.html", encoding="utf-8")
    css = _read_source(ROOT / "static" / "app.css", encoding="utf-8")
    for marker in (
        'name="branch_id"', 'name="specialty"', 'name="modality"',
        'name="priority"', 'name="readiness"', 'name="sla"',
        "Manage Assignment",
        "rb-assignment-drawer", "popovertarget", "Open Resolution",
    ):
        assert marker in template
    assert template.count("rb-manage-assignment") == 1
    assert "reason!='LEGACY_READINESS'" in template
    assert "R8_UNASSIGNED_ASSIGNMENT_WORKSPACE_V1" in css
    assert "var(--rb-card" in css
    assert "var(--rb-text-main" in css
    assert "@media(max-width:720px)" in css


def test_branch_user_cannot_read_or_manually_assign_another_branch_case(app_ctx):
    import json
    from uuid import uuid4

    m=app_ctx
    suffix=uuid4().hex[:8].upper()
    own, _=_queue_order(m,suffix+'A')
    other, _=_queue_order(m,suffix+'B')
    own_branch=m.Branch.query.get(own.branch_id)
    role=m.Role(code='TEST_SCOPE_'+suffix,name='Synthetic branch scope',
                permissions_json=json.dumps(['reports.view','assignment.manage']))
    user=m.User(username='scope-'+suffix,full_name='Synthetic scoped user',
                password_hash='DISABLED-SYNTHETIC',role=role,branch_id=own.branch_id,active=True)
    m.db.session.add_all([role,user]);m.db.session.commit()
    client=m.app.test_client()
    with client.session_transaction() as state:state['uid']=user.id
    try:
        response=client.get('/assignment/unassigned')
        assert response.status_code==200
        assert own.accession.encode() in response.data
        assert other.accession.encode() not in response.data
        assert own_branch.name.encode() in response.data
        assert m.Branch.query.get(other.branch_id).name.encode() not in response.data
        assert client.get('/assignment/unassigned?branch_id=%s' % other.branch_id).status_code==403
        assert client.post('/orders/%s/assign' % other.id,data={'mode':'manual'}).status_code==403
    finally:
        m.db.session.rollback()
        for order in (own,other):
            m.CaseReadiness.query.filter_by(order_id=order.id).delete()
            m.Order.query.filter_by(id=order.id).delete()
            m.Patient.query.filter_by(id=order.patient_id).delete()
            m.Procedure.query.filter_by(id=order.procedure_id).delete()
            m.Branch.query.filter_by(id=order.branch_id).delete()
        m.User.query.filter_by(id=user.id).delete()
        m.Role.query.filter_by(id=role.id).delete()
        m.db.session.commit()
