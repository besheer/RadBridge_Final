RIS Web v5.1
================
Adds:
- Arabic / English UI switch with RTL support.
- Hybrid Reporting: Word Agent + manual upload of DOCX/DOC/ODT/PDF.
- LibreOffice/OpenOffice compatibility through normal document files.
- Analytics center with operational + financial KPIs and CSV export.
- Import/Export center for Procedures, Contracts, Consumables and Devices.
- Appointments module for Call Center.
- Referring Doctors master data and order linkage.
- New granular permissions for analytics/import/export/appointments/referrers.
- Existing PACS, MWL, Contracts, Inventory, Users/Roles and Reporting retained.

Upgrade:
Preserve ris-db and report-files from v5 before replacing application files.

Important production follow-ups:
- Add SSO/2FA and password policy.
- Add patient merge / duplicate resolution.
- Add addendum workflow and e-signature.
- Add backup/restore + retention policy.
- Add HL7/FHIR integration when connecting HIS/EMR.
- Add notification engine (SMS/WhatsApp/email) only after provider selection.
