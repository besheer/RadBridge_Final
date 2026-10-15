import pytest
import app as m
import registration_policy
from werkzeug.exceptions import Forbidden
from test_assignment_distribution import doctor


@pytest.fixture(autouse=True)
def isolated(app_ctx, monkeypatch):
    monkeypatch.setattr(m.db.session, "commit", m.db.session.flush)
    yield
    m.db.session.rollback()
    m.db.session.remove()


def _guard():
    return next(
        callback for callback in m.app.before_request_funcs[None]
        if callback.__name__ == "guard"
        and callback.__code__.co_filename.endswith("inventory_transfer_policy.py")
    )


def _branch_warehouses():
    branch = m.Branch(code="CODEX-UAT-TRANSFER-A", name="CODEX UAT Transfer A", active=True)
    other_branch = m.Branch(code="CODEX-UAT-TRANSFER-B", name="CODEX UAT Transfer B", active=True)
    m.db.session.add_all([branch, other_branch])
    m.db.session.flush()
    central = m.Warehouse(code="CODEX-UAT-MAIN-A", name="CODEX UAT Main A", warehouse_type="MAIN", active=True)
    other_central = m.Warehouse(code="CODEX-UAT-MAIN-B", name="CODEX UAT Main B", warehouse_type="MAIN", active=True)
    m.db.session.add_all([central, other_central])
    m.db.session.flush()
    target = m.Warehouse(code="CODEX-UAT-BRANCH-A", name="CODEX UAT Branch A", warehouse_type="BRANCH", branch_id=branch.id, parent_id=central.id, active=True)
    other_target = m.Warehouse(code="CODEX-UAT-BRANCH-B", name="CODEX UAT Branch B", warehouse_type="BRANCH", branch_id=other_branch.id, parent_id=other_central.id, active=True)
    m.db.session.add_all([target, other_target])
    m.db.session.flush()
    return branch, central, target, other_central, other_target


def test_branch_can_request_only_from_linked_central_and_authorized_branch(monkeypatch):
    branch, central, target, other_central, other_target = _branch_warehouses()
    requester = doctor("inventory-transfer-branch", "RECEPTION")
    requester.branch_id = branch.id
    monkeypatch.setattr(m, "current_user", lambda: requester)
    monkeypatch.setattr(registration_policy, "allowed_registration_branches", lambda: [branch.id])
    guard = _guard()

    with m.app.test_request_context("/inventory/transfers", method="POST", data={
        "source_warehouse_id": str(central.id), "target_warehouse_id": str(target.id),
    }):
        guard()

    for data in (
        {"source_warehouse_id": str(other_central.id), "target_warehouse_id": str(target.id)},
        {"source_warehouse_id": str(central.id), "target_warehouse_id": str(other_target.id)},
    ):
        with m.app.test_request_context("/inventory/transfers", method="POST", data=data):
            with pytest.raises(Forbidden):
                guard()


def test_global_user_needs_explicit_transfer_approval_permission(monkeypatch):
    branch, central, target, _other_central, _other_target = _branch_warehouses()
    transfer = m.StockTransfer(
        transfer_no="CODEX-UAT-TRANSFER-APPROVAL",
        source_warehouse_id=central.id,
        target_warehouse_id=target.id,
        status="REQUESTED",
    )
    m.db.session.add(transfer)
    m.db.session.flush()
    operator = doctor("inventory-transfer-unprivileged", "CALL_CENTER")
    operator.branch_id = None
    monkeypatch.setattr(m, "current_user", lambda: operator)
    monkeypatch.setattr(registration_policy, "allowed_registration_branches", lambda: None)
    monkeypatch.setattr(m, "has_perm", lambda permission: False)
    guard = _guard()
    route = next(rule for rule in m.app.url_map.iter_rules() if rule.endpoint == "inventory_transfer_approve")
    path = route.rule.replace("<int:transfer_id>", str(transfer.id))

    with m.app.test_request_context(path, method="POST"):
        with pytest.raises(Forbidden):
            guard()

    monkeypatch.setattr(m, "has_perm", lambda permission: permission == "inventory.transfer.approve")
    with m.app.test_request_context(path, method="POST"):
        guard()
