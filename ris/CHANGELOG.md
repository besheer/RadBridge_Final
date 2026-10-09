# v5.44.2 - Production Stabilization

- Fixed registration browser-validation dead submit.
- Moved MWL/assignment side effects after the main registration commit.
- Added reporting API authentication and scoped desktop-agent tokens.
- Fixed communications production role names and permission registry defects.
- Added cookie/origin/secret hardening and source-complete packaging.

# v5.32.0 — Storage & Disaster Recovery
- Added vendor-neutral storage target abstraction with branch/company mapping.
- Added external/NAS/SAN protocol metadata and health/capacity monitoring.
- Added DR nodes, replication policies/states, RPO/RTO and audited failover events.
- Added safe DR runbook and storage migration documentation.
- Added new permissions: storage.targets.view/manage, dr.view/manage/failover.

# Changelog

## 5.31.1 — Developer-Ready Documentation

- Added AI/developer handover guide.
- Added architecture, database, DICOM/PACS, permissions, storage/backup, deployment and testing documentation.
- Added generated code-map tooling.
- Added module/function documentation in core worker/workflow code and top-level application guidance without changing clinical behavior.
- Added explicit production secret/security warnings for example Compose values.

**Functional behavior:** intended to remain equivalent to v5.31.0.

## 5.31.0 — DICOM Resend & Routing

- Technician Send/Resend from case/worklist PACS actions.
- Branch-aware destination filtering.
- Destination connectivity/C-ECHO action.
- PACS transfer queue lifecycle with retry/cancel.
- Explicit resend allowed even after a prior successful send.
- Audit coverage for transfer operations.

## 5.30.1 — Auto Discovery

- DICOM node auto-discovery baseline and approval/blocking workflow.

Earlier historical release notes remain in the versioned `README-V*.txt/.md` files shipped with the project.
