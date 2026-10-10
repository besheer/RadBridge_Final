# Architecture change validation plan

This plan applies **if a future architectural change is implemented**. Creating this blueprint did not refactor, rebuild, migrate or deploy the application.

## Phase A — capture the baseline

Pin the current source/image/schema/configuration privately and declare the exact change boundary. Build an independent synthetic environment. Resolve omitted assets first. Replay representative workflows and capture results, audit records and content hashes without patient data. Run the existing suite before the change and record actual skips/failures rather than treating the historical result as a new run.

Recorded checkpoint result: 1778 passed / 3 skipped, plus 22 isolated PostgreSQL RT tests. It is a comparison point, not a guarantee a fresh checkout is turnkey. Standard `tests/conftest.py` forces SQLite; PostgreSQL-specific validation needs an isolated PG fixture adaptation. See [development operations](../handover/OPERATIONS.md).

## Phase B — one seam per change

Pick a single service/policy boundary. Define inputs, outputs, permission checks, invariants, DB/file transaction boundaries and external-call failure behavior. Add behavioral contract tests around the existing implementation before extraction. Keep compatibility tests against the same synthetic fixtures. Do not add implementation-mirroring tests that prove only the internal refactor shape.

## Acceptance matrix

| Scenario | Positive path | Denial/failure path | Evidence |
|---|---|---|---|
| Patient/order creation | Correct existing patient, unique accession and branch | Duplicate identifiers, invalid branch or cancelled target | Records and audit; no duplicate identity |
| Staff procedure execution | Permitted technician/nurse under exam-code policy | Wrong role/device/room, stale exam state | Allowed transition; denied direct URL; policy snapshot |
| PACS reconciliation | Confirmed study mapped to true RIS order | Wrong patient, incorrect/incomplete identity, stale preview | Correct linkage; identities/history unchanged on rejection |
| Readiness/assignment | Explicitly eligible case assigned once | RECEIVING, missing requirements, wrong scope; single/bulk/automatic paths | Same evaluated blockers at every entry point |
| Doctor access | Assigned/permitted study via supported viewer | Other branch/patient, expired capability, unsupported client | Access denial and permitted study opening |
| Report save | Explicit draft commit creates persistent current version | Callback loss/timeout, stale base version, concurrent edits | Saved artifact/hash/version/audit consistency |
| Verify/final/revision | Latest saved version verified/finalized; audited correction | Edit locked original, verify unsaved/stale content | Original FINAL remains immutable |
| Financial adjustment | Approved FINAL replacement adjustment | ADDENDUM transfer, deleting posted payment, duplicate posting | Preserved original ledger plus explicit adjustment |
| RT course/session | External plan record and scoped session completion | Wrong PET patient/branch, dose tamper, changed replay, invalid device | Snapshot integrity and exactly one accepted completion |
| Exports/user preferences | Authorized scoped result and per-user saved filters | Cross-branch export or preferences expanding scope | Correct dataset; independent user settings |
| Audit/security | Authorized config change recorded | Untrusted proxy IP, forbidden role, stale collector data | Actor/reason/time; no credentials/capabilities in logs |
| Restart/queue/partial transfer | Required state persists and recovers | Process interruption, duplicate/lost acknowledgement | No duplicate clinical action; explicit external-status handling |

## Fault injection on isolated services

Test DB connection failure, stale versions and concurrent requests; editor callback failure; PACS/network interruption; process restart; partial transfer and uncertain acknowledgement where the changed transport component supports them. Verify retry does not bypass readiness/approval or repeat a financial/session commit. Exercise persistent pending state after restart. If the required recovery behavior is missing, document it as a gap rather than simulating a successful label.

Real destination Storage Commitment, external RIS/API/HL7/MWL behavior, or a treatment-device feed needs dedicated approved integration tests. None is automatically certified by a mocked unit test or by this plan.

## Performance and compatibility

Measure baseline and changed request latency, database query count, lock conflicts, worker backlog and representative concurrency on identical fixtures/hardware. Agree numerical acceptance thresholds for the selected change before implementation; this blueprint invents no throughput/SLA target. Review browser rendering on both languages and supported desktop/mobile sizes. Check all impacted callbacks, URL contracts, exports and persisted version formats.

## Release gates

1. **Source gate:** coherent commit, clean tree, actual dependency/asset requirements recorded.
2. **Functional gate:** relevant suite and contract scenarios pass; skips/failures are explained.
3. **Safety gate:** identity, branch/scope, immutable reports and audit/ledger/session invariants pass.
4. **Integration gate:** approved external services and fault paths verified, or explicitly excluded from the release scope.
5. **UAT gate:** role walkthrough, bilingual UI, direct URL denial and console/network checks.
6. **Recovery gate:** exact rollback target and additive migration compatibility checked; broader schema/storage changes require a real restore rehearsal.
7. **Deployment gate:** current authorized environment only, controlled replacement and post-release health/authenticated checks.
8. **Handover gate:** update source checkpoint, docs, exclusions and GitHub verification receipt.

Any failed required gate blocks release until corrected or the owner explicitly narrows the scope. An architectural diagram is not deployment authorization, test evidence or a database migration.

## Result template

```text
Change ID and source/base commits:
Component and contract changed:
Environment and synthetic dataset:
Baseline results / new results / skips:
Role and direct-URL checks:
Identity/report/ledger/session invariants:
External integrations and fault injection:
Performance measurements and agreed thresholds:
Migration/rollback evidence:
UAT evidence:
Open gaps and scope exclusions:
Release decision and reviewer:
Post-release checks and GitHub checkpoint:
```
