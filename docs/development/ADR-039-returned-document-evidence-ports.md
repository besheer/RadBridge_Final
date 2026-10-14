# ADR 039: Returned-case document prerequisite evidence

Status: isolated development source; no production deployment or main merge.

ReturnedDocuments receives a read-only history repository, quality-rule lookup and attachment counter. SqlAlchemyReturnedDocumentsRepository owns the original order-scoped note query and database length/trim semantics. Web compatibility composes these dependencies from the supplied runtime; technician_queue retains correction_documents_ready(m, order, state) for the existing callers.

The decision order is unchanged: read the quality rule, require history when the rule or MISSING_HISTORY return reason requires it, stop when no valid history exists, then check attachments only when the rule requires them. Accepted note types remain HISTORY, GENERAL, CLINICAL_HISTORY and NURSING_HISTORY; technical notes and blank database-trimmed text cannot satisfy history. No commit, rollback, report mutation, image action, identity correction or review approval is introduced. Evidence exceptions propagate rather than becoming READY.

This is a document prerequisite check, not complete return resolution. Existing handlers still own authorization, branch scope, strict imaging evidence, readiness and resubmission transactions. Broader technician queue SQL/HTTP composition and staff writes remain mixed dependencies outside the new registered boundary. This extraction does not certify aggregate visibility, concurrency or external integration.

Focused validation: 69 tests passed, covering isolated dependency ordering/absence/failure, actual SQL note-type/text/order filtering, authenticated technician return barriers, bulk assignment and factory compatibility. The new dependency tests and return route suite are included in the clinical PostgreSQL job. Exact runtime contract and full-suite results must be recorded for this change; prior published CI must not be attributed to it.


Historical local extraction note: at that intermediate source snapshot, 2,109 SQLite tests passed, five were skipped, and 109 focused tests passed. Later changes are validated only by the exact commit and CI run recorded in `IMPLEMENTATION_STATUS.md`; these intermediate counts are not the current branch result.
