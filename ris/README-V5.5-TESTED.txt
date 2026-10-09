RIS Web v5.5 Tested Build
==========================

Fixes merged:
- Attachment upload directory defined and persisted in Docker Compose.
- Attachment upload/download permissions.
- New Order now receives Referring Doctors and stores referring_doctor_id.
- Appointment has device_id, checked_in_at, cancelled_at.
- Booking page receives devices.
- /api/slots implemented from DeviceSchedule, procedure duration, breaks and maintenance blocks.
- Appointment Confirm/Cancel/No-show/Check-in implemented.
- Check-in avoids duplicate Orders and sends MWL after arrival.
- Existing schema migration adds Appointment fields and ReportVersion upload fields safely.
- Analytics fixes from v5.4.5 retained.
- One Gunicorn worker retained until migrations are moved out of app import.

Testing:
- preflight.py performs static route/template checks.
- smoke_test.py runs a full isolated Flask workflow using a temporary SQLite database.
  It does NOT use the production PostgreSQL DB.

On server after build run:
  docker exec ris-web python /app/preflight.py
  docker exec ris-web python /app/smoke_test.py

Do not put this into production use if smoke_test.py reports any FAIL.
