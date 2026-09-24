#!/usr/bin/env bash
set -u

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

APP="$ROOT/ris/app.py"
JS="$ROOT/ris/static/doctor-workspace.js"
HTML="$ROOT/ris/templates/doctor_unified_workspace.html"

FAIL=0

check_any() {
    NAME="$1"
    PATTERN="$2"
    shift 2

    FOUND=0

    for FILE in "$@"; do
        if [ -f "$FILE" ] && grep -Fq "$PATTERN" "$FILE"; then
            FOUND=1
            break
        fi
    done

    if [ "$FOUND" = "1" ]; then
        echo "PASS|$NAME"
    else
        echo "FAIL|$NAME|MISSING=$PATTERN"
        FAIL=$((FAIL+1))
    fi
}

echo "===== CANONICAL FEATURE CHECK ====="

check_any "doctor_layout_storage" \
    "radbridge.doctor.column-layout.v5" \
    "$JS"

check_any "doctor_column_presets" \
    "columnPresets" \
    "$JS"

check_any "doctor_reporting_preset" \
    "reporting:defaultColumns" \
    "$JS"

check_any "doctor_clinical_preset" \
    "clinical:['priority','accession','patient_worklist'" \
    "$JS"

check_any "doctor_verification_preset" \
    "verification:['priority','accession','patient_worklist'" \
    "$JS"

check_any "doctor_drag_start" \
    "dragstart" \
    "$JS"

check_any "doctor_drag_over" \
    "dragover" \
    "$JS"

check_any "doctor_resize" \
    "pointerdown" \
    "$JS"

check_any "doctor_width_storage" \
    "layout.widths[key]" \
    "$JS"

check_any "doctor_patient_worklist" \
    "patient_worklist" \
    "$APP" "$JS" "$HTML"

check_any "doctor_column_layout_api" \
    "doctor_workspace_column_layout_save" \
    "$APP"

check_any "doctor_layout_api_template" \
    "data-column-layout-api" \
    "$HTML"

check_any "doctor_columns_button" \
    "rbDoctorColumnsButton" \
    "$HTML"

check_any "doctor_patient_id_filter" \
    "rbDoctorPatientIdFilter" \
    "$HTML"

check_any "doctor_exam_code_filter" \
    "rbDoctorExamCodeFilter" \
    "$HTML"

check_any "doctor_saved_view_update_ui" \
    "data-doctor-saved-update" \
    "$HTML"

check_any "saved_search_model" \
    "class SavedSearchFilter" \
    "$APP"

check_any "saved_view_update_route" \
    "def saved_view_update" \
    "$APP"

check_any "doctor_saved_views" \
    "saved_views=_saved_views_for('DOCTOR')" \
    "$APP"

check_any "report_status" \
    "report_status" \
    "$APP" "$JS" "$HTML"

check_any "reported_by" \
    "reported_by" \
    "$APP" "$JS" "$HTML"

check_any "verified_by" \
    "verified_by" \
    "$APP" "$JS" "$HTML"

check_any "finalized_by" \
    "finalized_by" \
    "$APP" "$JS" "$HTML"

check_any "sla_status" \
    "sla_status" \
    "$APP" "$JS" "$HTML"

check_any "pacs_stage" \
    "PACS_IMAGES_ONLY" \
    "$APP"

check_any "reports_stage" \
    "REPORTS_ONLY" \
    "$APP"

check_any "ris_stage" \
    "RIS_CASE_DATA_ONLY" \
    "$APP"

check_any "pacs_executor" \
    "granular_delete_images_only_execute" \
    "$APP"

check_any "reports_executor" \
    "granular_delete_reports_only_execute" \
    "$APP"

check_any "ris_executor" \
    "granular_delete_ris_case_only_execute" \
    "$APP"

check_any "full_case_gate" \
    "RADBRIDGE_FULL_CASE_ORCHESTRATION_EXECUTION_ENABLED" \
    "$APP"

check_any "full_case_disabled" \
    "FULL_CASE_EXECUTION_DISABLED" \
    "$APP"

check_any "partial_destructive_state" \
    "partial_destructive_changes" \
    "$APP"

echo
echo "===== CANONICAL FEATURE CHECK RESULT ====="

if [ "$FAIL" = "0" ]; then
    echo "CANONICAL_FEATURE_CHECK=PASS"
    echo "FAILED_FEATURE_COUNT=0"
    exit 0
fi

echo "CANONICAL_FEATURE_CHECK=FAIL"
echo "FAILED_FEATURE_COUNT=$FAIL"
exit 1
