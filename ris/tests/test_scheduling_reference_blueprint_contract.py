from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_SOURCE = (ROOT / "app.py").read_text(encoding="utf-8")
BLUEPRINT_SOURCE = (ROOT / "scheduling_reference_routes.py").read_text(
    encoding="utf-8"
)

ROUTES = {
    "/api/registration/procedures",
    "/api/pricing",
    "/api/slots",
    "/api/booking/procedures",
}


def test_scheduling_reference_blueprint_owns_runtime_routes(app_ctx):
    rules = {
        str(rule): rule.endpoint
        for rule in app_ctx.app.url_map.iter_rules()
        if str(rule) in ROUTES
    }

    assert set(rules) == ROUTES
    assert all(
        endpoint.startswith("scheduling_reference.")
        for endpoint in rules.values()
    )


def test_scheduling_reference_routes_are_not_registered_on_app():
    for route in ROUTES:
        assert f"@app.route('{route}')" not in APP_SOURCE
        assert f'@app.route("{route}")' not in APP_SOURCE
        assert f"@app.get('{route}')" not in APP_SOURCE
        assert f'@app.get("{route}")' not in APP_SOURCE

    assert "RB_SCHEDULING_REFERENCE_BLUEPRINT_V1" in APP_SOURCE
    assert "register_scheduling_reference_routes" in APP_SOURCE


def test_scheduling_reference_preserves_auth_and_read_only_contract():
    assert "@login_required\ndef api_registration_procedures" in APP_SOURCE
    assert "@login_required\ndef api_pricing" in APP_SOURCE
    assert "@require_perm('appointments.manage')\ndef api_slots" in APP_SOURCE
    assert "@require_perm('appointments.view')\ndef api_booking_procedures" in APP_SOURCE
    assert BLUEPRINT_SOURCE.count("@bp.get(") == len(ROUTES)
    assert "@bp.post(" not in BLUEPRINT_SOURCE


def test_scheduling_reference_functions_remain_import_compatible(app_ctx):
    for function_name in (
        "api_registration_procedures",
        "api_pricing",
        "api_slots",
        "api_booking_procedures",
    ):
        assert callable(getattr(app_ctx, function_name))
