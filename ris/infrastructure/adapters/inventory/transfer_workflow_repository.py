"""SQLAlchemy and legacy stock-movement adapter for transfer workflows."""


class SqlAlchemyStockTransferWorkflowRepository:
    def __init__(self, StockTransferLine, InventoryLot, available_qty, stock_lots, move):
        self.StockTransferLine = StockTransferLine
        self.InventoryLot = InventoryLot
        self._available_qty = available_qty
        self._stock_lots = stock_lots
        self._move = move

    def lines_for_transfer(self, transfer_id):
        return self.StockTransferLine.query.filter_by(transfer_id=transfer_id).all()

    def available_qty(self, warehouse_id, item_id):
        return self._available_qty(warehouse_id, item_id)

    def stock_lots(self, warehouse_id, item_id):
        return self._stock_lots(warehouse_id, item_id)

    def untracked_target_lot(self, warehouse_id, item_id):
        return self.InventoryLot.query.filter_by(
            item_id=item_id, warehouse_id=warehouse_id, lot_no=""
        ).first()

    def move(self, *args, **kwargs):
        return self._move(*args, **kwargs)
