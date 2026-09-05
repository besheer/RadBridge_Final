v5.11 Workflow + PACS Tracking
- Forward-only: BOOKED -> ORDERED -> IN_PROGRESS -> EXAM_COMPLETED -> REPORTING -> VERIFIED -> FINAL
- Technician cannot move backward.
- Supervisor override requires a reason and is audited.
- PACS tracking page at /pacs/tracking.
- Orthanc lookup by Accession Number.
- Image count and PACS status shown.
- IMAGES_COMPLETE only after EXAM_COMPLETED and image count stable for 120 seconds.
- Existing Reporting, Nursing, Patient Portal and FINAL Notifications retained.
