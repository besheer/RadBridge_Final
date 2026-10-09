RIS Web v5.9.1 Logical Calendar Booking
=========================================
Core logic:
Calendar slot -> BOOKED Appointment only.
No Order and no MWL are created during booking.
Order remains created later by the established check-in/start-exam workflow.

Calendar:
- Day-style calendar grid
- Time rows at 15-minute intervals
- Device/room columns
- Previous/next day and date picker
- Branch/device filters
- Clicking an empty slot opens an in-page side panel

Booking side panel:
- Existing Patient
- New Patient inline
- New Arabic patient keeps original name
- Worklist Name supported
- Branch, procedure, device/time carried from selected slot
- Duplicate same patient/procedure/time is blocked

Known stabilization fixes consolidated:
- Appointment uses scheduled, not start_time
- Erroneous priority args removed from OrderConsumable and Payment constructors
- Existing Reporting, Patient Safety and Assignment code retained

Python and all Jinja templates validated before packaging.
