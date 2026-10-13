from web.source_contract import read_source as _read_source
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_SOURCE = _read_source(ROOT / "app.py", encoding="utf-8")
BLUEPRINT_SOURCE = _read_source(ROOT / "reporting_support_routes.py", encoding="utf-8")

ROUTES = {
    "/reporting-agent/download",
    "/api/reporting/health",
    "/word-addin/taskpane",
    "/word-addin/manifest.xml",
    "/word-addin/taskpane.js",
    "/api/ohif/reporting-agent/download",
    "/api/ohif/reporting/health",
}


def test_reporting_support_blueprint_owns_expected_runtime_routes(app_ctx):
    rules = {
        str(rule): rule.endpoint
        for rule in app_ctx.app.url_map.iter_rules()
        if str(rule) in ROUTES
    }

    assert set(rules) == ROUTES
    assert all(
        endpoint.startswith("reporting_support.")
        for endpoint in rules.values()
    )


def test_reporting_support_routes_are_not_registered_directly_on_app():
    for route in ROUTES:
        assert f"@app.route('{route}')" not in APP_SOURCE
        assert f"@app.get('{route}')" not in APP_SOURCE

    assert "RB_REPORTING_SUPPORT_BLUEPRINT_V1" in APP_SOURCE
    assert "register_reporting_support_routes" in APP_SOURCE


def test_reporting_support_blueprint_preserves_authentication_wrappers():
    assert "@login_required\ndef reporting_agent_download" in APP_SOURCE
    assert "@require_ohif_token\ndef api_ohif_reporting_agent_download" in APP_SOURCE
    assert 'Blueprint("reporting_support", __name__)' in BLUEPRINT_SOURCE
    assert BLUEPRINT_SOURCE.count("@bp.get(") == len(ROUTES)


def test_reporting_support_view_functions_remain_import_compatible(app_ctx):
    for function_name in (
        "reporting_agent_download",
        "api_reporting_health",
        "word_addin_taskpane",
        "word_addin_manifest",
        "word_addin_taskpane_js",
        "api_ohif_reporting_agent_download",
        "api_ohif_reporting_health",
    ):
        assert callable(getattr(app_ctx, function_name))
