from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
JS=(ROOT/'static'/'doctor-workspace.js').read_text()
HTML=(ROOT/'templates'/'doctor_unified_workspace.html').read_text()

def test_doctor_search_has_clear_apply_model_and_url_sync():
    for marker in (
        'rbDoctorAdvancedFilters',
        'rbDoctorApplyAdvancedFilters',
        'rbDoctorClearAdvancedFilters',
        'rbDoctorActiveFilters',
        'rbDoctorActiveFilterChips',
        "More filters",
        "Apply filters",
        "Saved views",
    ):
        assert marker in HTML
    for marker in (
        'appliedSearch',
        'appliedAdvanced',
        'syncUrl()',
        'applySearchFilters',
        'applyAdvancedFilterValues',
        'renderActiveFilters',
        'preserveRequestedOption',
        "history.replaceState",
    ):
        assert marker in JS

def test_final_cases_remain_hidden_until_explicit_search_or_final_filter():
    assert "String(c.report_status||'').toUpperCase()==='FINAL'&&!archivedRequested" in JS
    assert "appliedAdvanced.report_status==='FINAL'" in JS
    assert "appliedSearch.patient_id" in JS
    assert "appliedSearch.accession" in JS

def test_advanced_filters_do_not_auto_apply_on_change():
    assert "[dateFrom,dateTo,...Object.values(filters)].forEach(control=>control.addEventListener('change',renderCases));" not in JS
    assert "applyAdvancedFilters.addEventListener('click',applyAdvancedFilterValues)" in JS
