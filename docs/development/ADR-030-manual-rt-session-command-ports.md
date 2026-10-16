# ADR 030: Manual RT session command dependencies

Status: implemented on the isolated development branch; new full CI required.

Scheduling, rescheduling, starting, completion recording and cancellation use explicit persistence and immutable scope/actor/audit/clock policies. The repository owns course-before-fraction locks, preview/device lookup, active plan evidence, prior attempts and new session persistence. The domain owns the original normalized completion fingerprint. Permissions, nurse denial, device/branch scope, CSRF, HTTP outcomes and caller commit/rollback stay at the web edge.

Preserve prescribed session amounts, current-plan/version barriers, operational-device checks where the original workflow required them, course state, number/count bounds and original retry-attempt history. Rebooking retains CANCELLED/NOT_GIVEN attempts instead of reusing a delivered attempt. A paused course cannot start a new session but can record a previously STARTED one. Actual variance still needs the original recorded reason; no automatic prescription or clinical approval is inferred.

Completion replays retain the original ordering: scope/actor checks, input fingerprint, then known completed key/hash lookup before version/plan/state checks. An identical known completion returns a read-only redirect without a new audit or caller commit; changed payload/key conflicts. Fresh completion checks the current version/plan/device/STARTED state before recording the manual external input. Completed sessions cannot be cancelled/rescheduled or overwritten. These commands do not control treatment equipment or change RIS reports/source orders, stock or billing.

The old unused nested usable helper is removed; other still-used web course/fraction helpers remain for course-state/notes/consumables until their own extraction. No alternate session mutation implementation is kept at the HTTP edge.

Validation: 53 focused tests passed locally (one existing optional test skipped), including direct dependencies and actual original RT routes/factory/scopes. Direct tests cover actor/device barriers, lock ordering, replay before stale-version/new-plan checks, changed replay denial, paused completion, obsolete plans, inactive devices, invalid actual variance, rebooking history, immutable cancellation and pending rescheduling. PostgreSQL clinical includes the new dependency file; existing persisted route tests exercise every command.

Prior plan commit `9d93c2f3d0f40c3fcfb11124f11e4d0b9c986d94` passed all nine CI jobs (run 38212772301). New schema/route invariance and complete CI remain required for this session commit. Course-state, notes and consumable use cases still require their own explicit dependencies.
