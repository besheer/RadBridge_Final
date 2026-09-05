RIS Web v5.12 Admin Management

Added:
- Consumables CRUD-style editing: name, unit, reorder level, unit cost, active/inactive.
- Audited stock adjustments with mandatory reason.
- Procedure default consumables add/update/remove.
- Nursing actual consumables confirmation is locked after first confirmation.
- Nursing confirmation deducts actual quantities from stock.
- Supervisor correction via consumables.correct; reason required; stock delta reconciled and audited.
- User management: create, edit role/branch/status, reset password.
- New users and password resets require password change at next login.
- Role editor includes consumables.correct and workflow.override.
- Exam workflow supervisor override now requires workflow.override.
- Database migration adds user password-control fields and nursing correction fields.
- Preserves PACS tracking, exam workflow, reporting, portal and notifications.

Important deployment note:
Use the current server docker-compose.ris.yml so PACS credentials and local environment values are preserved.
