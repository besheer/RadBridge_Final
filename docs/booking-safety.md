Legacy appointment safety — 2026-10-07

POST /appointments now delegates to an extracted legacy_booking helper, retaining
appointment permissions and registration branch policy. It validates existing
patient, active branch/procedure, branch examination mapping, and matching device.
If no device is selected, existing branch routing is used. The canonical
booking_restriction_reason checks controls, device status, hours, maintenance and
overlap. acquire_booking_slot_lock serializes PostgreSQL device/day checks before
checking availability. Adjacent slots and other devices remain valid; cancelled
and no-show slots may be reused. Procedure duration is stored in Appointment.
Creation and audit are in one transaction; validation uses a savepoint and no
existing booking is overwritten. No real patient booking or MWL is sent for UAT.
15 isolated ORM tests cover overlap, adjacency, device restrictions and routing.
SQLite tests do not exercise concurrent PostgreSQL requests. Visual UAT pending
browser tool initialization recovery. No changes to patient or report files.
