# Architecture

## Runtime services

The standard Docker deployment contains:

- **ris-web** — Flask/Gunicorn RIS application.
- **ris-db** — PostgreSQL 16 database.
- **ris-pacs** — Orthanc PACS (external service on the shared `ris-network`).
- **pacs-worker** — periodically runs PACS auto-intake and transfer queue processing.
- **backup-worker** — scheduled report/attachment/database/cloud backup processor.

## Application layers

The project is currently a modular monolith centered around `app.py`. This is deliberate historical compatibility, not a recommendation to keep adding unlimited code to one file. New large features should prefer a service/module file while preserving existing route endpoints.

### Presentation

`templates/` contains server-rendered Jinja templates. `static/` contains UI assets.

### Business/domain logic

Most domain logic is currently in `app.py`; workflow-state authorization is extracted to `workflow_engine.py`.

### Persistence

SQLAlchemy models are defined in `app.py`. PostgreSQL is the production target. Alembic lives in `migrations/`.

### Integrations

- Orthanc REST API for PACS study query/routing.
- DICOM destination configuration for modality/workstation/PACS/archive targets.
- SMTP, Telegram, WhatsApp integration hooks.
- ERP integration hooks.
- Cloud backup via rclone.
- Word/reporting API and generated PDF/DOCX reporting.

## Clinical workflow

1. Patient registration / patient lookup.
2. Order creation and accession assignment.
3. Scheduling / appointment / worklist exposure.
4. Technician exam status.
5. PACS image reception in Orthanc.
6. PACS matching/reconciliation with RIS order.
7. Radiologist assignment/reporting.
8. Coordinator review when configured.
9. Final report/delivery/portal.
10. Archive and backup.

## PACS transfer workflow

1. Technician or privileged user opens case PACS actions.
2. Destination is selected from active, allowed destinations; branch scope is enforced for branch users.
3. Connectivity may be tested through C-ECHO/destination test.
4. A `PacsTransferJob` is queued.
5. `pacs-worker` processes pending/failed jobs subject to retry limits.
6. Status and image counters/errors are stored.
7. Retry/resend and cancel are explicit actions.
8. Relevant state-changing actions are audit logged.

## Architectural boundaries to preserve

- RIS owns patient/order/workflow/report metadata.
- Orthanc/PACS owns DICOM objects and StudyInstanceUID-level imaging storage.
- Filesystem/cloud storage owns generated reports and attachments.
- Do not use PACS as the authoritative source for financial/appointment state.
- Do not use the RIS database as a replacement for DICOM binary storage.

## Storage and Disaster Recovery layer (v5.32.0)
Storage is abstracted by `StorageLocation` logical targets. `ReplicationNode`, `ReplicationPolicy`, `ReplicationState` and `FailoverEvent` describe the DR topology and observed state. Infrastructure-specific mounts, storage credentials and promotion operations remain outside the Flask request path. See `STORAGE_DR.md`.
