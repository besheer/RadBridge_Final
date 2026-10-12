# ADR 034: Reviewed demographic request dependencies

Status: implemented locally on the isolated development branch; full validation recorded in implementation status.

The old patient correction module resolved the complete runtime inside every read, validation, request and review operation. Its canonical owner now belongs to web compatibility, preserving the legacy import/module identity and public callable signatures. Runtime lookup and HTTP abort translation stay at that edge.

The application service receives a repository, registration-rule reader/validator, actor identity, branch decision, audit and clock. The repository owns SQL evidence, patient locking and request/detail writes; it has no patient-demographic update or commit method. Domain field/date validation receives an explicit current date. Composition retains `date.today()` to preserve the original behavior.

Snapshot JSON and hash construction, ordering, report-version counts, duplicate open-request rules, reason truncation, audit wording and caller commit ownership remain unchanged. Approval remains review-only: the original patient and FINAL report are not mutated. Web routes still enforce request/review permissions and self-review denial. Application review rechecks the snapshot, every affected order's branch authorization and current registration rules after locking the patient.

This extraction does not solve the pre-existing race between concurrent request submissions, add an identity-correction execution workflow, or change cross-branch preview visibility. Those require explicit authorization/transaction design and acceptance. Do not interpret a reviewed request as a completed PACS identity correction.

New standalone dependency tests exercise no writes on stale evidence, duplicate requests, unchanged values and short reasons; review rejects unauthorized branches, changed report versions, changed registration rules and legacy unstructured requests. Existing authenticated route tests remain active. The PostgreSQL registration suite includes both the new tests and existing structured correction routes.
