# ADR 026: Daily closing mutation dependencies

Status: implemented on the isolated development branch; full CI required.

Daily closing saving/finalization now receives explicit authorization, repository, audit and clock dependencies. It authorizes before persistence, locks the active branch before selecting/locking the latest daily closing (also serializing first creation), rejects CLOSED rows, retrieves authoritative receipt/refund evidence, validates counted amounts, persists the snapshot, flushes and emits the original audit payload. Caller commit/rollback remains at the web edge.

The existing page still owns GET composition, branch selection, error/redirect presentation and the initial branch/closing locks. Its save composition rechecks actor activity, cashier permission and branch/global access through the same authoritative runtime permissions. The application service re-locks and rechecks the authoritative row before mutation. This redundant lock/read boundary protects callers from stale page objects without changing schema or reopening a closed day. Expected amounts are recomputed under that locked context, not accepted from client input.

No SAVE/CLOSE operation changes receipts/refunds, grants a role, overwrites a CLOSED snapshot, or commits inside the service. An exception leaves rollback to the caller; no success audit is issued after a failed flush. Broader cash receipt/disbursement/refund workflow dependencies and unit-of-work error presentation remain unfinished.

Validation: 98 focused SQLite tests passed across direct closing/evidence ports, actual closing routes, settlement workflows and facade identity. New tests cover authorization before queries, branch-before-closing lock ordering, immutable CLOSED barriers, invalid counts/actions, before/after audit snapshots and failed flush. PostgreSQL finance includes the new dependency file alongside persisted route governance. Structural and new full CI gates remain required.
