# Architecture decisions made while executing the blueprint

## 2026-10-16 — Continue as a modularizing monolith

- **Decision:** Extract one bounded workflow at a time inside the existing Flask application, keeping route URLs, persisted schemas and external contracts stable.
- **Reason:** The blueprint prefers gradual in-process extraction before considering independent services. It lowers compatibility risk and allows a rollback per change.
- **Alternative considered:** Split the current application into microservices or introduce a message broker. Deferred because service ownership, durable job state, idempotency and recovery contracts are not established.

## 2026-10-16 — Stock transfers are the next service boundary

- **Decision:** Move the request/approve/reject/dispatch/receive lifecycle orchestration behind an application service, leaving authorization at the web boundary and persistence/movement mechanics behind injected ports. The caller remains responsible for commit/rollback in this slice.
- **Reason:** The central-only approval policy and branch-scope query adapter are already implemented, but handlers still own state transitions and stock movement orchestration. This is a bounded seam with existing authorization tests and an explicit user-approved policy: branches request from authorized central warehouses; central staff approve; only authorized warehouses are visible.
- **Alternative considered:** Refactor cash, booking, or reporting callbacks first. Deferred so the already-started inventory boundary can be completed coherently before opening another seam.

## 2026-10-16 — Treat current CI failure as unverified, not as a source regression

- **Decision:** Keep the PR draft and do not infer green or code failure from the latest GitHub Actions run while all jobs expose no steps and logs return 404. Continue local validation and retry/inspect CI when diagnostics become available.
- **Reason:** The failure has no job-level evidence, while local architecture and source-safety checks pass.
- **Alternative considered:** Declare CI green based on historical runs, or weaken checks to make the current status pass. Rejected because neither is supported by current evidence.
