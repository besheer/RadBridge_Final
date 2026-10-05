"""Regression coverage for exam-state validation and DICOM calendar dates."""
from types import SimpleNamespace

import pytest
import app as m
from workflow_engine import can_transition, exam_transition_gate, normalize_state, work_order_gate

ROLES = ("SUPER_ADMIN", "SUPERVISOR", "RECEPTION", "NURSING", "TECHNICIAN", "RADIOLOGIST", "FINANCE", "SERVICE")
INVALID_TARGETS = ("FINAL", "VERIFIED", "UNKNOWN", "", None)


@pytest.mark.parametrize("role", ROLES)
@pytest.mark.parametrize("override", (False, True))
@pytest.mark.parametrize("target", INVALID_TARGETS)
def test_invalid_targets_are_denied_for_every_role(role, override, target):
    direct = can_transition(role, "BOOKED", target, override=override)
    gated = exam_transition_gate(
        role_code=role, current_exam_status="BOOKED", target_exam_status=target,
        order_status="SCHEDULED", override=override, pacs_gate_ok=True,
    )
    assert not direct.allowed
    assert not gated.allowed
    assert direct.reason == gated.reason == "invalid_target_exam_state"


@pytest.mark.parametrize("current", ("FINAL", "VERIFIED", "UNKNOWN"))
@pytest.mark.parametrize("override", (False, True))
def test_invalid_current_state_cannot_be_reopened_as_an_exam(current, override):
    decision = exam_transition_gate(
        role_code="SUPER_ADMIN", current_exam_status=current,
        target_exam_status="IN_PROGRESS", order_status="SCHEDULED", override=override,
    )
    assert not decision.allowed
    assert decision.reason == "invalid_current_exam_state"


@pytest.mark.parametrize("target", INVALID_TARGETS)
@pytest.mark.parametrize("override", (False, True))
def test_application_rejects_invalid_target_without_mutating_order(target, override):
    order = SimpleNamespace(status="SCHEDULED", exam_status="BOOKED")
    before = vars(order).copy()
    decision, current = m._apply_exam_transition(order, target, "SUPER_ADMIN", override=override)
    assert not decision.allowed
    assert current == "BOOKED"
    assert vars(order) == before


def test_allowed_technician_transition_still_updates_order():
    order = SimpleNamespace(status="SCHEDULED", exam_status="ORDERED", exam_started_at=None)
    decision, current = m._apply_exam_transition(order, "IN_PROGRESS", "TECHNICIAN")
    assert decision.allowed and current == "ORDERED"
    assert order.status == order.exam_status == "IN_PROGRESS"
    assert order.exam_started_at is not None


@pytest.mark.parametrize("role", ("SUPER_ADMIN", "SUPERVISOR"))
def test_override_still_accepts_valid_exam_states(role):
    assert can_transition(role, "EXAM_COMPLETED", "BOOKED", override=True).allowed


def test_display_normalization_preserves_legacy_fallback():
    assert normalize_state("FINAL") == "ORDERED"
    assert normalize_state(None) == "ORDERED"


@pytest.mark.parametrize("role", ROLES)
def test_exam_route_denies_users_without_permission(app_ctx, monkeypatch, role):
    user = m.User(id=999999, username="synthetic-validation", full_name="Synthetic Validation", active=True,
                  role=m.Role(code=role, name=role, permissions_json="[]"))
    monkeypatch.setattr(m, "current_user", lambda: user)
    monkeypatch.setattr(m, "has_perm", lambda permission: False)
    with m.app.test_client() as client:
        assert client.post("/orders/999999/exam-status", data={"status": "FINAL"}).status_code == 403


def test_exam_route_requires_authentication(monkeypatch):
    monkeypatch.setattr(m, "current_user", lambda: None)
    with m.app.test_client() as client:
        response = client.post("/orders/999999/exam-status", data={"status": "FINAL"})
        assert response.status_code == 302
        assert "/login" in response.location


def ready_work_order(dob):
    return work_order_gate(
        order_status="REGISTERED", balance=0, patient_id="SYNTHETIC-VALIDATION",
        patient_dob=dob, accession="SYNTHETIC-VALIDATION", modality="DX",
        procedure="Synthetic exam", device_id=1, station_ae="SYNTHETIC",
    )


@pytest.mark.parametrize("dob", ("19000229", "20230229", "19901340", "00000000", "19900431", "19900100", "19900132", "1990-01-01", "\u0661\u0669\u0669\u0660\u0660\u0661\u0660\u0661"))
def test_work_order_rejects_impossible_or_non_dicom_dates(dob):
    decision = ready_work_order(dob)
    assert not decision.allowed
    assert "PATIENT_DOB_INVALID_FOR_DICOM" in decision.blockers


@pytest.mark.parametrize("dob", ("20000229", "20240229", "19900101"))
def test_work_order_accepts_valid_calendar_dates(dob):
    assert ready_work_order(dob).allowed


@pytest.mark.parametrize("target", ("FINAL", "VERIFIED", "UNKNOWN", ""))
def test_authorized_http_route_rejects_invalid_target_without_writes(monkeypatch, target):
    order = SimpleNamespace(id=999999, status="SCHEDULED", exam_status="BOOKED")
    before = vars(order).copy()
    monkeypatch.setattr(m, "Order", SimpleNamespace(query=SimpleNamespace(get_or_404=lambda order_id: order)))
    monkeypatch.setattr(m, "current_user", lambda: SimpleNamespace(id=999999, active=True, role=SimpleNamespace(code="SUPER_ADMIN", permissions=lambda:["*"])))
    monkeypatch.setattr(m, "has_perm", lambda permission: True)

    def forbidden_write(*args, **kwargs):
        pytest.fail("Rejected transition attempted a write or successful-transition event")

    monkeypatch.setattr(m, "audit", forbidden_write)
    monkeypatch.setattr(m, "enqueue_event", forbidden_write)
    monkeypatch.setattr(m.db.session, "commit", forbidden_write)
    with m.app.test_client() as client:
        response = client.post("/orders/999999/exam-status", data={"status": target})
        assert response.status_code == 302
    assert vars(order) == before
