from pathlib import Path

from workflow_engine import (
    derive_journey_stage,
    exam_transition_gate,
    report_source_allowed,
    resend_mwl_gate,
    work_order_gate,
)

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.py").read_text(encoding="utf-8")


def block(start, end):
    return APP.split(start, 1)[1].split(end, 1)[0]


def ready_work_order(**overrides):
    data = {
        "order_status": "REGISTERED",
        "balance": 0,
        "patient_id": "P00000004",
        "patient_dob": "19900101",
        "accession": "RB-UAT-1",
        "modality": "DX",
        "procedure": "Chest X-Ray PA",
        "device_id": 1,
        "station_ae": "RB_UAT_DX",
    }
    data.update(overrides)
    return work_order_gate(**data)


def test_work_order_requires_dob_for_strict_pacs_match():
    decision = ready_work_order(patient_dob="")
    assert not decision.allowed
    assert "PATIENT_DOB_REQUIRED_FOR_PACS_MATCH" in decision.blockers


def test_work_order_passes_only_when_all_canonical_prerequisites_pass():
    assert ready_work_order().allowed
    assert not ready_work_order(balance=1).allowed
    assert not ready_work_order(order_status="SCHEDULED").allowed
    assert not ready_work_order(station_ae="").allowed
    invalid_dob = ready_work_order(patient_dob="1990-01-01")
    assert not invalid_dob.allowed
    assert "PATIENT_DOB_INVALID_FOR_DICOM" in invalid_dob.blockers


def test_mwl_resend_is_recovery_only():
    assert resend_mwl_gate(order_status="SCHEDULED").allowed
    assert resend_mwl_gate(order_status="MWL_ERROR").allowed
    for status in ("REGISTERED", "MWL_PENDING", "IN_PROGRESS", "FINAL", "CANCELLED"):
        assert not resend_mwl_gate(order_status=status).allowed


def test_exam_start_requires_active_work_order():
    blocked = exam_transition_gate(
        role_code="TECHNICIAN",
        current_exam_status="ORDERED",
        target_exam_status="IN_PROGRESS",
        order_status="REGISTERED",
    )
    assert not blocked.allowed
    assert blocked.reason == "work_order_not_active"

    allowed = exam_transition_gate(
        role_code="TECHNICIAN",
        current_exam_status="ORDERED",
        target_exam_status="IN_PROGRESS",
        order_status="SCHEDULED",
    )
    assert allowed.allowed


def test_reporting_entry_requires_pacs_demographic_gate():
    blocked = exam_transition_gate(
        role_code="RADIOLOGIST",
        current_exam_status="EXAM_COMPLETED",
        target_exam_status="REPORTING",
        order_status="COMPLETED",
        pacs_gate_ok=False,
    )
    assert not blocked.allowed
    assert blocked.reason == "pacs_demographic_gate_required"

    allowed = exam_transition_gate(
        role_code="RADIOLOGIST",
        current_exam_status="EXAM_COMPLETED",
        target_exam_status="REPORTING",
        order_status="COMPLETED",
        pacs_gate_ok=True,
    )
    assert allowed.allowed


def test_journey_is_derived_from_domain_authorities():
    assert derive_journey_stage(
        order_status="REGISTERED", exam_status="ORDERED", pacs_status="WAITING"
    ) == "REGISTERED"
    assert derive_journey_stage(
        order_status="SCHEDULED", exam_status="ORDERED", pacs_status="WAITING"
    ) == "WAITING"
    assert derive_journey_stage(
        order_status="IN_PROGRESS", exam_status="IN_PROGRESS", pacs_status="WAITING"
    ) == "TECHNICIAN"
    assert derive_journey_stage(
        order_status="COMPLETED", exam_status="EXAM_COMPLETED", pacs_status="WAITING"
    ) == "EXAM_DONE"
    assert derive_journey_stage(
        order_status="COMPLETED", exam_status="EXAM_COMPLETED",
        pacs_status="IMAGES_COMPLETE", pacs_image_count=1,
    ) == "PACS_RECEIVED"
    assert derive_journey_stage(
        order_status="REPORTING", exam_status="REPORTING",
        pacs_status="IMAGES_COMPLETE", pacs_image_count=1, report_status="DRAFT",
    ) == "REPORTING"
    assert derive_journey_stage(
        order_status="FINAL", exam_status="REPORTING",
        pacs_status="IMAGES_COMPLETE", pacs_image_count=1, report_status="FINAL",
    ) == "FINALIZED"


def test_report_source_is_final_only():
    assert report_source_allowed("FINAL")
    for status in ("UNREPORTED", "DRAFT", "VERIFIED", "READY_APPROVAL"):
        assert not report_source_allowed(status)


def test_direct_workflow_status_route_is_projection_only():
    body = block("def order_workflow_status(order_id):", "@app.route('/appointments'")
    assert "canonical_display_state(" in body
    assert "order.status=" not in body
    assert "order.workflow_status=" not in body
    assert "db.session.commit()" not in body
    decorator = APP.split("def order_workflow_status(order_id):", 1)[0][-200:]
    assert "@require_perm('orders.status')" in decorator


def test_patient_journey_route_cannot_write_stage():
    body = block("def order_journey_stage(order_id,stage):", "@app.get('/operations/booking-board')")
    assert "journey_snapshot(o)['stage']" in body
    assert "ensure_journey(" not in body
    assert "db.session.commit()" not in body
    decorator = APP.split("def order_journey_stage(order_id,stage):", 1)[0][-200:]
    assert "@require_perm('workflow.override')" in decorator


def test_pacs_tracking_get_has_no_refresh_side_effect():
    body = block("def pacs_tracking():", "@app.post('/pacs/tracking/refresh')")
    assert "pacs_lookup_order(" not in body
    assert "db.session.commit()" not in body


def test_key_routes_delegate_to_canonical_engine():
    work = block("def convert_to_work_order(order_id):", "def resend_mwl(order_id):")
    exam = block("def order_exam_status(order_id):", "def order_exam_status_override(order_id):")
    resend = block("def resend_mwl(order_id):", "def add_payment(order_id):")
    assert "work_order_gate(" in work
    assert "_apply_exam_transition(" in exam
    assert "resend_mwl_gate(" in resend


def test_report_source_route_enforces_final_only():
    body = block("def report_source(order_id):", "@app.route('/attachments/upload'")
    assert "report_source_allowed(report.status)" in body
    assert "abort(409" in body


def test_journey_template_has_no_manual_stage_buttons():
    template = (ROOT / "templates" / "operations_journey.html").read_text(encoding="utf-8")
    assert "order_journey_stage" not in template
    assert "Derived from clinical state" in template


def test_order_detail_separates_exam_and_report_domains():
    template = (ROOT / "templates" / "order_detail.html").read_text(encoding="utf-8")
    assert "<b>Report:</b>" in template
    assert "work_order_gate.allowed" in template
    assert "['BOOKED','ORDERED','IN_PROGRESS','EXAM_COMPLETED','REPORTING']" in template
