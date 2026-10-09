RIS v5.27.2 Inventory & Consumables Control

Built on v5.27.1 Finance Rules & Approvals.

Adds:
- Main / Branch / Sub-store warehouses.
- Item catalog with unit cost, lot/batch and expiry tracking.
- Warehouse stock by lot; on-hand / reserved / available.
- Min / Reorder / Target stock policies and low-stock alerts.
- Inter-warehouse transfer workflow:
  Request -> Approve -> Dispatch -> Receive / Reject.
- Default consumables per procedure.
- Case consumables from branch warehouse.
- Nursing/Technician can record Used, Extra, Waste and Return according to permissions.
- Extra consumable and Waste/Return require reasons.
- FEFO-like lot selection for stock consumption.
- Immutable Stock Movement Ledger.
- Consumables Usage / Cost Report.
- Optional copy of existing legacy Consumable catalog into multi-warehouse catalog.
- Order screen shows branch warehouse and actual consumable cost.

Inventory permissions:
inventory.view
inventory.consume
inventory.add_extra_consumable
inventory.adjust_quantity
inventory.waste
inventory.return
inventory.transfer.request
inventory.transfer.approve
inventory.transfer.dispatch
inventory.transfer.receive
inventory.manage
inventory.reports

All v5.27.1 finance rules and v5.26 Golden RIS hotfixes are preserved.
