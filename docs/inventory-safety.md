Inventory issue/return safety — 2026-10-07

Unexpired available stock excludes lots whose expiry_date is before the current
server date; today's expiry remains usable. Null expiry remains allowed under
existing rules. Physical on-hand totals retain expired lots for reconciliation.
Consumption validates finite positive quantity, locks the order and eligible lot
rows, subtracts reserved stock, and prechecks total availability before mutation.
The existing FEFO order, usage/movement entries and caller transaction ownership
are preserved. No source image, clinical order status or price is modified.

Returns are bounded by net USED/EXTRA issued quantities for the same order/item/
warehouse and original lot/cost. Existing RETURN quantities reduce that credit.
WASTE is not returnable. Missing/mismatched historic lot provenance fails closed
for inventory review. Split returns preserve original lot IDs, expiry and unit
cost; they never create a blank replacement lot. Restoring an expired original
lot does not make it usable. The existing return function still returns a usage
row; callers ignore it, while a split return may create multiple usage records.

21 isolated ORM tests cover expiration, reservations, insufficiency without partial
mutation, invalid/tiny quantities, repeated/excess/cross-case returns, multiple
lots/costs, and waste. PostgreSQL locks are used by the helpers; SQLite tests do
not prove concurrent behavior with all other inventory receipt/transfer writers.
No real live inventory transactions submitted for UAT. No migration or automatic
cleanup of historical usage. Visual browser review pending tool recovery.
