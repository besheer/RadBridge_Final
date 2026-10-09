RadBridge v5.30 — PACS Workflow, Archive, Coordinator & Cloud Backup

Preserved from previous release:
- v5.29 Platform Control / isolated tenant architecture
- branded login, Executive Analytics, sidebar search
- finance, inventory, nursing, reporting and data administration
- Stock Ledger fix and existing PACS reconciliation / assignment workflow

New:
1. PACS Auto Intake
   - Polls Orthanc continuously.
   - Exact Accession / safe patient matches link to existing RIS orders.
   - Unmatched PACS studies create a provisional RIS Patient + Order automatically.
   - Generated RIS Patient ID and Accession when required.
   - Status IMAGES_RECEIVED / EXAM_COMPLETED / unpaid until reception verifies details.
   - StudyInstanceUID / Orthanc Study ID de-duplication.

2. Workflow Command Center
   - Exam completed but no images.
   - Images received but unassigned.
   - Assignment delays.
   - PACS offline / problem queue.
   - Doctor workspace server/PACS and queue health.

3. Governed Doctor Open Pool
   - Take Case now respects readiness and assignment eligibility rules.
   - Prevents stealing cases assigned to another radiologist.

4. DICOM Destinations & PACS Actions
   - Admin-defined modality/workstation/PACS/backup/archive targets.
   - Technician/manual resend from a case.
   - Orthanc destination synchronization.
   - Transfer queue + retry history.

5. Auto Routing & Archive
   - Rules by branch, modality and source AE.
   - Copy to Backup PACS / Archive PACS.
   - Archive verification tracked.
   - No automatic primary deletion in this release: cleanup must only occur after verified archive copies.

6. Case Coordinator / Typist
   - New CASE_COORDINATOR role.
   - READY_FORMATTING → FORMATTING → READY_APPROVAL workflow.
   - Coordinator cannot finalize the medical report.
   - Return to doctor with notes.
   - Version audit records role, summary, hash and file size.

7. Storage & Cloud Backup
   - Explicit storage map for Reports / Attachments / Exports / Backups / PACS.
   - Reports and documents are separated from DICOM storage.
   - rclone-backed providers: Google Drive, OneDrive, S3, SFTP, etc.
   - Daily incremental/copy backup worker for Reports / Attachments / PostgreSQL.
   - PACS cloud copying is optional because image volume is usually large.
   - Credentials remain in rclone.conf / environment secrets, not clinical DB.

8. Requested PACS baseline
   - AE Title: DCM4CHEE
   - DICOM Port: 11112
   - Web Port: 8042
   - permissive C-ECHO / C-STORE / C-FIND / C-GET / C-MOVE configuration template.
   Note: C-MOVE still requires a routable destination AE/IP/port; C-GET is better through NAT.

Deployment:
- deploy/docker-compose.pacs-DCM4CHEE-11112.yml
- docker-compose.ris.yml now includes pacs-worker and backup-worker.
- Configure rclone credentials in ./rclone/rclone.conf if cloud backup is enabled.
