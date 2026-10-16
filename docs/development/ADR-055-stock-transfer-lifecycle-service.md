# ADR 055: Stock-transfer lifecycle service

Status: implemented on the isolated architecture review branch; full CI and database rollback integration acceptance remain open.

The approval, rejection, dispatch and receive operations now delegate transition and stock-allocation orchestration to `application.services.inventory.transfer_workflow`. SQLAlchemy line/lot access and existing stock functions are supplied by `infrastructure.adapters.inventory.transfer_workflow_repository`; composition occurs in `web.extensions.inventory_transfer_policy`.

The web boundary still performs authentication/permission and branch-scope checks, loads the scoped transfer, and owns commit/rollback. The request form and creation of transfer/line records remain in the existing route. The service does not introduce a new transaction manager, schema, URL, or service process.

Dispatch validates every requested line against available stock before the first movement, then allocates through the existing stock-lot ordering and movement callback. A movement failure is expected to be rolled back by the dispatch route's existing transaction handler. Receive creates the same untracked target lot and movement used before extraction. Audits remain in the same transaction and preserve the existing event names.

The component manifest retains each affected handler's `original_sha256` and records the reviewed post-extraction `current_sha256` plus a change reason. The handler integrity test accepts only the exact reviewed current source for those entries; unreviewed drift still fails.

Focused evidence: service transition/allocation tests, runtime permission/scope coverage, and component source-contract tests. Full SQLite, PostgreSQL inventory, Docker and GitHub Actions validation are required before treating the change as fully accepted. The latest GitHub Actions jobs have no summaries or retrievable logs, so that result remains unverified.
