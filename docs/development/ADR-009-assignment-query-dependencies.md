# ADR 009: Explicit assignment query dependencies

Date: 2026-10-11. Status: implemented on the development branch.

## Decision

The distribution policy snapshot, active-case count and doctor capacity now execute through `AssignmentQueries`. The application service depends on an explicit repository protocol and default rules. It imports neither Flask, SQLAlchemy, infrastructure nor the composition root.

`SqlAlchemyAssignmentQueryRepository` receives its session and model classes explicitly. It owns the existing read queries, preserving the policy record key, active-assignment predicate, order/report terminal exclusions and missing-profile behavior. It performs no commit, rollback or mutation.

The remaining distribution entry points are explicitly owned by `web.compatibility.assignment_distribution`. Both former import paths alias that same module so caller and monkeypatch identity remain intact. At the compatibility edge, `_queries()` selects the clinical runtime and supplies the repository to the service. This is deliberately an incremental migration: ranking, special qualifications, visit grouping and start/reclaim orchestration still use their existing compatibility interfaces.

## Validation

The new service imports in a subprocess without Flask, SQLAlchemy or the legacy runtime. Tests use separate injected repositories and actual SQLAlchemy sessions against two independent synthetic databases outside a Flask context. Runtime resolution is replaced with a failing stub in that adapter test, proving these queries do not need it. Existing distribution tests exercise the live compatibility callers, capacity enforcement, pending offers and immutable deadline snapshots.

The schema and route snapshot remains identical at 160 tables and 546 registrations. Full CI remains required on the committed revision, along with the release and integration gates in IMPLEMENTATION_STATUS.md.

## Consequences

The service is usable directly with any repository satisfying its read contract. Existing entry points continue to work during migration. No new endpoint, permission, database migration or production configuration is introduced. This does not complete the assignment use-case refactor or remove all compatibility dependencies.
