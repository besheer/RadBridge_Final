"""Stock-transfer lifecycle orchestration with explicit movement/audit ports.

The web caller owns authorization and transaction commit/rollback. This service
owns allowed state transitions and dispatch/receipt orchestration.
"""


class TransferWorkflowError(ValueError):
    """A transfer cannot perform the requested lifecycle transition."""


class StockTransferWorkflow:
    error_type = TransferWorkflowError

    def __init__(self, repository, audit):
        self.repository = repository
        self.audit = audit

    def approve(self, transfer, *, actor_id, occurred_at):
        if transfer.status != "REQUESTED":
            raise TransferWorkflowError("Only requested transfers can be approved.")
        transfer.status = "APPROVED"
        transfer.approved_by = actor_id
        transfer.approved_at = occurred_at
        self._audit("STOCK_TRANSFER_APPROVED", transfer)
        return transfer

    def reject(self, transfer, *, actor_id, occurred_at, reason=""):
        if transfer.status not in ("REQUESTED", "APPROVED"):
            raise TransferWorkflowError("Transfer cannot be rejected at this stage.")
        transfer.status = "REJECTED"
        transfer.approved_by = actor_id
        transfer.approved_at = occurred_at
        transfer.notes = ((transfer.notes or "") + "\nREJECT: " + (reason or "")).strip()
        self._audit("STOCK_TRANSFER_REJECTED", transfer)
        return transfer

    def dispatch(self, transfer, *, actor_id, occurred_at):
        if transfer.status != "APPROVED":
            raise TransferWorkflowError("Transfer must be approved before dispatch.")
        source = transfer.source_warehouse
        lines = self.repository.lines_for_transfer(transfer.id)

        # Validate all lines before making any movement. The outer transaction
        # still rolls back every movement if a later inventory operation fails.
        for line in lines:
            qty = float(line.qty_requested or 0)
            if self.repository.available_qty(source.id, line.item_id) < qty - 1e-9:
                raise ValueError(f"Insufficient stock for {line.item.name}")

        for line in lines:
            remaining = float(line.qty_requested or 0)
            dispatched = 0
            for lot in self.repository.stock_lots(source.id, line.item_id):
                take = min(
                    max(0, float(lot.qty_on_hand or 0) - float(lot.qty_reserved or 0)),
                    remaining,
                )
                if take <= 0:
                    continue
                self.repository.move(
                    source,
                    line.item,
                    -take,
                    "TRANSFER_OUT",
                    lot=lot,
                    reference_type="TRANSFER",
                    reference_id=transfer.id,
                    notes=transfer.transfer_no,
                )
                dispatched += take
                remaining -= take
                if remaining <= 1e-9:
                    break
            line.qty_dispatched = dispatched

        transfer.status = "DISPATCHED"
        transfer.dispatched_by = actor_id
        transfer.dispatched_at = occurred_at
        self._audit("STOCK_TRANSFER_DISPATCHED", transfer)
        return transfer

    def receive(self, transfer, *, actor_id, occurred_at):
        if transfer.status != "DISPATCHED":
            raise TransferWorkflowError("Only dispatched transfers can be received.")
        target = transfer.target_warehouse
        for line in self.repository.lines_for_transfer(transfer.id):
            qty = float(line.qty_dispatched or 0)
            if qty <= 0:
                continue
            lot = self.repository.untracked_target_lot(target.id, line.item_id)
            self.repository.move(
                target,
                line.item,
                qty,
                "TRANSFER_IN",
                lot=lot,
                reference_type="TRANSFER",
                reference_id=transfer.id,
                notes=transfer.transfer_no,
            )
            line.qty_received = qty

        transfer.status = "RECEIVED"
        transfer.received_by = actor_id
        transfer.received_at = occurred_at
        self._audit("STOCK_TRANSFER_RECEIVED", transfer)
        return transfer

    def _audit(self, action, transfer):
        self.audit(action, "stock_transfer", transfer.id, transfer.transfer_no)
