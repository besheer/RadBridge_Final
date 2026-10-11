from web.source_contract import read_source as _read_source
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = _read_source(ROOT / 'app.py', encoding='utf-8')
ORDER_FORM = _read_source(ROOT / 'templates' / 'order_form.html', encoding='utf-8')
DOCKERFILE = _read_source(ROOT / 'Dockerfile', encoding='utf-8')


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


def test_registration_commits_without_mwl_or_assignment_side_effects():
    import ast

    tree = ast.parse(APP)
    node = next(
        item
        for item in tree.body
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
        and item.name == 'new_order'
    )
    route = ast.get_source_segment(APP, node) or ''
    commit_marker = "# Persist the complete RIS transaction before any external side effect."
    assert commit_marker in route
    section = route.split(commit_marker, 1)[1]
    assert 'db.session.commit()' in section
    assert 'send_mwl(order)' not in section
    assert 'offer_next_doctor(' not in section
    assert "enqueue_event(\n            'ORDER_MWL_CREATE'" not in section
    assert "enqueue_event(\n            'ORDER_SMART_ASSIGNMENT'" not in section


def test_failed_registration_commit_cleans_saved_attachments():
    route = APP.split('def new_order():', 1)[1].split("@app.get('/api/registration/procedures')", 1)[0]
    assert 'saved_attachment_paths=[]' in route
    assert 'saved_attachment_paths.append(path)' in route
    assert 'os.remove(saved_path)' in route


def test_session_cookie_hardening_and_origin_guard_present(app_ctx):
    import os
    from infrastructure.settings import WebSettings

    expected = WebSettings.from_environment(os.environ).flask_config()
    assert app_ctx.app.config['SESSION_COOKIE_HTTPONLY'] is True
    for key in ('SESSION_COOKIE_SAMESITE', 'SESSION_COOKIE_SECURE'):
        assert app_ctx.app.config[key] == expected[key]
    assert any(handler.__name__ == '_same_origin_unsafe_request_guard'
               for handler in app_ctx.app.before_request_funcs[None])


def test_reporting_agent_v2_contract_replaces_legacy_package_gate():
    contract = _read_source(ROOT / 'docs' / 'REPORTING_AGENT_V2_CONTRACT.md')
    for marker in (
        'optional compatibility bridge',
        'X-RadBridge-Case-Token',
        'REPORT_EDIT_LOCKED',
        'DRAFT',
        'VERIFIED',
        'FINAL',
        'immutable',
        'checksum',
        'audit trail',
        'RadBridge branding',
    ):
        assert marker in contract

    route = APP.split('def reporting_agent_download():', 1)[1].split(
        '@app.get', 1
    )[0]
    assert "if not os.path.exists(path):" in route
    assert 'abort(404)' in route


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
