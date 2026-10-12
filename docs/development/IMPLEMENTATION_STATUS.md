# Architecture implementation and remaining gates

Date: 2026-10-12. Scope: isolated development source on `refactor/development-foundation`, draft PR #1. Main and production have not been modified. Clinical release metadata remains 5.46.9; these changes are not a deployed clinical release.

## Implemented ownership

- All 160 persisted models belong to 14 infrastructure model modules; the SQLAlchemy extension is unbound until application composition.
- All 949 extracted functions have executable owners in 32 component/route/helper modules. Eighty HTTP-dependent installers were assigned to web ownership without changing their handler bodies.
- All 76 migrated modules have one canonical owner and legacy aliases preserving module/exception/patch identity.
- The clinical application factory supports independently supplied database, secret, storage, cookie and runtime URL configuration. Two-instance authorization/scope tests cover supported isolation; provider and host flags remain process-level.
- Twenty-nine explicit workflow dependency boundaries are registered in `ris/application/port_contracts.json`. The architecture checker rejects infrastructure, web, framework and runtime imports in those services. Direct Flask imports are now rejected in the entire application/services package, including unregistered modules. This does not certify transitive dependencies or all old orchestration as clean.

`ris/docs/CODE_MAP.md` links executable models, composed routes, canonical legacy owners and explicit port boundaries. Regenerate it using `python ris/tools/generate_code_map.py` after ownership changes. `application/component_manifest.json` and `application/module_manifest.json` remain the ownership inventories.

## Explicit workflow boundaries

| Area | Implemented dependency separation | Remaining work |
|---|---|---|
| Assignment | Scoped queries, capacity/count policy, pure ranking/deadlines, case mutations/offer acceptance, grouped visit workflows, read-only monitoring projections | Aggregate visibility/performance review, coordinator previews, evidence gathering, broader workers and callbacks still compose at the compatibility edge |
| Registration | Patient field/date/sex policy, visit selection and reserved assignment, latest-decision insurance readiness, structured demographic request/review, existing-patient appointment creation | Patient creation, remaining scheduling/booking/check-in/rescheduling transactions, concurrent demographic request serialization, approved identity-change execution and external RIS interfaces |
| Readiness | Exception/history/alias/override mutations, scoped RIS candidate search, bounded scheduling/refresh, read-only operations aggregation | Actual evidence acquisition/evaluation, broader exceptions and operational worker lifecycle |
| Identity | Pure scope policy, explicit qualification/scope evidence and request/ORM guard ownership | Broader user lifecycle/import transactions, permission catalogue lifecycle and host security/VPN integration |
| Reporting | Immutable report saving with repository/artifact ports, edit leases, correction request/review | Reference resolution, correction/editor finalization, callbacks, exports and external editor failure acceptance |
| Finance | FINAL replacement entitlement settlement, branch collection checks, net receipt/refund evidence, authorized daily closing SAVE/CLOSE, manual report/image delivery readiness | Broader receipts/disbursements/refunds, delivery event write transactions, finance unit-of-work/error presentation and external accounting integration |
| Inventory | Original-lot return policy, repository and movement dependencies | Consumption, general stock movement, warehouse lifecycle and stock transport interfaces |
| Clinical staff/RT | Owned models, pure RT input validation, manual course/PET-link/external-plan/session/support/read ports and returned-document prerequisite read ports; components and web routes | staff mutation/worklist transactions, RT permissions/configuration and external acceptance; no treatment-device integration or controller is supplied |
| Imaging/viewers | Owned identity/matching policies, imaging adapters/routes and viewer extension | Provisioned synthetic PACS/viewer acceptance, partial transport/retry/recovery contracts |
| Communications/operations | Owned adapter/extension/component modules | Narrow external-provider dependencies, operational recovery and storage/worker lifecycle |

Detailed decisions are in ADRs 001–039. Canonical ownership, explicit use-case inversion and real external integration are separate claims. A screen, a source assertion or a renamed module alone does not establish working integration.

## Preserved contracts and focused evidence

Before/after runtime captures retain the same 160 tables and 546 URL registrations, including types/defaults, foreign keys, indexes, constraints, methods and endpoints. No schema migration or data transformation was introduced. Handler-source and facade-identity tests remain active.

