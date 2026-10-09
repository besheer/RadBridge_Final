from case_readiness_service import evaluate_readiness, required_series_groups

def test_slash_is_alternative_and_comma_is_required_group():
    assert required_series_groups("PA/AP,LATERAL") == [["PA", "AP"], ["LATERAL"]]

def test_ct_brain_blocks_images_and_missing_axial():
    result = evaluate_readiness(image_count=3, min_images=80, warning_images=60,
        require_pacs=True, pacs_present=True, require_history=True,
        history_present=True, require_attachments=False, attachment_count=0,
        required_series="AXIAL", series=[{"description":"RadBridge Synthetic PACS Test", "modality":"CT", "instance_count":3}])
    assert result["status"] == "BLOCKED"
    assert "INCOMPLETE_IMAGES" in result["details"]["blockers"]
    assert "MISSING_SERIES" in result["details"]["blockers"]

def test_axial_evidence_satisfies_series():
    result = evaluate_readiness(image_count=80, min_images=80, warning_images=60,
        require_pacs=True, pacs_present=True, require_history=True,
        history_present=True, require_attachments=False, attachment_count=0,
        required_series="AXIAL", series=[{"description":"AXIAL BRAIN", "modality":"CT", "instance_count":80}])
    assert result["status"] == "READY"
    assert result["details"]["missing_required_series"] == []
