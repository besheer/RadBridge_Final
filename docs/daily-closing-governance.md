Daily closing governance — 2026-10-07

Read: active cashier.workstation or financial.view, assigned branch unless an
explicit global administrator. Write: cashier.workstation only. Reception keeps
its existing branch reception_collection_enabled check; no permissions granted.
Order viewing does not confer any closing authority.

Serialize POST requests by locking the active Branch row, including first-row
creation, then locking the latest DailyClosing. CLOSED rows are immutable even
to administrators. GET displays saved figures for CLOSED rows. Saves and closes
record before/after AuditLog entries in the same transaction. Invalid dates,
actions and non-finite counted amounts are rejected before mutation.

Expected movement is receipts less PaymentRefund records by their respective
created_at dates, with branch filtering and Decimal arithmetic. REFUNDED and
PARTIAL_REFUND receipts retain their original amount; refund rows subtract the
movement once. Refund bucket uses the original receipt method because the
existing model has no independent refund payment method. Existing timestamp/day
convention is preserved. Accounting errors propagate instead of silently returning
zero. No opening cash balance, cash-to-card transfer, posted period reassignment,
or freeze of subsequent receipt/refund operations is introduced by this fix.

The bilingual screen labels NET amounts, shows CLOSED/read-only status and removes
save/close controls when unauthorized or closed. No schema changes or live
financial test writes. 32 new isolated role/ORM/date/HTML tests; full regression,
image tests and read-only runtime acceptance must pass. Native browser visual
UAT is pending because the browser tool cannot initialize its kernel assets.
