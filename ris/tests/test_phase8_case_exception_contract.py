from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_backend_routes_and_models_are_present():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    from infrastructure.models import ReadinessSeriesAlias, CaseExceptionResolutionEvent
    assert ReadinessSeriesAlias.__table__.name == 'readiness_series_alias'
    assert CaseExceptionResolutionEvent.__table__.name == 'case_exception_resolution_event'
    assert "def case_exception_resolver" in source
    assert "def case_exception_series_map" in source
    assert "def case_exception_history_add" in source
    assert "def case_exception_image_minimum" in source
    assert "def case_exception_refresh" in source
    assert source.count("@require_perm('pacs.reconcile')") >= 6


def test_service_owns_no_commit_and_protects_terminal_cases():
    source = (ROOT / "case_exception_resolution_service.py").read_text(encoding="utf-8")
    assert ".commit(" not in source
    assert "with_for_update" in source
    assert "TERMINAL_CASE_RESOLUTION_LOCKED" in source
    assert "TERMINAL_REPORT_RESOLUTION_LOCKED" in source
    assert "CANONICAL_SERIES_NOT_REQUIRED_BY_RULE" in source
    assert "APPROVED_MINIMUM_MUST_NOT_EXCEED_CURRENT_IMAGES" in source


def test_resolver_template_has_search_preview_and_audit_guidance():
    source = (ROOT / "templates" / "case_exception_resolver.html").read_text(encoding="utf-8")
    assert "Search RIS" in source
    assert "Resolution Steps" in source
    assert "Back to Exception Queue" in source
    assert "Save Mapping & Re-evaluate" in source
    assert "Save Exception & Re-evaluate" in source
    assert "Resolution History" in source
    assert source.count("action_info(") >= 3


def test_migration_chain_and_tables():
    source = (ROOT / "migrations" / "versions" /
              "20260904_001_case_exception_resolution.py").read_text(encoding="utf-8")
    assert 'revision = "20260904_001"' in source
    assert 'down_revision = "20260903_003"' in source
    assert '"readiness_series_alias"' in source
    assert '"case_exception_resolution_event"' in source
    assert '"case_readiness_override"' in source
