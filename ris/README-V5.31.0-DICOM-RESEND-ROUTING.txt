RadBridge v5.31.0 — Technician DICOM Resend & Multi-PACS Routing

Built on v5.30.1 Auto Discovery.

New in v5.31.0:
- Technician role receives pacs.transfer permission.
- Direct PACS Send / Resend action from Technician Worklist when images exist.
- Manual send to approved MODALITY, WORKSTATION, PACS, BACKUP or ARCHIVE destinations.
- Branch-aware destination visibility for technician/service users.
- True resend: a successful previous transfer no longer suppresses a new manual resend job.
- AUTO_ROUTE remains idempotent to prevent duplicate automatic copies.
- DICOM C-ECHO test before C-STORE transfer.
- Transfer lifecycle: PENDING -> SENDING -> SUCCESS / FAILED, plus CANCELLED.
- Retry/Resend and Cancel actions.
- Attempts, start/completion/cancel timestamps and image-count progress tracking.
- Audit events for queue, retry, cancel and successful C-ECHO tests.
- Existing database auto-migration adds new pacs_transfer_job tracking columns.

Safety / behavior:
- Technician cannot create/edit destinations; Admin controls DICOM Destinations.
- Technician only sees global destinations or destinations mapped to the technician branch.
- C-STORE is executed by Orthanc after C-ECHO validation.
- No patient/study deletion is added.
