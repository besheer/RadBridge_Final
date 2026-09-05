RIS v5.27.3.1 Re-authenticated Data Administration

Adds UI-only sensitive operations:
- Backup All Patient Data: requires current user's password.
- Delete All Patient Operational Data: requires current user's password.
- Dedicated permissions backup.all_patients and data.delete.all_patients.
- Wrong password makes no data change and is audit logged.
- Delete-all preserves Users/Roles/Branches/Procedures/configuration/inventory master data/Audit Log.
- Dependent patient/order tables are discovered from SQLAlchemy FK metadata and deleted child-first.
- Reports/attachments are moved to a quarantine folder instead of permanently erased.
- PACS/DICOM studies are not deleted.
- Browser confirmation is also shown before delete-all.
- hashlib import hotfix is included.

Also preserves v5.27.3 Backup/Storage/Data Administration, inventory, nursing, finance, RIS Studio and prior Golden fixes.
