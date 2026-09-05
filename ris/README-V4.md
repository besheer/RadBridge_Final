# RIS Web v4 — Reporting API + Microsoft Word Add-in

## New in v4
- Reporting API: case lookup, Save Draft, Finalize, health check.
- Microsoft Word task-pane Add-in hosted by the RIS.
- Add-in automatically reads `RIS_ACCESSION` from the Word report.
- Save Draft uploads the currently open DOCX directly from Word.
- Finalize stores versioned DOCX + generated PDF and locks the report.
- New `ReportVersion` audit/history table; existing v3 tables remain unchanged.
- "Open in Microsoft Word" uses the Microsoft Office `ms-word:ofe|u|...` URI scheme.

## Important production requirement
Use HTTPS for `RIS_PUBLIC_URL` before production deployment of the Office Add-in. Microsoft strongly recommends HTTPS for Office Add-ins and requires it for Office on the web / Marketplace.

## Useful endpoints
- `/api/reporting/health`
- `/api/reporting/cases/<ACCESSION>`
- `/word-addin/taskpane`
- `/word-addin/manifest.xml`
