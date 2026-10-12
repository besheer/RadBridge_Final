# ADR 029: Externally approved manual RT plan records

Status: implemented on the isolated development branch; new full CI required.

Manual plan recording receives explicit repository, actor/course scope, audit and current approval-date dependencies. The repository owns course locking, started/delivered session evidence, attachment identity, active plan selection, maximum revision and model persistence. Route permissions, nurse denial, CSRF, HTTP error mapping and caller commit/rollback remain at the web edge.

Preserve course scope/version checks before mutation, terminal/started-session barriers, approved-date/count limits, delivered-number floor and attachment patient/primary-order identity. Validate all supplied external plan metadata/amounts before superseding the prior plan. Add/flush the new version, increment course version, activate a DRAFT course and emit the original manual-record audit. Existing prior prescription values remain unchanged; only its superseded status changes. This records external approvals and does not infer a prescription, approve a plan clinically or operate a treatment device.

Plan count/dose relationships and clinical criteria are unchanged from the original source. The injected approval-date clock retains Cairo local-date semantics. Session scheduling/delivery, notes, consumables and course-state use cases still require their own dependencies.

Validation: 51 focused tests passed (one existing optional test skipped), including actor/scope/version barriers, started/completed evidence, future approval, wrong attachment identity, invalid amounts, prior prescription retention, actual RT routes and factory isolation. The complete working-tree SQLite suite passed 1,985 tests (five skipped), including this plan extraction and the audit-history fixture fix. Clinical PostgreSQL adds the new plan dependency file.

The preceding course/PET commit passed seven PostgreSQL jobs and Docker but its complete SQLite suite exposed a test fixture counting older audit history after SQLite reused a deleted link ID. Fix commit `5ff5b7c3ef973aeb2323839abfe9cb0974f2c833` restricts that assertion to new audit rows, retaining the no-duplicate retry check; it passed all nine CI jobs in run 38212440206. This is a test-only fix, not a changed audit/production workflow. New schema/route invariance and complete CI remain required for this plan commit.
