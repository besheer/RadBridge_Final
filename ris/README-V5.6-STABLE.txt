RIS Web v5.6 Stable Recovery Edition
========================================
Purpose: stability and recovery paths, not new feature expansion.

Recovery paths:
1) Word Agent automatic opening.
2) Direct DOCX download (Word / LibreOffice / OpenOffice).
3) Manual upload DOCX/DOC/ODT/PDF.
4) Web Draft editor as last reporting fallback.
5) PACS button opens study if StudyInstanceUID exists, otherwise PACS home.
6) Friendly 404/500 pages with Error ID instead of blank Internal Server Error.
7) /admin/diagnostics checks DB, PACS, report storage, attachments, Word Agent and critical routes.
8) Health API returns database/PACS/storage/agent status.
9) Report file naming: PatientID_Accession_vNNN_STATUS.ext.
10) One Gunicorn worker retained while migrations remain import-time.

Before production:
python3 preflight.py
After start:
docker exec ris-web python /app/live_self_test.py
curl https://ris.dynuddns.net/api/reporting/health
