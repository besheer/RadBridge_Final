"""Contract tests for the first incremental Blueprint extraction."""

import pytest
from werkzeug.exceptions import Forbidden


ROUTE = "/api/storage/resolve"
TEST_CODE_PREFIX = "BPTEST_"


def _clear_test_storage(m):
    (
        m.StorageLocation.query
        .filter(
            m.StorageLocation.code.like(
                TEST_CODE_PREFIX + "%"
            )
        )
        .delete(synchronize_session=False)
    )
    m.db.session.commit()


def _add_storage(
    m,
    *,
    code,
    branch_id=None,
    company_code="",
    priority=100,
    active=True,
    storage_type="PACS",
    role="PRIMARY",
):
    row = m.StorageLocation(
        code=code,
        label=code,
        path="/test/" + code.lower(),
        storage_type=storage_type,
        protocol="LOCAL",
        role=role,
        branch_id=branch_id,
        company_code=company_code,
        priority=priority,
        health_status="HEALTHY",
        active=active,
    )
    m.db.session.add(row)
    m.db.session.flush()
    return row


def test_storage_route_url_and_method_contract(app_ctx):
    matches = [
        rule
        for rule in app_ctx.app.url_map.iter_rules()
        if rule.rule == ROUTE
    ]

    assert len(matches) == 1
    assert {"GET", "HEAD", "OPTIONS"}.issubset(
        matches[0].methods
    )
    assert "POST" not in matches[0].methods


def test_storage_route_auth_contract(
    app_ctx,
    monkeypatch,
):
    monkeypatch.setattr(
        app_ctx,
        "current_user",
        lambda: None,
    )

    with app_ctx.app.test_client() as client:
        response = client.get(
            ROUTE,
            follow_redirects=False,
        )

    assert response.status_code == 302
    assert response.headers["Location"].endswith(
        "/login?next=/api/storage/resolve"
    )

    monkeypatch.setattr(
        app_ctx,
        "current_user",
        lambda: object(),
    )
    monkeypatch.setattr(
        app_ctx,
        "has_perm",
        lambda permission: False,
    )

    rule = next(
        rule
        for rule in app_ctx.app.url_map.iter_rules()
        if rule.rule == ROUTE
    )
    view = app_ctx.app.view_functions[
        rule.endpoint
    ]

    with app_ctx.app.test_request_context(ROUTE):
        with pytest.raises(Forbidden) as denied:
            view()

    assert denied.value.code == 403


def test_storage_resolution_and_api_contract(
    app_ctx,
    monkeypatch,
):
    m = app_ctx
    _clear_test_storage(m)

    try:
        global_slower = _add_storage(
            m,
            code="BPTEST_GLOBAL_SLOWER",
            priority=50,
        )
        global_best = _add_storage(
            m,
            code="BPTEST_GLOBAL_BEST",
            priority=10,
        )
        company = _add_storage(
            m,
            code="BPTEST_COMPANY",
            company_code="RBTEST",
            priority=80,
        )
        branch = _add_storage(
            m,
            code="BPTEST_BRANCH",
            branch_id=8801,
            priority=70,
        )
        exact = _add_storage(
            m,
            code="BPTEST_EXACT",
            branch_id=8801,
            company_code="RBTEST",
            priority=90,
        )
        _add_storage(
            m,
            code="BPTEST_INACTIVE_EXACT",
            branch_id=8801,
            company_code="RBTEST",
            priority=1,
            active=False,
        )
        m.db.session.commit()

        assert global_slower.id is not None

        assert m.resolve_storage_target(
            "pacs",
            None,
            "",
            "primary",
        ).id == global_best.id

        assert m.resolve_storage_target(
            "PACS",
            9999,
            "rbtest",
            "PRIMARY",
        ).id == company.id

        assert m.resolve_storage_target(
            "PACS",
            8801,
            "OTHER",
            "PRIMARY",
        ).id == branch.id

        assert m.resolve_storage_target(
            "PACS",
            8801,
            "rbtest",
            "PRIMARY",
        ).id == exact.id

        monkeypatch.setattr(
            m,
            "current_user",
            lambda: object(),
        )
        monkeypatch.setattr(
            m,
            "has_perm",
            lambda permission: (
                permission == "storage.targets.view"
            ),
        )

        with m.app.test_client() as client:
            response = client.get(
                ROUTE,
                query_string={
                    "type": "pacs",
                    "branch_id": 8801,
                    "company_code": "rbtest",
                    "role": "primary",
                },
            )

            missing = client.get(
                ROUTE,
                query_string={
                    "type": "ARCHIVE",
                    "role": "PRIMARY",
                },
            )

        assert response.status_code == 200
        assert response.get_json() == {
            "ok": True,
            "id": exact.id,
            "code": "BPTEST_EXACT",
            "path": "/test/bptest_exact",
            "protocol": "LOCAL",
            "role": "PRIMARY",
            "health": "HEALTHY",
            "branch_id": 8801,
            "company_code": "RBTEST",
        }

        assert missing.status_code == 404
        assert missing.get_json() == {
            "ok": False,
            "error": "NO_STORAGE_TARGET",
        }
    finally:
        _clear_test_storage(m)
