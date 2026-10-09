RIS v5.27.4 Executive Analytics

Adds a live management reporting layer without replacing the existing dashboard.

New route:
  /analytics/executive

Permission:
  analytics.executive.view

Filters:
  Date range, Branch, Modality, Assigned Doctor, Device, Contract.

KPIs:
  Total Exams, New Patients, Average TAT, Completion Rate, Revenue, Collected.

Charts (rendered locally with inline SVG/CSS/JS; no external CDN required):
  Daily Exams
  Exams by Modality
  Case Status
  Revenue Trend
  Branch Performance
  Top Doctors by Exam Volume
  Device Utilization by Exam Volume

All figures are calculated from current RIS database records. Device utilization is explicitly an exam-volume measure, not a capacity percentage.

Carried-forward fix:
  Stock Ledger ORDER BY uses WarehouseStockMovement.id.

All earlier Finance, Inventory, Nursing, Backup/Data Administration and RIS Studio functionality is preserved.
