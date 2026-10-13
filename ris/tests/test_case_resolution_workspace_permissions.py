from web.source_contract import get_source as _get_source
import inspect
from pathlib import Path
from types import SimpleNamespace

import pytest
from werkzeug.exceptions import Forbidden


ROOT = Path(__file__).resolve().parents[1]


def _permission_set(monkeypatch, module, allowed):
    allowed = set(allowed)
    monkeypatch.setattr(module, "has_perm", lambda permission: permission in allowed)


def test_operational_permission_matrix(app_ctx, monkeypatch):
    m = app_ctx

    _permission_set(monkeypatch, m, {"orders.create"})
    assert m.case_exception_history_allowed() is True
    assert m.case_exception_refresh_allowed() is False
    assert m.case_exception_override_allowed() is False

    _permission_set(monkeypatch, m, {"nursing.worklist"})
    assert m.case_exception_history_allowed() is True
    assert m.case_exception_refresh_allowed() is True
    assert m.case_exception_override_allowed() is False

    _permission_set(monkeypatch, m, {"reports.coordinate", "assignment.manage"})
    assert m.case_exception_history_allowed() is True
    assert m.case_exception_refresh_allowed() is True
    assert m.case_exception_override_allowed() is False

    _permission_set(monkeypatch, m, {"pacs.reconcile"})
    assert m.case_exception_history_allowed() is True
    assert m.case_exception_refresh_allowed() is True
    assert m.case_exception_override_allowed() is False

    _permission_set(monkeypatch, m, {"pacs.reconcile", "workflow.override"})
    assert m.case_exception_override_allowed() is True


@pytest.mark.parametrize(
    "endpoint,path,outer_permission",
    [
        ("case_exception_history_add", "/orders/999/exceptions/history", "orders.view"),
        ("case_exception_refresh", "/orders/999/exceptions/refresh", "orders.view"),
        ("case_exception_image_minimum", "/orders/999/exceptions/image-minimum", "pacs.reconcile"),
        ("case_exception_image_minimum_deactivate", "/orders/999/exceptions/image-minimum/1/deactivate", "pacs.reconcile"),
    ],
)
def test_write_routes_reject_users_missing_action_permission(
    app_ctx, monkeypatch, endpoint, path, outer_permission
):
    m = app_ctx
    monkeypatch.setattr(m, "current_user", lambda: SimpleNamespace(id=-1))
    checked = []

    def permission(permission_name):
        checked.append(permission_name)
        return permission_name == outer_permission

    monkeypatch.setattr(m, "has_perm", permission)
    values = {"order_id": 999}
    if endpoint == "case_exception_image_minimum_deactivate":
        values["override_id"] = 1

    with m.app.test_request_context(path, method="POST"):
        with pytest.raises(Forbidden):
            m.app.view_functions[endpoint](**values)

    assert outer_permission in checked


def test_resolver_passes_separate_capabilities_to_template(app_ctx):
    source = _get_source(app_ctx.case_exception_resolver)
    for marker in (
        "can_reconcile=can_reconcile",
        "can_map_series=can_reconcile and bool(rule) and bool(series)",
        "can_add_history=can_add_history",
        "can_refresh=can_refresh",
        "can_override=can_override",
        "can_manage_quality_rules=has_perm('users.view')",
        "can_view_resolution_history=has_perm('audit.view')",
        "focus_mode=bool(selected)",
    ):
        assert marker in source


def test_focused_workspace_is_simple_evidence_grounded_and_theme_safe(app_ctx):
    m = app_ctx
    source, _, _ = m.app.jinja_env.loader.get_source(
        m.app.jinja_env, "case_exception_resolver.html"
    )
    m.app.jinja_env.parse(source)

    for marker in (
        "{% if not focus_mode %}",
        "Back to Exception Queue",
        "Resolution Steps",
        "Advanced PACS tools — authorized users only",
        "can_map_series",
        "can_add_history",
        "can_refresh",
        "can_override",
        "workflow.override",
        "No persisted Series evidence. Series Mapping is disabled.",
        "var(--rb-card",
        "var(--rb-text-main",
        "@media(max-width:620px)",
    ):
        assert marker in source

    assert "order_id=item.order.id,q=item.order.accession" not in source
    assert source.count("Case Exception Resolution & Data Mapping") == 0


def test_no_schema_migration_is_added_for_workspace_permissions():
    migrations = list((ROOT / "migrations" / "versions").glob("*.py"))
    assert not any("case_resolution_workspace" in item.name for item in migrations)
