from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_SOURCE = (ROOT / "app.py").read_text(encoding="utf-8")
BLUEPRINT_SOURCE = (ROOT / "voice_scheduling_reference_routes.py").read_text(
    encoding="utf-8"
)

ROUTES = {
    "/api/voice/branches": "voice_api_branches",
    "/api/voice/procedures": "voice_api_procedures",
    "/api/voice/slots": "voice_api_slots",
}

EXCLUDED = {
    "/api/voice/patient/search": "voice_api_patient_search",
    "/api/voice/inquiry": "voice_api_inquiry",
    "/api/voice/patient": "voice_api_patient_create",
    "/api/voice/book": "voice_api_book",
}


def test_voice_scheduling_blueprint_owns_selected_runtime_routes(app_ctx):
    rules = {
        str(rule): rule.endpoint
        for rule in app_ctx.app.url_map.iter_rules()
        if str(rule) in ROUTES
    }

    assert set(rules) == set(ROUTES)
    assert all(
        endpoint.startswith("voice_scheduling_reference.")
        for endpoint in rules.values()
    )


def test_voice_scheduling_routes_are_not_registered_directly_on_app():
    for route in ROUTES:
        assert f'@app.route("{route}", methods=["GET"])' not in APP_SOURCE
        assert f"@app.route('{route}', methods=['GET'])" not in APP_SOURCE
        assert f'@app.get("{route}")' not in APP_SOURCE
        assert f"@app.get('{route}')" not in APP_SOURCE

    assert "RB_VOICE_SCHEDULING_REFERENCE_BLUEPRINT_V1" in APP_SOURCE
    assert "register_voice_scheduling_reference_routes" in APP_SOURCE


def test_voice_token_guard_and_read_only_contract_are_preserved():
    for function_name in ROUTES.values():
        function_start = APP_SOURCE.index(f"def {function_name}(")
        next_route = APP_SOURCE.find("\n@app.", function_start)
        function_source = APP_SOURCE[
            function_start: next_route if next_route >= 0 else len(APP_SOURCE)
        ]
        assert "_voice_api_authorized()" in function_source
        assert "db.session.commit" not in function_source
        assert "db.session.add(" not in function_source
        assert "db.session.delete(" not in function_source

    assert BLUEPRINT_SOURCE.count("@bp.get(") == len(ROUTES)
    assert "@bp.post(" not in BLUEPRINT_SOURCE


def test_sensitive_and_write_voice_routes_remain_on_legacy_app(app_ctx):
    runtime = {
        str(rule): rule
        for rule in app_ctx.app.url_map.iter_rules()
        if str(rule) in EXCLUDED
    }

    assert set(runtime) == set(EXCLUDED)
    for route, endpoint in EXCLUDED.items():
        rule = runtime[route]
        assert rule.endpoint == endpoint
        assert "." not in rule.endpoint

    assert (
        runtime["/api/voice/patient/search"].methods - {"HEAD", "OPTIONS"}
    ) == {"GET"}
    assert (
        runtime["/api/voice/inquiry"].methods - {"HEAD", "OPTIONS"}
    ) == {"GET"}
    assert (
        runtime["/api/voice/patient"].methods - {"HEAD", "OPTIONS"}
    ) == {"POST"}
    assert (
        runtime["/api/voice/book"].methods - {"HEAD", "OPTIONS"}
    ) == {"POST"}


def test_voice_scheduling_functions_remain_import_compatible(app_ctx):
    for function_name in ROUTES.values():
        assert callable(getattr(app_ctx, function_name))
