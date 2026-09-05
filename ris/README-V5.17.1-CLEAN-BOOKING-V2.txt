RIS Web v5.17.1 — Clean Booking V2

NEW independent scheduling screen:
  /schedule/v2

Design principles:
- Backend links for every slot. Booking does not depend on popup JavaScript.
- Old scheduling page is preserved during validation.
- Booking form re-validates availability at Save time.

Booking blocks:
- Device inactive.
- Booking disabled.
- Operational status OUT_OF_SERVICE / MAINTENANCE / DISABLED.
- Outside device working hours.
- DeviceBlock / maintenance overlap.
- Existing appointment overlap based on procedure duration.
- Wrong modality.
- Wrong branch.
- Duplicate patient safety for new patients.

Device settings:
- Operational status.
- Booking enabled/disabled.
- Working start/end hours.
- Existing DeviceBlock maintenance periods remain supported.

Slots:
- 15-minute display.
- Occupied slot shows patient/exam/status.
- Available slot is a normal backend hyperlink.
- Blocked slot displays the exact blocking reason.

Tests:
- Routes.
- Booking helpers.
- Operational states.
- Backend-first slot links.
