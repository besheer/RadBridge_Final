from web.source_contract import get_source as _get_source

def test_v523_models():
    import app as m
    for n in ["ImagingAIProvider","ImagingAIAnalysis","DemographicOverrideAudit"]:
        assert hasattr(m,n)

def test_v523_routes():
    import app as m
    rules={r.rule for r in m.app.url_map.iter_rules()}
    assert {
      "/admin/imaging-ai",
      "/reports/<int:order_id>/imaging-ai",
      "/reports/<int:order_id>/imaging-ai/verify-demographics",
      "/reports/<int:order_id>/imaging-ai/<int:analysis_id>/analyze"
    } <= rules

def test_demographic_gate_exists():
    import app as m,inspect
    src=_get_source(m.imaging_ai_analyze)
    assert "demographic_status!='VERIFIED'" in src

def test_ai_context_uses_only_verified_image_analysis():
    import app as m,inspect
    src=_get_source(m.latest_verified_imaging_analysis)
    assert "demographic_status='VERIFIED'" in src
    assert "status='AI_FINDINGS_READY'" in src

def test_booking_hotfixes_preserved():
    import app as m,inspect
    src=_get_source(m.device_booking_reason)
    assert "active=True" not in src
    sig=inspect.signature(m.device_booking_reason)
    assert sig.parameters["start_at"].default is None
    assert hasattr(m,"and_")
