from assignment_decision_engine import evaluate_assignment_decision, normalize_mode


READY_FACTS = {
    "exam_status": "EXAM_COMPLETED",
    "pacs_status": "IMAGES_COMPLETE",
    "readiness_status": "READY",
    "return_open": False,
    "already_assigned": False,
}


def test_disabled_is_default_and_never_enforces():
    result = evaluate_assignment_decision(facts=READY_FACTS)
    assert result.mode == "DISABLED"
    assert result.recommendation == "NO_DECISION"
    assert result.enforce is False


def test_unknown_mode_fails_safe_to_disabled():
    assert normalize_mode("active") == "DISABLED"
    result = evaluate_assignment_decision(mode="active", facts=READY_FACTS)
    assert result.mode == "DISABLED"
    assert result.enforce is False


def test_shadow_allows_ready_case_without_enforcement():
    result = evaluate_assignment_decision(mode="SHADOW", facts=READY_FACTS)
    assert result.recommendation == "ALLOW"
    assert result.reasons == ("READY_FOR_ASSIGNMENT",)
    assert result.enforce is False


def test_shadow_blocks_incomplete_case_without_enforcement():
    facts = dict(READY_FACTS, pacs_status="RECEIVING", readiness_status="BLOCKED")
    result = evaluate_assignment_decision(mode="SHADOW", facts=facts)
    assert result.recommendation == "BLOCK"
    assert "IMAGES_NOT_COMPLETE" in result.reasons
    assert "READINESS_NOT_READY" in result.reasons
    assert result.enforce is False
