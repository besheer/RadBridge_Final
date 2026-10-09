RIS Web v5.4.3 Stable
=====================
Fixes:
- Adds missing appointment_action route used by Appointments template.
- Implements Confirm / Cancel / No-show / Check-in.
- Check-in creates radiology Order and sends MWL automatically.
- Keeps only one db.create_all() invocation.
- Makes supported ALTER COLUMN migrations idempotent with IF NOT EXISTS.
- Gunicorn remains at 1 worker temporarily to avoid import-time migration races.
- Health API reports version 5.4.3.
- Preserves bilingual procedure catalog, accounting, receivables, attachments, delivery, calendar and reporting.

Static Python validation passed.
Core routes validated.
Unmatched template url_for references for later review:
admin_device_blocks
admin_device_schedules
static
