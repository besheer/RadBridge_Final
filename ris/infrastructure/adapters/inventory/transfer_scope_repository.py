"""SQLAlchemy query construction for central-to-branch stock-transfer scope."""

from sqlalchemy import select


class SqlAlchemyStockTransferScopeRepository:
    def __init__(self, Warehouse, StockTransfer):
        self.Warehouse = Warehouse
        self.StockTransfer = StockTransfer

    def linked_central_ids(self, branch_ids=None):
        Warehouse = self.Warehouse
        children = select(Warehouse.parent_id).where(
            Warehouse.warehouse_type == "BRANCH",
            Warehouse.branch_id.is_not(None),
            Warehouse.parent_id.is_not(None),
            Warehouse.active.is_(True),
        )
        if branch_ids is not None:
            children = children.where(Warehouse.branch_id.in_(branch_ids))
        return select(Warehouse.id).where(
            Warehouse.id.in_(children),
            Warehouse.warehouse_type == "MAIN",
            Warehouse.branch_id.is_(None),
            Warehouse.active.is_(True),
        )

    def target_ids(self, branch_ids=None):
        Warehouse = self.Warehouse
        query = select(Warehouse.id).where(
            Warehouse.warehouse_type == "BRANCH",
            Warehouse.active.is_(True),
            Warehouse.branch_id.is_not(None),
        )
        if branch_ids is not None:
            query = query.where(Warehouse.branch_id.in_(branch_ids))
        return query

    def valid_transfer_ids(self, branch_ids=None):
        Warehouse = self.Warehouse
        StockTransfer = self.StockTransfer
        target_parent_id = select(Warehouse.parent_id).where(
            Warehouse.id == StockTransfer.target_warehouse_id,
            Warehouse.warehouse_type == "BRANCH",
            Warehouse.active.is_(True),
        ).scalar_subquery()
        return select(StockTransfer.id).where(
            StockTransfer.source_warehouse_id.in_(self.linked_central_ids(branch_ids)),
            StockTransfer.target_warehouse_id.in_(self.target_ids(branch_ids)),
            StockTransfer.source_warehouse_id == target_parent_id,
        )
