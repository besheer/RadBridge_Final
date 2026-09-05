from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / 'app.py').read_text(encoding='utf-8')
ORDER_FORM = (ROOT / 'templates' / 'order_form.html').read_text(encoding='utf-8')
DOCKERFILE = (ROOT / 'Dockerfile').read_text(encoding='utf-8')


def test_release_metadata_is_v5442():
    assert "APP_VERSION = '5.46.9'" in APP
    assert "BUILD_NAME = 'fresh-schema-runtime-hardening'" in APP
    assert 'org.opencontainers.image.version' in DOCKERFILE


def test_permission_registry_has_backup_view_as_separate_permission():
    assert "'inventory.reports'," in APP
    assert "'backup.view'," in APP
    assert "inventory.reportsbackup.view" not in APP
    # ROLE_PERMS should contain a single CALL_CENTER definition.
    role_block = APP.split('ROLE_PERMS = {', 1)[1].split('ALL_PERMISSIONS = [', 1)[0]
    assert role_block.count("'CALL_CENTER':") == 1


def test_ai_case_context_has_single_definition():
    assert APP.count('\ndef ai_case_context(order):') == 1
    assert "'verified_image_ai'" in APP


def test_communications_accepts_canonical_production_roles():
    section = APP.split('def _rb_staff_role_allowed():', 1)[1].split('@app.post("/api/public-call/request")', 1)[0]
    assert '"SUPER_ADMIN"' in section
    assert '"CASE_COORDINATOR"' in section
    assert '"RECEPTION"' in section
    assert '"CALL_CENTER"' in section


def test_reporting_api_requires_authentication():
    assert 'RADBRIDGE_REPORTING_TOKEN' in APP
    assert 'X-RadBridge-Reporting-Token' in APP
    assert 'X-RadBridge-Case-Token' in APP
    assert 'reporting_case_token' in APP
    assert "@require_reporting_api(write=False)\ndef api_reporting_case" in APP
    assert "@require_reporting_api(write=True)\ndef api_reporting_draft" in APP
    assert "@require_reporting_api(write=True)\ndef api_reporting_finalize" in APP


def test_registration_form_disables_inactive_patient_section():
    assert 'function setSectionActive(section,active)' in ORDER_FORM
    assert 'el.disabled=!active' in ORDER_FORM
    assert "el.required=active && el.dataset.rbInitiallyRequired==='1'" in ORDER_FORM
    assert 'id="savePatientVisitBtn"' in ORDER_FORM
    assert 'type="submit"' in ORDER_FORM


def test_page_title_contains_no_script():
    title_block = ORDER_FORM.split('{% block page_title %}', 1)[1].split('{% endblock %}', 1)[0]
    assert '<script' not in title_block


def test_registration_commits_before_external_side_effects():
    route = APP.split('def new_order():', 1)[1].split("@app.get('/api/registration/procedures')", 1)[0]
    commit_marker = "# Persist the complete RIS transaction before any external side effect."
    assert commit_marker in route
    section = route.split(commit_marker, 1)[1]
    assert section.index('db.session.commit()') < section.index('send_mwl(order)')
    assert section.index('db.session.commit()') < section.index('offer_next_doctor(')
    assert "enqueue_event(\n            'ORDER_MWL_CREATE'" in section
    assert "enqueue_event(\n            'ORDER_SMART_ASSIGNMENT'" in section


def test_failed_registration_commit_cleans_saved_attachments():
    route = APP.split('def new_order():', 1)[1].split("@app.get('/api/registration/procedures')", 1)[0]
    assert 'saved_attachment_paths=[]' in route
    assert 'saved_attachment_paths.append(path)' in route
    assert 'os.remove(saved_path)' in route


def test_session_cookie_hardening_and_origin_guard_present():
    assert "SESSION_COOKIE_HTTPONLY" in APP
    assert "SESSION_COOKIE_SAMESITE" in APP
    assert "SESSION_COOKIE_SECURE" in APP
    assert 'def _same_origin_unsafe_request_guard()' in APP


def test_reporting_agent_package_uses_scoped_token():
    import zipfile
    path = ROOT / 'downloads' / 'RIS-Reporting-Agent-Auto-v2.zip'
    with zipfile.ZipFile(path) as zf:
        source = zf.read('RISReportingAgent.cs').decode('utf-8')
    assert 'X-RadBridge-Case-Token' in source
    assert 'ReadQueryValue(arg,"token")' in source


def test_accession_is_dicom_sh_safe():
    import app

    values = set()

    for _ in range(50):
        value = app.new_accession()
        assert len(value) <= 16
        assert value.isalnum()
        assert value not in values
        values.add(value)


def test_accession_is_dicom_sh_safe():
    import app

    values = set()

    for _ in range(50):
        value = app.new_accession()
        assert len(value) <= 16
        assert value.isalnum()
        assert value not in values
        values.add(value)
