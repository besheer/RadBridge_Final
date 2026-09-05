# RadBridge RIS/PACS — AI & Developer Handover Guide

**Current baseline:** v5.31.1 Developer-Ready  
**Functional baseline:** v5.31.0 DICOM Resend & Routing  
**Purpose:** make the project maintainable by another developer or AI without depending on prior chat history.

## Read this first

Before changing code, read in this order:

1. `AI_DEVELOPER_GUIDE.md` — rules for safe continuation.
2. `docs/ARCHITECTURE.md` — services, modules, data flow, boundaries.
3. `docs/DATABASE.md` — ORM models and migration policy.
4. `docs/DICOM_PACS.md` — Orthanc, discovery, routing, transfer queue.
5. `docs/ROLES_PERMISSIONS.md` — authorization model.
6. `docs/STORAGE_BACKUP.md` — reports, attachments, DB and cloud backup.
7. `docs/DEPLOYMENT.md` — Docker deployment/upgrade/rollback.
8. `docs/CODE_MAP.md` — generated inventory of models/routes/functions.
9. `CHANGELOG.md` — version history from the documented baseline forward.

## Non-negotiable safety rules

- Do **not** delete or recreate the production database to solve schema errors.
- Do **not** change DICOM identifiers (Patient ID, Accession Number, StudyInstanceUID) silently.
- Do **not** bypass `require_perm()` / role checks on clinical, financial, PACS, user or administrative actions.
- Do **not** make transfer actions destructive. PACS send/resend is a copy/routing action; source studies must remain intact unless a separately authorized retention workflow explicitly deletes them.
- Do **not** hard-code production passwords, API keys, SMTP credentials or cloud secrets in source control.
- Do **not** modify existing migrations after they have been applied. Add a new migration.
- Do **not** rename database columns/tables or route endpoints casually; templates and integrations may depend on them.
- Do **not** expose Orthanc directly to the public Internet without authentication, TLS/reverse proxy and network controls.
- Keep audit logging for privileged/clinical/PACS changes.
- Keep branch isolation when a user is branch-scoped.

## Current architecture in one line

`Registration → Order/Accession → MWL/Modality → Orthanc PACS → PACS Intake/Reconciliation → Assignment → Reporting → Coordinator → Finalize/Delivery → Archive/Backup`

The PACS routing extension adds:

`Orthanc Study → Destination selection → C-ECHO test → Transfer Queue → Orthanc peer/modality send → Success/Failed/Retry/Cancel → Audit`

## Where to change what

- Main application, ORM models, most routes and business logic: `app.py`
- Workflow transition rules: `workflow_engine.py`
- PACS background intake/transfer processing: `pacs_worker.py`
- Backup scheduler/worker: `backup_worker.py`
- UI templates: `templates/`
- CSS/static assets: `static/`
- DB migrations: `migrations/versions/`
- Docker runtime: `Dockerfile`, `docker-compose.ris.yml`, `docker-compose.staging.yml`
- Automated/preflight checks: `preflight.py`, `schema_check.py`, `smoke_test.py`, `live_self_test.py`, `stabilization_self_test.py`
- Generated code inventory: `docs/CODE_MAP.md` via `python tools/generate_code_map.py`

## Recommended change workflow

1. Make a backup of DB + reports + attachments.
2. Create a new semantic version.
3. Add/modify models through a new migration when schema changes.
4. Add permission checks before exposing a route/action.
5. Add audit logging for state-changing operations.
6. Update the relevant documentation.
7. Regenerate `docs/CODE_MAP.md`.
8. Run compile/template/preflight tests.
9. Test on staging with a copy of representative data.
10. Deploy, verify health, then keep the previous package for rollback.

## Definition of done for a new feature

A feature is not complete until the code, permission model, migration (if needed), UI/API, audit behavior, failure behavior, documentation and tests are all considered.

## Versioning

- Patch `x.y.Z`: fixes, documentation, non-breaking maintenance.
- Minor `x.Y.0`: backward-compatible feature additions.
- Major `X.0.0`: breaking architecture/schema/API changes.

v5.31.1 intentionally changes documentation/maintainability only; v5.31.0 remains the functional baseline.

## v5.32.0 Storage & DR
Before changing storage, PACS archive paths, replication, backup or failover behavior, read `docs/STORAGE_DR.md` and `docs/DR_RUNBOOK.md`. Storage is vendor-neutral and addressed by stable logical codes + OS-visible mount paths. Never add storage credentials to database models or source control. Never automate destructive failover in a request handler; preserve fencing/split-brain safeguards and audit trails.
