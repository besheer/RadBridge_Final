RadBridge v5.30.1 — DICOM Auto Discovery

Adds to v5.30:
- Automatic registry of AE Titles observed during PACS Auto Intake.
- Tracks AE Title, last seen time, modality, study count and optional host/port.
- PENDING / APPROVED / BLOCKED states.
- Admin can classify a discovered node as MODALITY / VIEWER / UNKNOWN.
- Approval can map to a branch and, if IP/port are supplied, automatically create/sync a DICOM Destination.
- Manual viewer registration for C-MOVE or resend use-cases.
- Permissive Orthanc PACS baseline remains: DCM4CHEE / 11112 with C-ECHO/STORE/FIND/GET/MOVE enabled.

Important DICOM behavior:
- Any modality that can reach the PACS can C-STORE when permissive mode is enabled.
- Any viewer can C-FIND / C-GET without a pre-registered destination if it can reach PACS.
- C-MOVE still needs a known, routable destination AE/IP/port.
- Orthanc study metadata does not always expose the TCP source IP of the sender. In that case RadBridge records the AE Title and lets an admin supply/confirm host/port.
