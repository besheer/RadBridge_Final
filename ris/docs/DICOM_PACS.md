# DICOM / PACS Developer Guide

## Components

- Orthanc is the DICOM archive/PACS service used by RadBridge.
- RIS stores workflow metadata and links orders to PACS studies.
- `pacs-worker` performs automatic PACS intake and transfer queue processing.

## Important models

- `PacsStudyMatch` — RIS/PACS match state.
- `PacsStudyInbox` — studies discovered/intaken from PACS.
- `DiscoveredDicomNode` — auto-discovered candidate DICOM nodes.
- `DicomDestination` — approved DICOM send destinations.
- `PacsRoutingRule` — routing rules.
- `PacsTransferJob` — queued send/resend jobs and status.

## Destination types

Destinations can represent modalities, workstations, PACS peers, archive or backup targets. The exact transport is implemented through the Orthanc integration and destination configuration.

## Technician send/resend

Technicians with `pacs.transfer` can send/resend a study to an allowed destination. Branch-scoped technicians only see destinations assigned to their branch or global destinations. A successful historical transfer must not prevent a deliberate new resend.

Expected job lifecycle:

`PENDING → SENDING → SUCCESS`

Failure/operations states include:

`FAILED`, `CANCELLED`, and explicit `Retry/Resend` actions.

## Safety requirements

- Validate destination is active and manual send is allowed.
- Enforce branch scope.
- Validate the order has/resolve its PACS study before queueing.
- Prefer C-ECHO/connectivity validation before clinical use.
- Never delete the source study as part of send/resend.
- Keep attempt count and last error.
- Audit who sent, resent, retried, cancelled or approved a destination.
- Never silently alter StudyInstanceUID to make routing work.

## Matching/reconciliation

PACS matching should prefer deterministic identifiers such as accession and DICOM UIDs and should avoid unsafe automatic merges where identity is ambiguous. Manual reconciliation must remain auditable.

## Auto discovery

Auto-discovered nodes start as candidates. Approval should create/activate a trusted destination; blocking prevents accidental use. Discovery does not mean a node is automatically trusted for clinical routing.

## Troubleshooting order

1. Confirm Orthanc is reachable from `ris-web`/`pacs-worker`.
2. Verify Orthanc credentials.
3. C-ECHO/test destination.
4. Verify AE Title, host and port.
5. Check `PacsTransferJob.last_error` and attempt count.
6. Check Orthanc logs.
7. Confirm network/firewall/NAT path.
8. Confirm destination accepts the called/calling AE configuration.