Focused runtime suites retain branch/role scope, receiving assignment barriers, immutable VERIFIED/FINAL reports, scoped editor leases, correction review and FINAL-only replacement settlement. Readiness aliasing requires captured PACS evidence; image exceptions cannot invent images; failed PACS evidence stays BLOCKED. Scheduling tests include PostgreSQL advisory-lock contention on two actual connections. Read-only receiving projections do not overwrite stored readiness.

Inventory returns preserve original lots, costs and expiry; prior disbursements are retained during replacement entitlement adjustments. Closing totals use receipt/refund accounting timestamps, original payment method buckets and finite decimal values. Daily closing authorizes before persistence, locks branch before closing, recomputes expected evidence under the locked context, rejects CLOSED mutations and audits flushed snapshots. Callers own commit/rollback except the explicitly documented per-case scheduler transaction boundary.

The Case Operations Control Center now derives branch scope from the signed-in user's registration policy. Its cases, leases, PACS inbox items, exam links, escalations and PACS events are restricted to the scoped order IDs; branch-specific strategies include only global and permitted-branch entries. The unassigned-case queue now filters cases, filter choices, branches and doctors to the user's branch, and both GET and POST assignment entry points share the existing assignment-role and branch guard. Synthetic SQL-backed and route tests cover permitted and empty scopes plus direct cross-branch read and assignment attempts. These fixes close those screens' direct cross-branch paths; they do not certify branch/role scope across the rest of the application or replace role-based browser UAT.

## CI evidence and current gate

GitHub Actions runs nine jobs: the complete SQLite suite, seven independent PostgreSQL suites (`clinical`, `assignment`, `scope`, `reporting`, `finance`, `inventory`, `registration`) and a separate Docker Compose build/start/login smoke check.

Validated published source `eabe773cc91e6122bd9c5d3428c84230d2f298f8` passed all nine jobs in [run 38271477503](https://github.com/besheer/RadBridge_Final/actions/runs/38271477503): 2,094 SQLite passed, five skipped, 43,265 warnings; seven PostgreSQL suites and Docker smoke passed. Source guard scanned 3,319 tracked files and 3,552 history blobs with no findings. These results cover the 28-boundary source plus safety guards and corrected synthetic booking fixtures; they do not cover subsequent changes until their own CI completes.

Earlier local extraction test results are historical evidence for their individual steps, not the latest cloud baseline.

Current returned-document extraction: 2109 SQLite passed, five skipped, 43315 warnings in 158.21 seconds; 109 focused tests passed. Architecture checks, source guard and exact before/after runtime comparison passed (160 tables, 546 URL registrations). The initial full run failed the CSV export roundtrip because new repository fixtures committed users into the shared synthetic database. Those read-only fixtures now flush and roll back without committing; CSV row limits, security assertions and application behavior were not weakened. This complete rerun passed. PostgreSQL/Docker results for this newer change require its own remote CI.

The local runner forces synthetic SQLite and temporary artifact directories. PostgreSQL runs require the guarded isolated development database. Real provider HTTP is blocked in unit/contract tests. The Docker stack contains RIS/PostgreSQL only, not a complete PACS/ONLYOFFICE or host disaster-recovery package.

## Release gates still open

1. Continue replacing `Bindings`, `legacy_runtime` and mixed extension callbacks with narrow evidence/repository/policy interfaces. Broad handler composition, cash entries, stock consumption, registration booking, clinical staff/RT and provider/worker lifecycles remain unfinished.
2. Audit branch/role visibility of auxiliary queries and operations metrics, and run role-based browser UAT with synthetic cases.
3. Provision synthetic PACS/OHIF/ONLYOFFICE failure acceptance: delayed/lost callbacks, reassignment, partial transfer, retry uncertainty, queue restart and destination storage confirmation. Screens/source checks do not replace these scenarios.
4. Validate upgrade/rollback and operational recovery in an isolated environment. PR review, merge and production deployment require a separate release decision.

Module/port counts are concrete inventory measures, not a percentage of total architecture completion or clinical deployment readiness. No live patient data, production database snapshot, credentials or host secrets are added by this development work.

See [server transfer readiness](SERVER_TRANSFER_READINESS.md) for development-versus-full-production transfer gates and residual coupling. Production has not been changed. The demographic/delivery/monitoring/appointment boundaries and HTTP placement passed the published nine-job CI above. The returned-document boundary is newer and requires its own CI; no deployed-release claim is made. Static auditing still finds SQLAlchemy imports outside the registry; broad Bindings, runtime resolution and model/HTTP callbacks remain. Direct Flask import enforcement does not certify transitive dependencies or all services as independent.
