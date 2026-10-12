# ADR 032: Scoped RT read projections

Status: implemented on the isolated development branch; new full CI required.

RT worklist/detail composition and device visibility use explicit read repositories. The infrastructure adapter owns branch/global restrictions, primary-order scope predicates, reference/patient-ID search, the fixed 100-row worklist, plan/session/history ordering and allowed-device filtering for sessions, notes and consumables. It reuses the canonical infrastructure clinical-scope predicate rather than resolving a web runtime.

The application detail service loads/scopes the course before related records and obtains scope evidence after the original plan/device query boundary. Missing courses retain 404; denied course/device scope retains its authoritative denial. The same filtered device IDs constrain all three related projections. Disabled scope avoids device predicate queries; configured invalid scope retains the canonical fail-closed SQL predicate. Existing auxiliary note filtering and search wildcard behavior are unchanged.

The RT extension now contains HTTP registration, actor/permission/CSRF policy composition, templates, caller commit/rollback and semantic-error presentation. It contains no ORM query construction or SQL execution. Manual RT mutations and read projections are application/repository responsibilities; permissions/default-role configuration and external acceptance remain separate release responsibilities.

Validation: 82 focused tests passed locally (one existing optional test skipped), including direct read projections, negative helper import checks, persisted bilingual RT pages, device/branch/direct-URL restrictions, clinical scope, all manual commands and factory isolation. New tests verify scope/query ordering, filtered related IDs, missing/denied early exits, normalized search and independent repositories. PostgreSQL clinical includes the direct read tests; existing real RT route tests exercise the adapter.

Support/context commit `fa44068aadcc5507631b7ee5992403c77064e422` passed all nine jobs (run 38214725444), including 2,013 SQLite tests (five skipped). New schema/route invariance and complete CI remain required for this read projection commit. This separation does not certify a treatment-device feed, external clinical approval or a production RT rollout.
