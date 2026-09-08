from types import SimpleNamespace

import pytest
from flask import url_for
from jinja2 import nodes
from werkzeug.exceptions import Forbidden

ROUTES = [
    ("storage_dr_manager", "/admin/storage-dr",
     {"GET", "POST"}, "storage.targets.view", {}),
    ("storage_target_health", "/admin/storage-dr/storage/<int:storage_id>/health",
     {"POST"}, "storage.targets.manage", {"storage_id": 7}),
    ("replication_state_update", "/admin/storage-dr/policy/<int:policy_id>/state",
     {"POST"}, "dr.manage", {"policy_id": 7}),
    ("dr_failover_request", "/admin/storage-dr/policy/<int:policy_id>/failover",
     {"POST"}, "dr.failover", {"policy_id": 7}),
    ("storage_cloud_manager", "/admin/storage-cloud",
     {"GET", "POST"}, "storage.cloud.view", {}),
]


def registered_rule(m, path):
    rules = [
        r for r in m.app.url_map.iter_rules()
        if r.rule == path and not r.build_only
    ]
    assert len(rules) == 1, (path, rules)
    return rules[0]


def request_path(path, arguments):
    for key, value in arguments.items():
        path = path.replace("<int:" + key + ">", str(value))
    return path


@pytest.mark.parametrize("name,path,methods,permission,arguments", ROUTES)
def test_storage_admin_url_and_method_contract(
    app_ctx, name, path, methods, permission, arguments
):
    m = app_ctx
    rule = registered_rule(m, path)
    expected_methods = methods | {"OPTIONS"}
    if "GET" in methods:
        expected_methods |= {"HEAD"}
    assert rule.methods == expected_methods
    assert rule.endpoint.rsplit(".", 1)[-1] == name
    with m.app.test_request_context("/"):
        assert url_for(rule.endpoint, **arguments) == request_path(path, arguments)


@pytest.mark.parametrize("name,path,methods,permission,arguments", ROUTES)
def test_storage_admin_anonymous_redirect(
    app_ctx, monkeypatch, name, path, methods, permission, arguments
):
    m = app_ctx
    monkeypatch.setattr(m, "current_user", lambda: None)

    def unexpected_permission_check(*args, **kwargs):
        pytest.fail("Anonymous request reached permission evaluation")

    monkeypatch.setattr(m, "has_perm", unexpected_permission_check)
    rule = registered_rule(m, path)
    method = "GET" if "GET" in methods else "POST"
    with m.app.test_request_context(
        request_path(path, arguments), method=method
    ):
        response = m.app.make_response(
            m.app.view_functions[rule.endpoint](**arguments)
        )
        assert response.status_code == 302
        assert response.location.split("?", 1)[0] == url_for("login")


@pytest.mark.parametrize("name,path,methods,permission,arguments", ROUTES)
def test_storage_admin_outer_permission_contract(
    app_ctx, monkeypatch, name, path, methods, permission, arguments
):
    m = app_ctx
    monkeypatch.setattr(m, "current_user", lambda: SimpleNamespace(id=-1))
    checked = []

    def deny(permission_name):
        checked.append(permission_name)
        return False

    def unexpected_defaults():
        pytest.fail("Denied request entered storage handler")

    monkeypatch.setattr(m, "has_perm", deny)
    monkeypatch.setattr(m, "storage_defaults", unexpected_defaults)
    rule = registered_rule(m, path)
    method = "GET" if "GET" in methods else "POST"
    with m.app.test_request_context(
        request_path(path, arguments), method=method
    ):
        with pytest.raises(Forbidden):
            m.app.view_functions[rule.endpoint](**arguments)
    assert checked == [permission]


@pytest.mark.parametrize("path,form,allowed,required", [
    ("/admin/storage-dr", {"action": "ADD_STORAGE"},
     {"storage.targets.view"}, "storage.targets.manage"),
    ("/admin/storage-dr", {"action": "ADD_NODE"},
     {"storage.targets.view", "storage.targets.manage"}, "dr.manage"),
    ("/admin/storage-dr", {"action": "ADD_POLICY"},
     {"storage.targets.view", "storage.targets.manage"}, "dr.manage"),
    ("/admin/storage-cloud", {},
     {"storage.cloud.view"}, "storage.cloud.manage"),
])
def test_storage_admin_post_requires_manage_permission(
    app_ctx, monkeypatch, path, form, allowed, required
):
    m = app_ctx
    checked = []
    monkeypatch.setattr(m, "current_user", lambda: SimpleNamespace(id=-1))
    monkeypatch.setattr(m, "storage_defaults", lambda: None)

    def permitted(permission_name):
        checked.append(permission_name)
        return permission_name in allowed

    monkeypatch.setattr(m, "has_perm", permitted)
    rule = registered_rule(m, path)
    with m.app.test_request_context(path, method="POST", data=form):
        with pytest.raises(Forbidden):
            m.app.view_functions[rule.endpoint]()
    assert required in checked


def test_storage_admin_template_endpoint_links(app_ctx):
    m = app_ctx
    expected_names = {item[0] for item in ROUTES}
    checked = set()

    with m.app.test_request_context("/"):
        for template in ("base.html", "storage_dr.html", "storage_cloud.html"):
            source, _, _ = m.app.jinja_env.loader.get_source(
                m.app.jinja_env, template
            )
            tree = m.app.jinja_env.parse(source)
            for call in tree.find_all(nodes.Call):
                if not isinstance(call.node, nodes.Name):
                    continue
                if call.node.name != "url_for" or not call.args:
                    continue
                first = call.args[0]
                if not isinstance(first, nodes.Const):
                    continue
                endpoint = first.value
                if not isinstance(endpoint, str):
                    continue
                name = endpoint.rsplit(".", 1)[-1]
                if name not in expected_names:
                    continue
                contract = next(item for item in ROUTES if item[0] == name)
                arguments = contract[4]
                template_keys = {kw.key for kw in call.kwargs}
                assert set(arguments).issubset(template_keys)
                assert url_for(endpoint, **arguments) == request_path(
                    contract[1], arguments
                )
                checked.add(name)

    assert checked == expected_names
