import pytest
from pacs_resolution_policy import (
    PacsResolutionPolicyError,
    assert_exam_link_allowed,
    assert_exam_unlink_allowed,
    assert_primary_link_allowed,
)


def test_terminal_same_study_is_idempotent():
    assert assert_primary_link_allowed(order_status="FINAL", report_status="FINAL", current_study_id="A", requested_study_id="A") == "IDEMPOTENT"


def test_terminal_different_study_is_blocked():
    with pytest.raises(PacsResolutionPolicyError, match="TERMINAL_CASE_PACS_LOCKED"):
        assert_primary_link_allowed(order_status="FINAL", report_status="FINAL", current_study_id="A", requested_study_id="B")


def test_exam_link_requires_same_patient():
    with pytest.raises(PacsResolutionPolicyError, match="EXAM_LINK_PATIENT_MISMATCH"):
        assert_exam_link_allowed(primary_patient_id=1, secondary_patient_id=2, secondary_order_status="SCHEDULED", secondary_report_status="UNREPORTED", reason="same acquisition")


def test_exam_link_allows_same_patient_editable_order():
    assert assert_exam_link_allowed(primary_patient_id=1, secondary_patient_id=1, secondary_order_status="SCHEDULED", secondary_report_status="UNREPORTED", reason="CT chest abdomen pelvis")


def test_final_secondary_unlink_is_blocked():
    with pytest.raises(PacsResolutionPolicyError, match="TERMINAL_CASE_PACS_LOCKED"):
        assert_exam_unlink_allowed(
            secondary_order_status="FINAL",
            secondary_report_status="VERIFIED",
            reason="valid removal reason",
        )


def test_exam_unlink_requires_reason():
    with pytest.raises(PacsResolutionPolicyError, match="EXAM_UNLINK_REASON_REQUIRED"):
        assert_exam_unlink_allowed(
            secondary_order_status="SCHEDULED",
            secondary_report_status="UNREPORTED",
            reason="no",
        )
