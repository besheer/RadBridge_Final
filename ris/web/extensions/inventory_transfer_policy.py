"""Branch and central authority boundaries for stock transfers."""

from flask import abort, current_app, g, has_request_context, request
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session, with_loader_criteria


TRANSFER_ENDPOINTS = frozenset({
    "inventory_transfers", "inventory_transfer_detail", "inventory_transfer_approve",
    "inventory_transfer_reject", "inventory_transfer_dispatch", "inventory_transfer_receive",
})
CENTRAL_ACTIONS = frozenset({
    "inventory_transfer_approve", "inventory_transfer_reject", "inventory_transfer_dispatch",
})


def register(m):
    from registration_policy import allowed_registration_branches

    @m.app.context_processor
    def transfer_template_context():
        if request.endpoint != "inventory_transfers":
            return {}
        branch_scope = allowed_registration_branches()
        branch_ids = tuple(branch_scope or ())
        parent_ids = select(m.Warehouse.parent_id).where(
            m.Warehouse.warehouse_type == "BRANCH",
            m.Warehouse.active.is_(True),
            m.Warehouse.parent_id.is_not(None),
            m.Warehouse.branch_id.in_(branch_ids) if branch_ids else m.db.false(),
        )
        source_warehouses = m.Warehouse.query.filter(
            m.Warehouse.active.is_(True),
            m.Warehouse.warehouse_type == "MAIN",
            m.Warehouse.branch_id.is_(None),
            m.Warehouse.id.in_(parent_ids),
        ).order_by(m.Warehouse.name).all()
        target_warehouses = m.Warehouse.query.filter(
            m.Warehouse.active.is_(True),
            m.Warehouse.warehouse_type == "BRANCH",
            m.Warehouse.branch_id.in_(branch_ids) if branch_ids else m.db.false(),
        ).order_by(m.Warehouse.name).all()
        return {
            "source_warehouses": source_warehouses,
            "target_warehouses": target_warehouses,
            "is_central_transfer_operator": getattr(g, "rb_inventory_transfer_central", False),
        }

    def linked_central_ids(branch_ids=None):
        children = select(m.Warehouse.parent_id).where(
            m.Warehouse.warehouse_type == "BRANCH",
            m.Warehouse.branch_id.is_not(None),
            m.Warehouse.parent_id.is_not(None),
            m.Warehouse.active.is_(True),
        )
        if branch_ids is not None:
            children = children.where(m.Warehouse.branch_id.in_(branch_ids))
        return select(m.Warehouse.id).where(
            m.Warehouse.id.in_(children),
            m.Warehouse.warehouse_type == "MAIN",
            m.Warehouse.branch_id.is_(None),
            m.Warehouse.active.is_(True),
        )

    def target_ids(branch_ids=None):
        query = select(m.Warehouse.id).where(
            m.Warehouse.warehouse_type == "BRANCH",
            m.Warehouse.active.is_(True),
            m.Warehouse.branch_id.is_not(None),
        )
        if branch_ids is not None:
            query = query.where(m.Warehouse.branch_id.in_(branch_ids))
        return query

    def valid_transfer_ids(branch_ids=None):
        target_parent_id = select(m.Warehouse.parent_id).where(
            m.Warehouse.id == m.StockTransfer.target_warehouse_id,
            m.Warehouse.warehouse_type == "BRANCH",
            m.Warehouse.active.is_(True),
        ).scalar_subquery()
        return select(m.StockTransfer.id).where(
            m.StockTransfer.source_warehouse_id.in_(linked_central_ids(branch_ids)),
            m.StockTransfer.target_warehouse_id.in_(target_ids(branch_ids)),
            m.StockTransfer.source_warehouse_id == target_parent_id,
        )

    def guard():
        endpoint = request.endpoint or ""
        if endpoint not in TRANSFER_ENDPOINTS:
            return
        user = m.current_user()
        if not user or not user.active:
            abort(403)
        allowed = allowed_registration_branches()
        central = not user.branch_id and m.has_perm("inventory.transfer.approve")
        g.rb_inventory_transfer_central = central
        g.rb_inventory_transfer_branch_ids = None if central else tuple(allowed or ())

        if request.method == "POST" and endpoint == "inventory_transfers":
            if central or not allowed:
                abort(403)
            source_id = request.form.get("source_warehouse_id", type=int)
            target_id = request.form.get("target_warehouse_id", type=int)
            permitted_source = m.Warehouse.query.filter(
                m.Warehouse.id == source_id,
                m.Warehouse.id.in_(linked_central_ids(allowed)),
            ).first() if source_id else None
            permitted_target = m.Warehouse.query.filter(
                m.Warehouse.id == target_id,
                m.Warehouse.warehouse_type == "BRANCH",
                m.Warehouse.branch_id.in_(allowed),
                m.Warehouse.active.is_(True),
                m.Warehouse.parent_id == source_id,
            ).first() if target_id else None
            if not permitted_source or not permitted_target:
                abort(403)
        elif endpoint in CENTRAL_ACTIONS:
            if not central:
                abort(403)
        elif endpoint == "inventory_transfer_receive":
            if central or not allowed:
                abort(403)

        transfer_id = (request.view_args or {}).get("transfer_id")
        if transfer_id is not None:
            ids = valid_transfer_ids(None if central else allowed)
            row = m.StockTransfer.query.filter(
                m.StockTransfer.id == transfer_id,
                m.StockTransfer.id.in_(ids),
            ).first()
            if row is None:
                abort(403)
            if endpoint == "inventory_transfer_receive" and row.target_warehouse.branch_id not in allowed:
                abort(403)

    m.app.before_request_funcs.setdefault(None, []).insert(1, guard)

    @m.app.teardown_request
    def clear_transfer_context(error=None):
        g.pop("rb_inventory_transfer_central", None)
        g.pop("rb_inventory_transfer_branch_ids", None)

    def restrict_transfer_queries(state):
        if (not has_request_context() or current_app._get_current_object() is not m.app
                or request.endpoint not in TRANSFER_ENDPOINTS or not state.is_select
                or not state.is_orm_statement):
            return
        branch_ids = getattr(g, "rb_inventory_transfer_branch_ids", ())
        central = bool(getattr(g, "rb_inventory_transfer_central", False))
        visible = valid_transfer_ids(None if central else branch_ids)
        options = [
            with_loader_criteria(m.StockTransfer, m.StockTransfer.id.in_(visible), include_aliases=True),
            with_loader_criteria(m.StockTransferLine, m.StockTransferLine.transfer_id.in_(visible), include_aliases=True),
        ]
        if central:
            warehouses = select(m.Warehouse.id).where(
                m.Warehouse.id.in_(linked_central_ids()),
                m.Warehouse.warehouse_type == "MAIN",
                m.Warehouse.branch_id.is_(None),
            ).union(target_ids())
        else:
            warehouses = select(m.Warehouse.id).where(
                m.Warehouse.branch_id.in_(branch_ids),
                m.Warehouse.warehouse_type == "BRANCH",
            ).union(linked_central_ids(branch_ids))
        options.append(with_loader_criteria(m.Warehouse, m.Warehouse.id.in_(warehouses), include_aliases=True))
        state.statement = state.statement.options(*options)

    from sqlalchemy import event
    event.listen(Session, "do_orm_execute", restrict_transfer_queries)
    m.app.extensions.setdefault("radbridge_orm_listeners", []).append(
        (Session, "do_orm_execute", restrict_transfer_queries)
    )
