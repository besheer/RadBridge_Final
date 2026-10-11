# ADR 016: Correction request and review dependency boundaries

Date: 2026-10-11. Status: implemented on the development branch; full CI required.

`revision_workflow` owns request creation and approve/reject transitions through explicit repository and reference, qualification, audit, notification and clock policies. `SqlAlchemyRevisionRepository` owns order/revision row locks, request/version queries, row construction and flush. Shared lifecycle/error identity lives in `domain.reporting.revision_policy`.

The old mixed module now belongs to `web.extensions.report_revisions`, which retains HTTP guards, document/reference evidence and internal notifications. Both old import paths alias this module. It composes the new workflows with the existing evidence and permission callbacks, preserving patch and registration identity. Document resolution and editor/finalization remain unfinished services.

Requests lock the order before checking the original approved reference and active request, then flush before audit and notification. Review locks order then revision, checks state/reason/action and requires unchanged reference plus qualified doctor before approval. Rejection releases the active request slot. These workflows never update the original FINAL report, order, assignment or settlement. Commit/rollback remain caller-owned.

Validation: 50 focused tests passed locally, with the PostgreSQL-only lease test skipped. Direct tests verify reference linkage, duplicate request rejection, lock ordering, unqualified-doctor rejection, original-order preservation and repeat-review denial. Runtime correction lifecycle tests retain document integrity, permission and callback assertions. The 160-table/546-route structural contract remains a required check.

The preceding PostgreSQL reporting run exposed two additional fixture defects: a synthetic lease doctor omitted required full_name, and a cross-branch test assigned a nonexistent foreign key. Fixtures now supply the required name and a real synthetic second branch without weakening denial assertions. Those PostgreSQL checks must pass on this commit. No production deployment or data/schema change is included.
