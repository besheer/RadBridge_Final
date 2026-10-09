# Physician FINAL workload counts — 8 October 2026

GET `/coordinator/physician-final-counts` provides aggregate workload by physician and branch, filtered by an inclusive date range and optional physician/branch. Available from the navigation for `reports.coordinate` or `finance.doctor_share.view`. Users must be active; users without wildcard access must have a fixed branch and cannot select another branch. Lists include only physicians in the permitted workload, including inactive historical physicians.

Original cases require both Order and Report FINAL and a Report.finalized_at inside the selected range. A case counts once for Order.assigned_doctor_id. Existing FINAL assignment protections and independent correction records preserve this original attribution. ReportVersion rows do not participate in this query. Records without an assigned physician remain explicitly unspecified.

Correction work uses ReportRevision.status FINAL, ReportRevision.finalized_at and its separate doctor_id. Distinct corrected orders and distinct finalized revision IDs are shown separately. Repeated corrections never increase original case counts. Their dates can fall outside the original case's reporting period. Counts do not use appointments or report last-updated timestamps.

The report does not modify records, files, accounting entries, existing earnings rules or settlement amounts. Replacement consultant compensation remains a separately unresolved policy. No database migration is needed. The existing earnings page remains distinct from this workload report.

Validation: 15 new isolated tests; full RIS suite 1456 passed. Tests cover multiple original versions, repeated corrections, date boundaries, branch tampering, wildcard scope, unauthorized/inactive/branchless users, invalid filters, historical physicians, real template rendering and read-only behavior. All test records and databases are isolated from clinical data.

Pending: full browser acceptance of this report and remaining historical UI backlog; consultant compensation policy; other items in RadBridge-Remaining-Requests-20261006.txt.
