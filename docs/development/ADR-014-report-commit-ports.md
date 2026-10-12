# ADR 014: Report commit persistence and artifact ports

Date: 2026-10-11. Status: implemented on the development branch; full CI required.

`domain.reporting.commit_policy` owns commit identity, retry identity, base-version and duplicate-content decisions. Existing imports re-export the same function and error objects. No database, filesystem or web imports are added to this policy module.

`application.services.reporting.report_commit_service` orchestrates report saving with explicit repository and artifact-store dependencies. It imports neither SQLAlchemy, infrastructure implementations, Flask nor a runtime resolver. `SqlAlchemyReportCommitRepository` owns row locking, version queries, construction and flush/rollback. `LocalReportArtifactStore` owns source hashing, secure version paths, hash-verified copying and atomic no-clobber hard-link publication. The compatibility edge wires the original function signature to these implementations; both old import paths alias that edge.

The existing operation order is preserved: patient identity validation, report row lock, known-commit retry, FINAL/finalized barrier, base-version check, source validation, duplicate hash check, publication and version persistence. Known retries remain accepted after FINAL without republishing. The service flushes and leaves successful commit ownership with the caller. A failed flush rolls back and compensates only its own newly published artifact. Existing artifacts are never replaced. Database commit failure after the service returns and crash recovery still require a broader unit-of-work/reconciliation design; this extraction does not claim that gap is solved.

Validation: 67 focused tests passed locally, including real ORM/synthetic-file saves, post-FINAL retries, stale-base rejection, independent fake repositories/stores, failed-flush compensation, existing-artifact preservation and copy-hash mismatch. The architecture import checker passes. CI adds an isolated PostgreSQL reporting suite alongside the existing clinical, assignment and scope suites. All fixture content is synthetic.

Report revisions, editor callback orchestration, exports and finalization retain their existing compatibility dependencies and require subsequent use-case separation. External editor/PACS acceptance remains a separate gate. No production deployment, schema migration or data transformation is included.
