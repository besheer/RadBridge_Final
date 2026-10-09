# Manual PET/CT and radiotherapy handover

## Delivered scope

The owner chose **manual recording of an externally approved plan and its sessions first**. The module does not prescribe treatment, calculate clinical doses, control machines or certify delivered dose from a device. PET radiopharmaceutical activity must not be entered as treatment dose in Gy. A plan version represents one prescription/target; separate prescriptions/targets require separate courses in this phase.

Entry point: `/radiotherapy`. Main module: `ris/radiotherapy.py`; templates: `radiotherapy_list.html`, `radiotherapy_course.html`; additive migration: `radiotherapy_migration.py`; tests: `tests/test_radiotherapy.py`.

## Data records

| Table | Purpose |
|---|---|
| `rt_course` | Primary RIS order, patient, branch, reference, lifecycle and optimistic version |
| `rt_plan_version` | Immutable external plan reference, approver/date, target, total Gy, per-session Gy, fractions and optional approval attachment |
| `rt_fraction` | Plan snapshot, fraction number/attempt, device, scheduling, execution, actual dose and manual record reference |
| `rt_pet_link` | Same-patient/branch PT accession linked for baseline, planning reference, follow-up or another documented purpose |
| `rt_note` | Append-only preparation/nursing/technical/clinical note, optionally tied to a session |
| `rt_consumable` | Manual positive-quantity session ledger; no stock deduction or automatic billing |

Class names are prefixed `RT` to avoid collisions with existing ORM class relationships. A plan/session has explicit course-linked constraints; cancelled/not-given attempts remain recorded.

## State and invariant contracts

- Course: DRAFT → ACTIVE when a plan is recorded. ACTIVE may pause, complete or cancel; PAUSED may resume or cancel. Completion requires the prescribed count of completed fractions. No terminal transition while a session is STARTED.
- A recorded externally approved plan cannot have a future approval date. Its supporting attachment must belong to the primary RIS case/patient. A new version supersedes the prior active version; deny revision with started sessions or a terminal course.
- Scheduled session dose is copied from the active plan's `fraction_gy`; a coordinator cannot alter it in a scheduling request. Pending sessions retain their previous snapshot until explicitly rescheduled/adopted with a reason.
- Session starts only when permitted and the course allows a new start. Pause stops new starts but permits recording an already-started session's completion.
- Completion requires STARTED, positive valid actual dose and manual machine-record reference. Actual dose variance requires a recorded reason. This remains a human-entered record.
- A repeated completion key with identical canonical content does not create a second completion/audit entry. Changed replay or stale versions conflict with HTTP 409. PostgreSQL row locks protect concurrent completion.
- Completed sessions are immutable. Only scheduled attempts can be cancelled/not given with a reason; rebooking keeps prior attempts and requires an explanation.
- Device and primary case must satisfy branch and configured modality/device/room scope. Linking PET neither changes original identities nor merges orders or reports.
- Posted timestamps are interpreted in Africa/Cairo when naive, then stored in UTC. Ambiguous local DST times are rejected.

## Role grants at this release

| Role | New RT permissions |
|---|---|
| TECHNICIAN | view, session.start, session.record, notes, consumables |
| NURSING | view, notes, consumables |
| CASE_COORDINATOR | view, course.create, pet.link, schedule, notes |
| BRANCH_MANAGER | view |
| RADIOTHERAPY_PHYSICIAN | view, course.create, plan.record, pet.link, schedule, notes; plus dashboard/patient/order/attachment viewing |

Permission names use the `rt.` prefix. Role grants were additive/audited; no users were created or reassigned. New RT physician role does not automatically grant report editing or image access. Nursing cannot enter a plan/dose or start/complete RT sessions even if dose permissions are accidentally added; regular exam start/end is a separate policy.

## Form/HTTP routes

All mutating routes require the appropriate permission, scope and session CSRF token; `rt_csrf` is exposed to templates as the `csrf_token` field. These are form routes, not a public machine-to-machine clinical API.

| Method/path | Contract |
|---|---|
| GET `/radiotherapy` | Search course reference or exact patient ID within access scope |
| POST `/radiotherapy/courses` | Create using a true RIS accession and unique course reference |
| GET `/radiotherapy/<course_id>` | Scoped course detail |
| POST `/radiotherapy/<course_id>/plans` | Record an externally approved plan/revision |
| POST `/radiotherapy/<course_id>/pet-links` | Exact PT accession, same patient/branch, purpose and reason |
| POST `/radiotherapy/<course_id>/fractions` | Schedule an attempt with a permitted existing device |
| POST `/radiotherapy/<course_id>/state` | Reasoned course lifecycle transition |
| POST `/radiotherapy/<course_id>/notes` | Append note, optionally a permitted course session |
| POST `/radiotherapy/fractions/<fraction_id>/reschedule` | Scheduled session only, explicit plan snapshot adoption/reason |
| POST `/radiotherapy/fractions/<fraction_id>/start` | Version-checked session start |
| POST `/radiotherapy/fractions/<fraction_id>/complete` | Actual Gy, machine record, idempotency key and variance reason where needed |
| POST `/radiotherapy/fractions/<fraction_id>/cancel` | Cancel/not-given with required reason |
| POST `/radiotherapy/fractions/<fraction_id>/consumables` | Append the manual consumables record |

Check actual input field names and validation in source/templates before building a client. Success commonly redirects; validation may flash and redirect. Unauthorized/missing scope uses 403, optimistic/constraint conflicts use 409 and missing entities may use 404. Do not reinterpret every redirect as successful clinical delivery.

## Migration and acceptance

The release added only these six tables with `metadata.create_all(..., tables=wanted, checkfirst=True)` in a transaction and asserted the before/after table delta. Existing tables were not altered. It is not called automatically on web startup. Do not substitute broad `db.create_all()` or `bootstrap_db.py` on production.

Recorded checks: 22 isolated PostgreSQL tests including real concurrent completion; SQLite runs skip the PostgreSQL-specific case. The full runtime suite recorded 1778 passed/3 skipped. Arabic/English synthetic pages were checked at widths 1440 and 390; read-only live GET checks passed. No real treatment course was inserted for acceptance.

Outstanding: assigning the specialist role to real authorized users, configuring appropriate existing branch treatment devices and clinical procedure/catalog policy, and agreeing on advanced treatment/stock/billing integrations. No external TPS/machine dose feed, prescription engine or multi-target automatic calculations are implemented by this phase.
