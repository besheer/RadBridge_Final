# RadBridge gradual architecture plan

Scope: continue the existing modularizing-monolith migration on the isolated GitHub review branch. Keep routes, persisted data and external contracts compatible. Do not deploy, merge, or modify production.

## Milestones

- [x] Read the architecture blueprint, current progress, repository rules and branch state.
- [x] Confirm the current branch is clean and matches the remote PR head before work.
- [x] Record the latest CI state: current GitHub Actions jobs fail without step summaries or retrievable logs; local checks remain the actionable evidence until GitHub diagnostics return.
- [x] Extract stock-transfer approve/reject/dispatch/receive orchestration from compatibility route handlers into an application service with injected persistence/movement ports; preserve central-only approval, authorized-warehouse scope, audit records, and caller-owned transaction commit/rollback.
- [x] Add behavior-focused service and runtime regression tests for allowed transitions, invalid states, insufficient stock, and partial receive; preserve route contracts and explicitly version handler source hashes when architectural changes are reviewed. Database rollback-on-failure is still covered by legacy handler behavior and needs an integration assertion before this seam is considered fully accepted.
- [x] Run focused inventory suites, full SQLite suite, and architecture/source-safety checks. Focused inventory/component suites: 25 passed; full SQLite suite: 2,168 passed, 5 skipped; architecture and source-safety checks passed.
- [ ] Run PostgreSQL inventory contracts and Docker smoke. This checkout has no configured isolated PostgreSQL DSN and no Docker CLI; GitHub Actions on the previous head failed without logs. Revisit after a usable CI run or isolated test environment is available.
- [ ] Continue the permission/branch-scope census across remaining workflows and convert each confirmed gap into an isolated, tested change.
- [ ] Close external acceptance gates in an isolated staging environment: PACS/OHIF/Weasis/ONLYOFFICE, role/browser UAT, and failure/retry scenarios.
- [ ] Rehearse upgrade, rollback, backup and restore on a separate server before any release decision.

## Current focus and completion rule

The current focus is the stock-transfer lifecycle, whose authorization and query-scope seams already exist while transaction orchestration remains in legacy handlers. Do not mark the blueprint complete based on module counts. Complete release readiness only when each applicable source, functional, safety, integration, UAT, recovery and handover gate has recorded evidence; production release remains a separate authorization.
