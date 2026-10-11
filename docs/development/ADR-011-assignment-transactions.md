# ADR 011: Explicit assignment transaction dependencies

Date: 2026-10-11. Status: implemented on the development branch.

## Decision

`application.services.assignment.assignment_transaction` owns assignment and offer-acceptance orchestration. It receives a row repository and required qualification, deadline and automatic-visit policy callbacks. Offer acceptance receives explicit group-lock and visit-assignment callbacks. The service imports no Flask, SQLAlchemy, legacy runtime or infrastructure implementation.

`SqlAlchemyAssignmentRepository` owns the original row queries and locks. It receives session/model classes and performs flushes only. The caller retains commit/rollback and audit transaction ownership. Assignment ordering remains order lock, lifecycle check, report lock/check, doctor lock/check, qualification, active assignment lock, idempotency, automatic policy, offer cancellation and mutation. A terminal order fails before the report query. Offer acceptance preserves visit/order/offer locking and actor/expiry checks.

The two old import paths alias `web.compatibility.case_assignment_service`. Its signatures and exception/result identity remain compatible; helper entry points delegate to the same core and adapter. The edge supplies the current qualification and grouped-visit callbacks. Qualification evidence and grouped-visit orchestration still require separate application interfaces.

## Validation

The focused local suite passed 105 tests, including receiving/report barriers, coordinator assignment, distribution, visit grouping, import aliases and direct-port mutation/acceptance. A subprocess verifies that the core imports without Flask, SQLAlchemy or a clinical runtime. Direct-port tests verify idempotency, lifecycle failure before mutations, injected qualification/visit denial, and lock order.

CI now has separate PostgreSQL matrix jobs for clinical and assignment contracts, each with its own disposable database service. The assignment suite includes existing actual database tests for grouped visits and the assignment service, plus dependency/domain tests. Both use the guarded `radbridge_dev_test` database/user; no arbitrary targets are allowed in PostgreSQL mode. This is behavioral and lock-path coverage, not a claim that every race scenario has been rehearsed.

No schema migration, new permission, endpoint, production change or external delivery is introduced. Required clinical integration/browser/release gates remain in IMPLEMENTATION_STATUS.md.
