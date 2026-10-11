from web.source_contract import read_source as _read_source
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_SOURCE = _read_source(ROOT / "app.py", encoding="utf-8")
BLUEPRINT_SOURCE = _read_source(ROOT / "telephony_reference_routes.py", encoding="utf-8")

ROUTES = {
    "/api/telephony/me",
    "/api/telephony/directory",
}


def test_telephony_reference_blueprint_owns_runtime_routes(app_ctx):
    rules = {
        str(rule): rule.endpoint
        for rule in app_ctx.app.url_map.iter_rules()
        if str(rule) in ROUTES
    }

    assert set(rules) == ROUTES
    assert all(
        endpoint.startswith("telephony_reference.")
        for endpoint in rules.values()
    )


def test_telephony_reference_routes_are_not_registered_on_app():
    for route in ROUTES:
        assert f"@app.route('{route}')" not in APP_SOURCE
        assert f'@app.route("{route}")' not in APP_SOURCE
        assert f"@app.get('{route}')" not in APP_SOURCE
        assert f'@app.get("{route}")' not in APP_SOURCE

    assert "RB_TELEPHONY_REFERENCE_BLUEPRINT_V1" in APP_SOURCE
    assert "register_telephony_reference_routes" in APP_SOURCE


def test_telephony_reference_preserves_auth_and_read_only_contract():
    assert "@login_required\ndef telephony_me" in APP_SOURCE
    assert "@login_required\ndef telephony_directory" in APP_SOURCE
    assert BLUEPRINT_SOURCE.count("@bp.get(") == len(ROUTES)
    assert "@bp.post(" not in BLUEPRINT_SOURCE
    assert "telephony_credentials" not in BLUEPRINT_SOURCE
    assert "authorization_password" not in BLUEPRINT_SOURCE


def test_telephony_reference_functions_remain_import_compatible(app_ctx):
    assert callable(app_ctx.telephony_me)
    assert callable(app_ctx.telephony_directory)
