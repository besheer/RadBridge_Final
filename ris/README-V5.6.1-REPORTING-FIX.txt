RIS Web v5.6.1 Reporting Fix
================================
Fixes:
- PACS public URL no longer derives from n8n hostname.
- Default PACS public URL: http://ris.dynuddns.net:8042
- Prevents duplicated /ui/app//ui/ paths.
- Open Images falls back to Orthanc home when StudyInstanceUID is unavailable.
- Upload Report restored and always visible for non-final reports.
- Web Report Editor has explicit Save Draft and Finalize Report buttons.
- Finalizing from web sets report/order FINAL and stores version/audit.
- Word Agent and direct DOCX download remain available.
- Current uploaded report file remains downloadable.
Static route/template/UI validation passed.
