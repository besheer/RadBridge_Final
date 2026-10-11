# ADR 025: Collection access and accounting evidence

Status: implemented on the isolated development branch; full CI required.

Collection access uses an explicit branch repository. Active reception users need their own active branch's collection setting; cashiers remain restricted to their branch. This narrow check preserves the original behavior for other active roles: their route permission gate remains authoritative. The service does not grant financial permissions, alter roles or enable collection settings. Legacy abort/runtime resolution stays at the compatibility edge.

Closing totals use an explicit session/model repository for receipts and refunds, half-open accounting-day timestamps and optional branch filtering. Decimal validation, method buckets and net arithmetic belong to the domain layer. A refund uses its original receipt's method and must reference the same order; query/reconciliation failures propagate instead of producing a zero balance. The original decimal quantization behavior is retained.

The daily closing page belongs to the web extension, preserving branch/permission decisions, branch/closing row locks, counted-amount handling, CLOSED snapshot immutability, audit and caller commits. These mutation and transaction orchestration dependencies are still unfinished; separating evidence totals does not complete the daily closing workflow.

Validation: 91 focused SQLite tests passed across evidence ports, actual closing routes, replacement settlements and facade ownership. New direct tests check branch activation/settings, accounting timestamps, original refund buckets, decimal arithmetic and invalid/refund mismatch failures. The PostgreSQL finance suite adds these files and the existing closing governance tests. Their fixture now uses bounded synthetic branch codes and a persisted synthetic cashier actor, creating its test role if absent; all original role/branch/closed/amount assertions remain. The operations snapshot commit `1f72b68bcffb51e0b197795bd265de9cf06680b6` passed all nine jobs (run 38166865498). New schema/route and full CI gates remain required.
