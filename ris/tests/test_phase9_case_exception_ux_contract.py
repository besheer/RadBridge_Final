from web.source_contract import read_source as _read_source
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_phase9_routes_and_permissions_are_present():
    source = _read_source(ROOT / "app.py", encoding="utf-8")
    assert source.count("def case_exception_series_map_deactivate") == 1
    assert source.count("def case_exception_image_minimum_deactivate") == 1
    assert source.count("@require_perm('pacs.reconcile')") >= 5
    assert "queue_total=queue_query.count()" in source
    assert ".offset((page-1)*per_page).limit(per_page)" in source
    assert "selected_editable=bool(" in source
    assert "has_perm('pacs.reconcile') and selected_editable" in source


def test_phase9_service_is_atomic_and_evidence_grounded():
    source = "\n".join((ROOT / path).read_text(encoding="utf-8") for path in (
        "application/services/readiness/resolution_workflow.py",
        "infrastructure/adapters/readiness/resolution_repository.py"))
    assert "SERIES_ALIAS_NOT_IN_PACS_EVIDENCE" in source
    assert "def atomic_deactivate_series_alias" in source
    assert "def atomic_deactivate_readiness_override" in source
    assert "db.session.commit" not in source
    assert ".with_for_update()" in source


def test_phase9_template_has_queue_filters_and_safe_disable_actions():
    source = _read_source(ROOT / "templates" / "case_exception_resolver.html", encoding="utf-8")
    for token in (
        "Case Exception Queue",
        'name="scope"',
        'name="status"',
        'name="branch_id"',
        'name="modality"',
        'name="blocker"',
        "case_exception_series_map_deactivate",
        "case_exception_image_minimum_deactivate",
        "Exception Queue",
        "Case locked — view only",
        "the Order or Report is terminal and Series Mapping cannot be changed",
        "Advanced PACS tools — authorized users only",
        "Series Mapping is unavailable without PACS evidence",
    ):
        assert token in source


def test_phase9_does_not_add_schema_migration():
    migrations = list((ROOT / "migrations" / "versions").glob("*.py"))
    assert not any("phase9" in item.name.lower() for item in migrations)
