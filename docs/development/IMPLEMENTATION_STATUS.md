# Architecture implementation and remaining gates

Date: 2026-10-12. Scope: isolated development source on `refactor/development-foundation`, draft PR #1. Main and production have not been modified. Clinical release metadata remains 5.46.9; these changes are not a deployed clinical release.

## Implemented ownership

- All 160 persisted models belong to 14 infrastructure model modules; the SQLAlchemy extension is unbound until application composition.
- All 949 extracted functions have executable owners in 32 component/route/helper modules. Eighty HTTP-dependent installers were assigned to web ownership without changing their handler bodies.
- All 76 migrated modules have one canonical owner and legacy aliases preserving module/exception/patch identity.
- The clinical application factory supports independently supplied database, secret, storage, cookie and runtime URL configuration. Two-instance authorization/scope tests cover supported isolation; provider and host flags remain process-level.
- Twenty-two explicit workflow dependency boundaries are registered in `ris/application/port_contracts.json`. The architecture checker rejects infrastructure, web, framework and runtime imports in those services. This is a specific enforced registry, not a claim that all old services are clean.

`ris/docs/CODE_MAP.md` links executable models, composed routes, canonical legacy owners and explicit port boundaries. Regenerate it using `python ris/tools/generate_code_map.py` after ownership changes. `application/component_manifest.json` and `application/module_manifest.json` remain the ownership inventories.

## Explicit workflow boundaries

| Area | Implemented dependency separation | Remaining work |
|---|---|---|
| Assignment | Scoped queries, capacity/count policy, pure ranking/deadlines, case mutations/offer acceptance, grouped visit workflows | Coordinator previews, evidence gathering, broader workers and callbacks still compose at the compatibility edge |
| Registration | Patient field/date/sex policy, visit selection and reserved assignment, latest-decision insurance readiness | Patient creation, scheduling/booking and external RIS interfaces |
| Readiness | Exception/history/alias/override mutations, scoped RIS candidate search, bounded scheduling/refresh, read-only operations aggregation | Actual evidence acquisition/evaluation, broader exceptions and operational worker lifecycle |
| Identity | Pure scope policy, explicit qualification/scope evidence and request/ORM guard ownership | Broader user lifecycle/import/contact dependencies, permission catalogue ownership and host security/VPN integration |
| Reporting | Immutable report saving with repository/artifact ports, edit leases, correction request/review | Reference resolution, correction/editor finalization, callbacks, exports and external editor failure acceptance |
| Finance | FINAL replacement entitlement settlement, branch collection checks, net receipt/refund evidence, authorized daily closing SAVE/CLOSE | Broader receipts/disbursements/refunds, finance unit-of-work/error presentation and external accounting integration |
| Inventory | Original-lot return policy, repository and movement dependencies | Consumption, general stock movement, warehouse lifecycle and stock transport interfaces |
| Clinical staff/RT | Owned models, pure RT input validation and explicit manual course/PET-link/external-plan/session/support ports; components and web routes | Explicit staff transaction use cases, RT read projections and external acceptance; no treatment-device integration or controller is supplied |
| Imaging/viewers | Owned identity/matching policies, imaging adapters/routes and viewer extension | Provisioned synthetic PACS/viewer acceptance, partial transport/retry/recovery contracts |
| Communications/operations | Owned adapter/extension/component modules | Narrow external-provider dependencies, operational recovery and storage/worker lifecycle |

Detailed decisions are in ADRs 001–031. Canonical ownership, explicit use-case inversion and real external integration are separate claims. A screen, a source assertion or a renamed module alone does not establish working integration.

## Preserved contracts and focused evidence

Before/after runtime captures retain the same 160 tables and 546 URL registrations, including types/defaults, foreign keys, indexes, constraints, methods and endpoints. No schema migration or data transformation was introduced. Handler-source and facade-identity tests remain active.

Focused runtime suites retain branch/role scope, receiving assignment barriers, immutable VERIFIED/FINAL reports, scoped editor leases, correction review and FINAL-only replacement settlement. Readiness aliasing requires captured PACS evidence; image exceptions cannot invent images; failed PACS evidence stays BLOCKED. Scheduling tests include PostgreSQL advisory-lock contention on two actual connections. Read-only receiving projections do not overwrite stored readiness.

Inventory returns preserve original lots, costs and expiry; prior disbursements are retained during replacement entitlement adjustments. Closing totals use receipt/refund accounting timestamps, original payment method buckets and finite decimal values. Daily closing authorizes before persistence, locks branch before closing, recomputes expected evidence under the locked context, rejects CLOSED mutations and audits flushed snapshots. Callers own commit/rollback except the explicitly documented per-case scheduler transaction boundary.

Operations aggregation preserves existing auxiliary query scopes and window-based metrics. Global lease statistics and other aggregate visibility policies still require explicit branch/role review before release; existing broad queries are not certified as safe by an extraction test.

## CI evidence and current gate

GitHub Actions runs nine jobs: the complete SQLite suite, seven independent PostgreSQL suites (`clinical`, `assignment`, `scope`, `reporting`, `finance`, `inventory`, `registration`) and a separate Docker Compose build/start/login smoke check.

Latest completed baseline: manual RT session commit 1095b010e0500f2e6acb34fe568ae1eaa97383d8 passed all nine jobs in run 38213659798, including complete SQLite, seven PostgreSQL suites and Docker smoke. The preceding plan head passed 1,985 SQLite tests and all nine jobs; the audit-history fixture fix also passed its own nine checks.

The new RT support/state ports and shared context import enforcement passed 66 focused local tests (one optional existing test skipped). Their own complete CI is required. See [progress measures](PROGRESS.md): ownership inventories are complete, but service counts are not route/function/code percentages and total dependency work is not fully enumerated.

The local runner forces synthetic SQLite and temporary artifact directories. PostgreSQL runs require the guarded isolated development database. Real provider HTTP is blocked in unit/contract tests. The Docker stack contains RIS/PostgreSQL only, not a complete PACS/ONLYOFFICE or host disaster-recovery package.

## Release gates still open

1. Continue replacing `Bindings`, `legacy_runtime` and mixed extension callbacks with narrow evidence/repository/policy interfaces. Broad handler composition, cash entries, stock consumption, registration booking, clinical staff/RT and provider/worker lifecycles remain unfinished.
2. Audit branch/role visibility of auxiliary queries and operations metrics, and run role-based browser UAT with synthetic cases.
3. Provision synthetic PACS/OHIF/ONLYOFFICE failure acceptance: delayed/lost callbacks, reassignment, partial transfer, retry uncertainty, queue restart and destination storage confirmation. Screens/source checks do not replace these scenarios.
4. Validate upgrade/rollback and operational recovery in an isolated environment. PR review, merge and production deployment require a separate release decision.

Module/port counts are concrete inventory measures, not a percentage of total architecture completion or clinical deployment readiness. No live patient data, production database snapshot, credentials or host secrets are added by this development work.
