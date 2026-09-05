# Storage & Backup

## Local application storage

Runtime paths are environment-controlled:

- `REPORT_DIR` (default `/app/report-files`) — generated/final report files.
- `ATTACHMENT_DIR` (default `/app/attachments`) — uploaded case/patient attachments.
- `BACKUP_DIR` (worker default `/app/backups`) — database dump staging.

Docker Compose mounts these paths to host directories so application containers can be replaced without losing files.

## PACS images

PACS images belong to the PACS/Orthanc storage layer. Do not put bulk DICOM image data into the RIS PostgreSQL database.

The backup worker deliberately does not copy PACS storage unless `PACS_STORAGE_PATH` is explicitly configured and the backup configuration requests PACS backup.

## Cloud backup

`backup_worker.py` uses rclone. A cloud configuration can independently include reports, attachments, database and optionally a mounted PACS archive.

Recommended separation:

- Reports/documents: frequent daily cloud backup.
- Database: frequent scheduled dump with retention.
- PACS images: separate capacity/retention policy because image volume is much larger.

## Restore principles

A restore plan must identify a consistent point for DB + reports + attachments. Restoring only the DB may leave report/attachment file references missing. PACS recovery is handled separately through the PACS archive/storage backup strategy.
