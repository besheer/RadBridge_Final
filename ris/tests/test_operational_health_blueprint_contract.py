from web.source_contract import read_source as _read_source
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_SOURCE = _read_source(ROOT / "app.py", encoding="utf-8")
BLUEPRINT_SOURCE = _read_source(ROOT / "operational_health_routes.py", encoding="utf-8")

ROUTES = {
    "/api/ops/health",
    "/api/ohif/onlyoffice/health",
}


def test_operational_health_blueprint_owns_runtime_routes(app_ctx):
    rules = {
        str(rule): rule.endpoint
        for rule in app_ctx.app.url_map.iter_rules()
        if str(rule) in ROUTES
    }

    assert set(rules) == ROUTES
    assert all(
        endpoint.startswith("operational_health.")
        for endpoint in rules.values()
    )


def test_operational_health_routes_are_not_registered_on_app():
    for route in ROUTES:
        assert f"@app.route('{route}')" not in APP_SOURCE
        assert f'@app.route("{route}")' not in APP_SOURCE
        assert f"@app.get('{route}')" not in APP_SOURCE
        assert f'@app.get("{route}")' not in APP_SOURCE

    assert "RB_OPERATIONAL_HEALTH_BLUEPRINT_V1" in APP_SOURCE
    assert "register_operational_health_routes" in APP_SOURCE


def test_operational_health_preserves_access_contract():
    assert "@login_required\ndef api_ops_health" in APP_SOURCE
    assert (
        "@login_required\ndef api_ohif_onlyoffice_health"
        not in APP_SOURCE
    )
    assert BLUEPRINT_SOURCE.count("@bp.get(") == len(ROUTES)
    assert "@bp.post(" not in BLUEPRINT_SOURCE


def test_operational_health_remains_read_only():
    assert "db.session.commit" not in BLUEPRINT_SOURCE
    assert "db.session.add" not in BLUEPRINT_SOURCE
    assert "db.session.delete" not in BLUEPRINT_SOURCE
    assert "api_assignment_offer_pending" not in BLUEPRINT_SOURCE


def test_operational_health_functions_remain_import_compatible(app_ctx):
    assert callable(app_ctx.api_ops_health)
    assert callable(app_ctx.api_ohif_onlyoffice_health)
