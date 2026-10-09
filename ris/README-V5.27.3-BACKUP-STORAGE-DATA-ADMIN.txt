RIS v5.27.3 Backup, Storage & Data Administration

Security design:
- Dedicated permissions for backup/storage/export/anonymize/delete/reset/purge.
- Destructive actions require exact typed confirmation.
- Every export/anonymize/delete/reset operation is audit logged.
- Direct patient deletion is blocked when dependent Orders exist.
- Bulk clinical/financial/inventory/audit reset is intentionally blocked in this release.
- Anonymization preserves clinical/order history while removing identifying demographics.
- Patient ZIP export uses DB-linked files only; it does not crawl arbitrary server directories.
- Storage page shows configured paths, existence, writability and size.
- Web UI does NOT embed PostgreSQL passwords or run pg_dump with secrets.
- Backup manifest includes SHA-256 metadata; database backup should be performed by a server-side scheduled job.

Carried-forward hotfixes:
- New multi-warehouse StockMovement renamed WarehouseStockMovement / warehouse_stock_movement.
- Existing legacy StockMovement preserved.
- Nursing inventory context passed explicitly to template.
- Extra Consumables block placed inside content block.
- v5.27.2.2 automatic Main/Branch warehouse creation preserved.
