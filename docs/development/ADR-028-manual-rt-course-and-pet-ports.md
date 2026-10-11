# ADR 028: Manual RT course creation and PET links

Status: implemented on the isolated development branch; new full CI required.

Course creation and PET reference linking execute through explicit repository, clinical-scope, actor and audit dependencies. SQL course locks/order lookup/model creation belong to an infrastructure repository. Domain version/link barriers raise semantic errors; HTTP outcome mapping remains at the web edge. Existing route permissions, CSRF, error presentation and caller commit/rollback remain unchanged.

Course creation copies the authoritative order/patient/branch identity, rejects cancelled orders and audits only after flush. PET linking locks/scopes the course before checking the submitted version and terminal status, then looks up/scopes the target order. It requires matching patient and branch, PT modality and a non-cancelled source order. Allowed link purposes and reviewed reasons are retained; no name-based identity inference or automatic data correction is added. Accepted links increment course version after persistence and retain the original audit payload. Unique constraints and caller rollback handle duplicate writes.

This is manual record/reference orchestration. It does not change prescriptions, approve plans, control a treatment device, modify a clinical report or change source orders. Plan versions, scheduling, delivered session records, notes and consumables still require their own explicit transaction dependencies.

Validation: 41 focused tests passed locally (one existing optional test skipped). New direct tests cover scope-before-mutation, stale versions, terminal courses and mismatched patient/branch/modality/cancelled orders. The persisted synthetic PET route test checks success, original identity/state retention, stale retry rejection and exactly one link/audit. Existing RT nursing/device/branch/session/factory tests remain active. PostgreSQL clinical includes the new direct/runtime files.

The preceding validation ownership commit `4a47f25f0b5ce8fab63649ca0d88949eb4e819f7` passed all nine jobs in run 38167591224, including 1,963 SQLite tests (five skipped). New schema/route captures and full CI remain required.
