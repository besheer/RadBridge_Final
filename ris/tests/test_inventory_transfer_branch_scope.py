import json
from uuid import uuid4

import app as m


def test_branch_transfer_scope_and_central_approval(app_ctx):
    suffix = uuid4().hex[:8].upper()
    own_branch = m.Branch(code=f"TB{suffix}", name=f"Transfer branch {suffix}", active=True)
    other_branch = m.Branch(code=f"TO{suffix}", name=f"Other transfer branch {suffix}", active=True)
    m.db.session.add_all([own_branch, other_branch])
    m.db.session.flush()
    main = m.Warehouse(
        code=f"TM{suffix}", name=f"Central {suffix}", warehouse_type="MAIN",
        branch_id=None, active=True,
    )
    unrelated_main = m.Warehouse(
        code=f"TU{suffix}", name=f"Unrelated central {suffix}", warehouse_type="MAIN",
        branch_id=None, active=True,
    )
    own = m.Warehouse(
        code=f"TW{suffix}", name=f"Own target {suffix}", warehouse_type="BRANCH",
        branch_id=own_branch.id, active=True,
    )
    foreign = m.Warehouse(
        code=f"TF{suffix}", name=f"Foreign target {suffix}", warehouse_type="BRANCH",
        branch_id=other_branch.id, active=True,
    )
    wrong_source = m.Warehouse(
        code=f"TS{suffix}", name=f"Own substore {suffix}", warehouse_type="SUBSTORE",
        branch_id=own_branch.id, active=True,
    )
    item = m.InventoryItem(code=f"TI{suffix}", name=f"Transfer item {suffix}", active=True)
    m.db.session.add_all([main, unrelated_main, own, foreign, wrong_source, item])
    m.db.session.flush()
    own.parent_id = main.id
    wrong_source.parent_id = main.id
    m.db.session.flush()
    own_transfer = m.StockTransfer(
        transfer_no=f"TR-OWN-{suffix}", source_warehouse_id=main.id,
        target_warehouse_id=own.id, status="REQUESTED",
    )
    foreign_transfer = m.StockTransfer(
        transfer_no=f"TR-FOREIGN-{suffix}", source_warehouse_id=main.id,
        target_warehouse_id=foreign.id, status="REQUESTED",
    )
    m.db.session.add_all([own_transfer, foreign_transfer])
    branch_role = m.Role(
        code=f"TRB{suffix}", name="Branch transfer requester",
        permissions_json=json.dumps([
            "inventory.view", "inventory.transfer.request", "inventory.transfer.approve",
            "inventory.transfer.dispatch", "inventory.transfer.receive",
        ]),
    )
    central_role = m.Role.query.filter_by(code="MANAGEMENT").first()
    created_central_role = central_role is None
    if created_central_role:
        central_role = m.Role(
            code="MANAGEMENT", name="Management",
            permissions_json=json.dumps(["inventory.view", "inventory.transfer.approve"]),
        )
    branch_user = m.User(
        username=f"transfer-branch-{suffix}", full_name="Transfer branch user",
        password_hash="DISABLED-SYNTHETIC", role=branch_role,
        branch_id=own_branch.id, active=True,
    )
    central_user = m.User(
        username=f"transfer-central-{suffix}", full_name="Transfer central user",
        password_hash="DISABLED-SYNTHETIC", role=central_role,
        branch_id=None, active=True,
    )
    m.db.session.add_all([branch_role, branch_user, central_user])
    if created_central_role:
        m.db.session.add(central_role)
    m.db.session.flush()
    branch_client = m.app.test_client()
    with branch_client.session_transaction() as state:
        state["uid"] = branch_user.id

    try:
        listing = branch_client.get("/inventory/transfers")
        assert listing.status_code == 200
        assert own_transfer.transfer_no.encode() in listing.data
        assert foreign_transfer.transfer_no.encode() not in listing.data
        assert main.name.encode() in listing.data
        assert unrelated_main.name.encode() not in listing.data
        assert own.name.encode() in listing.data
        assert foreign.name.encode() not in listing.data

        assert branch_client.get(
            f"/inventory/transfers/{foreign_transfer.id}"
        ).status_code == 403
        assert branch_client.post(
            f"/inventory/transfers/{own_transfer.id}/approve"
        ).status_code == 403
        assert branch_client.post(
            f"/inventory/transfers/{own_transfer.id}/reject",
            data={"reason": "synthetic branch approval denial"},
        ).status_code == 403
        assert branch_client.post(
            f"/inventory/transfers/{own_transfer.id}/dispatch"
        ).status_code == 403
        assert own_transfer.status == "REQUESTED"

        invalid_source = branch_client.post(
            "/inventory/transfers",
            data={"source_warehouse_id": wrong_source.id, "target_warehouse_id": own.id,
                  "item_id": item.id, "qty": "1"},
        )
        assert invalid_source.status_code == 403
        unrelated_source = branch_client.post(
            "/inventory/transfers",
            data={"source_warehouse_id": unrelated_main.id, "target_warehouse_id": own.id,
                  "item_id": item.id, "qty": "1"},
        )
        assert unrelated_source.status_code == 403
        foreign_target = branch_client.post(
            "/inventory/transfers",
            data={"source_warehouse_id": main.id, "target_warehouse_id": foreign.id,
                  "item_id": item.id, "qty": "1"},
        )
        assert foreign_target.status_code == 403

        created = branch_client.post(
            "/inventory/transfers",
            data={"source_warehouse_id": main.id, "target_warehouse_id": own.id,
                  "item_id": item.id, "qty": "1"},
        )
        assert created.status_code == 302
        created_transfer = m.StockTransfer.query.filter_by(
            source_warehouse_id=main.id, target_warehouse_id=own.id,
            requested_by=branch_user.id,
        ).order_by(m.StockTransfer.id.desc()).first()
        assert created_transfer is not None
        assert created_transfer.status == "REQUESTED"

        central_client = m.app.test_client()
        with central_client.session_transaction() as state:
            state["uid"] = central_user.id
        approved = central_client.post(f"/inventory/transfers/{own_transfer.id}/approve")
        assert approved.status_code == 302
        m.db.session.expire_all()
        assert m.StockTransfer.query.filter_by(id=own_transfer.id).one().status == "APPROVED"
        assert m.AuditLog.query.filter_by(
            action="STOCK_TRANSFER_APPROVED", entity="stock_transfer",
            entity_id=str(own_transfer.id),
        ).count() == 1
        assert m.AuditLog.query.filter_by(
            action="STOCK_TRANSFER_REQUEST", entity="stock_transfer",
            entity_id=str(created_transfer.id),
        ).count() == 1
    finally:
        m.db.session.rollback()
        transfer_ids = [own_transfer.id, foreign_transfer.id]
        created_transfer = locals().get("created_transfer")
        if created_transfer is not None:
            transfer_ids.append(created_transfer.id)
        m.AuditLog.query.filter(
            m.AuditLog.entity == "stock_transfer",
            m.AuditLog.entity_id.in_([str(transfer_id) for transfer_id in transfer_ids]),
        ).delete(synchronize_session=False)
        m.StockTransferLine.query.filter(
            m.StockTransferLine.transfer_id.in_(transfer_ids)
        ).delete(synchronize_session=False)
        m.StockTransfer.query.filter(m.StockTransfer.id.in_(transfer_ids)).delete(
            synchronize_session=False
        )
        m.UserProfile.query.filter(
            m.UserProfile.user_id.in_([branch_user.id, central_user.id])
        ).delete(synchronize_session=False)
        m.User.query.filter(m.User.id.in_([branch_user.id, central_user.id])).delete(
            synchronize_session=False
        )
        m.Role.query.filter_by(id=branch_role.id).delete(synchronize_session=False)
        if created_central_role:
            m.Role.query.filter_by(id=central_role.id).delete(synchronize_session=False)
        m.Warehouse.query.filter(
            m.Warehouse.id.in_([main.id, unrelated_main.id, own.id, foreign.id, wrong_source.id])
        ).delete(
            synchronize_session=False
        )
        m.InventoryItem.query.filter_by(id=item.id).delete(synchronize_session=False)
        m.Branch.query.filter(m.Branch.id.in_([own_branch.id, other_branch.id])).delete(
            synchronize_session=False
        )
        m.db.session.commit()
