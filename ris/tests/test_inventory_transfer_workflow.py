from types import SimpleNamespace

import pytest

from application.services.inventory.transfer_workflow import (
    StockTransferWorkflow,
    TransferWorkflowError,
)


class FakeRepository:
    def __init__(self, lines=(), available=None, lots=None):
        self.lines = list(lines)
        self.available = dict(available or {})
        self.lots = dict(lots or {})
        self.moves = []

    def lines_for_transfer(self, transfer_id):
        return self.lines

    def available_qty(self, warehouse_id, item_id):
        return self.available.get((warehouse_id, item_id), 0)

    def stock_lots(self, warehouse_id, item_id):
        return self.lots.get((warehouse_id, item_id), [])

    def untracked_target_lot(self, warehouse_id, item_id):
        return SimpleNamespace(id=f"target-{warehouse_id}-{item_id}")

    def move(self, *args, **kwargs):
        self.moves.append((args, kwargs))


def _workflow(repository):
    audit = []
    return StockTransferWorkflow(repository, lambda *event: audit.append(event)), audit


def _transfer(status="REQUESTED"):
    return SimpleNamespace(
        id=21,
        transfer_no="TR-SYNTHETIC-21",
        status=status,
        notes="initial request",
        source_warehouse=SimpleNamespace(id=1),
        target_warehouse=SimpleNamespace(id=2),
    )


def test_approve_and_reject_enforce_state_and_emit_audit():
    workflow, audit = _workflow(FakeRepository())
    transfer = _transfer()
    when = object()

    workflow.approve(transfer, actor_id=7, occurred_at=when)
    assert (transfer.status, transfer.approved_by, transfer.approved_at) == ("APPROVED", 7, when)
    assert audit == [("STOCK_TRANSFER_APPROVED", "stock_transfer", 21, "TR-SYNTHETIC-21")]
    with pytest.raises(TransferWorkflowError, match="Only requested transfers"):
        workflow.approve(transfer, actor_id=8, occurred_at=when)

    workflow.reject(transfer, actor_id=8, occurred_at=when, reason="stock count mismatch")
    assert transfer.status == "REJECTED"
    assert transfer.notes.endswith("REJECT: stock count mismatch")
    assert audit[-1] == ("STOCK_TRANSFER_REJECTED", "stock_transfer", 21, "TR-SYNTHETIC-21")


def test_dispatch_checks_every_line_before_any_stock_movement():
    first = SimpleNamespace(item_id=11, item=SimpleNamespace(name="First"), qty_requested=2, qty_dispatched=0)
    second = SimpleNamespace(item_id=12, item=SimpleNamespace(name="Second"), qty_requested=4, qty_dispatched=0)
    repo = FakeRepository([first, second], available={(1, 11): 2, (1, 12): 3})
    workflow, audit = _workflow(repo)
    transfer = _transfer("APPROVED")

    with pytest.raises(ValueError, match="Insufficient stock for Second"):
        workflow.dispatch(transfer, actor_id=7, occurred_at=object())
    assert repo.moves == []
    assert transfer.status == "APPROVED"
    assert audit == []


def test_dispatch_allocates_available_lots_and_records_transition():
    item = SimpleNamespace(name="Contrast")
    line = SimpleNamespace(item_id=11, item=item, qty_requested=4, qty_dispatched=0)
    lots = [
        SimpleNamespace(qty_on_hand=3, qty_reserved=1),
        SimpleNamespace(qty_on_hand=5, qty_reserved=0),
    ]
    repo = FakeRepository([line], available={(1, 11): 7}, lots={(1, 11): lots})
    workflow, audit = _workflow(repo)
    transfer = _transfer("APPROVED")
    when = object()

    workflow.dispatch(transfer, actor_id=7, occurred_at=when)

    assert line.qty_dispatched == 4
    assert [move[0][2] for move in repo.moves] == [-2, -2]
    assert transfer.status == "DISPATCHED"
    assert (transfer.dispatched_by, transfer.dispatched_at) == (7, when)
    assert audit == [("STOCK_TRANSFER_DISPATCHED", "stock_transfer", 21, "TR-SYNTHETIC-21")]


def test_receive_posts_only_dispatched_quantities_and_keeps_status_gate():
    item = SimpleNamespace(name="Contrast")
    received = SimpleNamespace(item_id=11, item=item, qty_dispatched=3, qty_received=0)
    empty = SimpleNamespace(item_id=12, item=SimpleNamespace(name="Empty"), qty_dispatched=0, qty_received=0)
    repo = FakeRepository([received, empty])
    workflow, audit = _workflow(repo)
    transfer = _transfer("DISPATCHED")
    when = object()

    workflow.receive(transfer, actor_id=9, occurred_at=when)

    assert len(repo.moves) == 1
    assert repo.moves[0][0][2:4] == (3, "TRANSFER_IN")
    assert received.qty_received == 3
    assert empty.qty_received == 0
    assert transfer.status == "RECEIVED"
    assert (transfer.received_by, transfer.received_at) == (9, when)
    assert audit == [("STOCK_TRANSFER_RECEIVED", "stock_transfer", 21, "TR-SYNTHETIC-21")]
    with pytest.raises(TransferWorkflowError, match="Only dispatched transfers"):
        workflow.receive(transfer, actor_id=9, occurred_at=when)
