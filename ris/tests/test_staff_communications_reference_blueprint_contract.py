from web.source_contract import read_source as _read_source
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_SOURCE = _read_source(ROOT / "app.py", encoding="utf-8")
BLUEPRINT_SOURCE = _read_source(ROOT / "staff_communications_reference_routes.py", encoding="utf-8")

ROUTES = {
    "/api/staff/communications/queue",
    "/api/staff/chat/<int:request_id>/messages",
    (
        "/api/staff/communications/"
        "<int:request_id>/attachments"
    ),
}


def test_staff_communications_reference_blueprint_owns_runtime_routes(app_ctx):
    rules = {
        str(rule): rule.endpoint
        for rule in app_ctx.app.url_map.iter_rules()
        if str(rule) in ROUTES
    }

    assert set(rules) == ROUTES
    assert all(
        endpoint.startswith("staff_communications_reference.")
        for endpoint in rules.values()
    )


def test_staff_communications_reference_routes_are_not_registered_on_app():
    for route in ROUTES:
        assert f"@app.get('{route}')" not in APP_SOURCE
        assert f'@app.get("{route}")' not in APP_SOURCE
        assert f"@app.route('{route}')" not in APP_SOURCE
        assert f'@app.route("{route}")' not in APP_SOURCE

    assert "RB_STAFF_COMMUNICATIONS_REFERENCE_BLUEPRINT_V1" in APP_SOURCE
    assert "register_staff_communications_reference_routes" in APP_SOURCE


def test_staff_communications_reference_preserves_access_contract():
    for function_name in (
        "staff_communications_queue",
        "staff_chat_messages",
        "staff_contact_attachments",
    ):
        assert f"@login_required\ndef {function_name}" in APP_SOURCE

    assert APP_SOURCE.count("_rb_staff_role_allowed()") >= 4
    assert BLUEPRINT_SOURCE.count("@bp.get(") == len(ROUTES)
    assert "@bp.post(" not in BLUEPRINT_SOURCE


def test_staff_communications_reference_blueprint_remains_read_only():
    for token in (
        "db.session.commit",
        "db.session.add",
        "db.session.delete",
        "staff_communications_claim",
        "staff_communications_confirm",
        "staff_communications_reject",
        "staff_chat_message(",
        "staff_contact_upload",
    ):
        assert token not in BLUEPRINT_SOURCE


def test_staff_communications_reference_functions_remain_import_compatible(app_ctx):
    assert callable(app_ctx.staff_communications_queue)
    assert callable(app_ctx.staff_chat_messages)
    assert callable(app_ctx.staff_contact_attachments)
