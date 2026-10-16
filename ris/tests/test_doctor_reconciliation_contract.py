from web.source_contract import read_source as _read_source
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
APP=_read_source(ROOT/'app.py')
JS=_read_source(ROOT/'static'/'doctor-workspace.js')
HTML=_read_source(ROOT/'templates'/'doctor_unified_workspace.html')

def test_doctor_reconciliation_preserves_advanced_workspace_contract():
    for marker in (
        "patient_worklist_display_name",
        "DOCTOR_WORKLIST_COLUMN_KEYS",
        "normalize_doctor_worklist_layout",
        "doctor_workspace_column_layout_save",
        "saved_views=_saved_views_for('DOCTOR')",
        "'pacs_status','report_status','sla_status'",
    ):
        assert marker in APP
    for marker in (
        "radbridge.doctor.column-layout.v5",
        "columnPresets",
        "reporting:defaultColumns",
        "clinical:['priority','accession','patient_worklist'",
        "verification:['priority','accession','patient_worklist'",
        "dragstart",
        "pointerdown",
        "layout.widths[key]",
    ):
        assert marker in JS
    for marker in (
        "data-column-layout-api",
        "rbDoctorColumnsButton",
        "rbDoctorPatientIdFilter",
        "rbDoctorExamCodeFilter",
        "data-doctor-saved-update",
    ):
        assert marker in HTML

def test_doctor_reconciliation_does_not_import_historical_full_app():
    assert 'RADBRIDGE_FULL_CASE_ORCHESTRATION_EXECUTION_ENABLED' in APP
    assert 'FULL_CASE_EXECUTION_DISABLED' in APP
