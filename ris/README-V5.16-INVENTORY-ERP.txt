RIS Web v5.16 — Inventory & ERP Integration

Inventory Master:
- Generic default consumable catalog with fixed codes/barcodes.
- English/Arabic names, category, unit, current stock, reorder level, unit cost, selling price.
- Expiry tracking switch.
- Batch/Lot and expiry records.
- Stock Movement ledger.
- Nursing actual use and corrections create auditable stock movements.

Import/Export:
- CSV export/import.
- XLSX export/import.
- Downloadable XLSX import template.
- Import updates existing items by Code and creates missing items.

ERP:
- Generic ERP Item Mapping (RIS item code -> ERP item code / warehouse).
- Reliable ERPSyncQueue with PENDING / SENT / FAILED / attempts / error.
- Item Master sync.
- Stock Movement events queued to ERP when ERP_SYNC_ENABLED=1.
- Generic endpoint contract: POST {ERP_BASE_URL}/ris/events
- Bearer API token supported.
- Designed for SAP/Odoo adapters without coupling the RIS core to a vendor.

Environment:
ERP_SYNC_ENABLED=0
ERP_PROVIDER=GENERIC
ERP_BASE_URL=
ERP_API_TOKEN=
ERP_TIMEOUT=15
