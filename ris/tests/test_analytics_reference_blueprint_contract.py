from web.source_contract import read_source as _read_source
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_SOURCE = _read_source(ROOT / "app.py", encoding="utf-8")
BLUEPRINT_SOURCE = _read_source(ROOT / "analytics_reference_routes.py", encoding="utf-8")

BASE_TEMPLATE = _read_source(ROOT / "templates" / "base.html", encoding="utf-8")
ADMIN_TEMPLATE = _read_source(ROOT / "templates" / "admin.html", encoding="utf-8")


ROUTES = {
    "/analytics": "analytics",
    "/analytics/export.csv": "analytics_export_csv",
}


def _function_source(function_name):
    start = APP_SOURCE.index(f"def {function_name}(")
    next_definition = APP_SOURCE.find("\ndef ", start + 1)
    next_route = APP_SOURCE.find("\n@app.", start + 1)
    endings = [value for value in (next_definition, next_route) if value >= 0]
    end = min(endings) if endings else len(APP_SOURCE)
    return APP_SOURCE[start:end]


def test_analytics_reference_blueprint_owns_runtime_routes(app_ctx):
    rules = {
        str(rule): rule
        for rule in app_ctx.app.url_map.iter_rules()
        if str(rule) in ROUTES
    }

    assert set(rules) == set(ROUTES)
    for route, function_name in ROUTES.items():
        rule = rules[route]
        assert rule.endpoint == f"analytics_reference.{function_name}"
        assert rule.methods - {"HEAD", "OPTIONS"} == {"GET"}


def test_analytics_routes_are_not_registered_directly_on_app():
    for route in ROUTES:
        assert f"@app.route('{route}')" not in APP_SOURCE
        assert f'@app.route("{route}")' not in APP_SOURCE
        assert f"@app.get('{route}')" not in APP_SOURCE
        assert f'@app.get("{route}")' not in APP_SOURCE

    assert "RB_ANALYTICS_REFERENCE_BLUEPRINT_V1" in APP_SOURCE
    assert "register_analytics_reference_routes" in APP_SOURCE


def test_analytics_permissions_are_preserved():
    assert "@require_perm('analytics.view')\ndef analytics" in APP_SOURCE
    assert "@require_perm('export.view')\ndef analytics_export_csv" in APP_SOURCE
    assert BLUEPRINT_SOURCE.count("@bp.get(") == len(ROUTES)
    assert "@bp.post(" not in BLUEPRINT_SOURCE


def test_analytics_template_links_use_blueprint_endpoint():
    expected = "url_for('analytics_reference.analytics')"
    legacy = "url_for('analytics')"

    assert expected in BASE_TEMPLATE
    assert 'analytics_reference.analytics' in _read_source(ROOT / 'admin_control_center.py', encoding='utf-8')
    assert 'sections' in ADMIN_TEMPLATE
    assert legacy not in BASE_TEMPLATE
    assert legacy not in ADMIN_TEMPLATE


def test_analytics_handlers_remain_read_only_and_import_compatible(app_ctx):
    for function_name in ROUTES.values():
        function_source = _function_source(function_name)
        assert "db.session.add(" not in function_source
        assert "db.session.delete(" not in function_source
        assert "db.session.commit(" not in function_source
        assert callable(getattr(app_ctx, function_name))


def test_unrelated_sensitive_and_write_surfaces_remain_legacy(app_ctx):
    protected = {
        "/admin/import-export": "admin_import_export",
        "/attachments/<int:attachment_id>": "attachment_download",
        "/api/voice/patient/search": "voice_api_patient_search",
        "/api/voice/inquiry": "voice_api_inquiry",
    }

    runtime = [
        rule
        for rule in app_ctx.app.url_map.iter_rules()
        if str(rule) in protected and rule.endpoint in protected.values()
    ]

    assert len(runtime) == len(protected)
    for rule in runtime:
        assert rule.endpoint == protected[str(rule)]
        assert "." not in rule.endpoint
