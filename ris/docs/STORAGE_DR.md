# Storage & Disaster Recovery Architecture — v5.32.0

## Goals
RadBridge must remain independent of storage vendor, site and replication technology. Application code refers to stable logical codes and OS-visible mount paths. Infrastructure owns credentials, mounts, SAN zoning, iSCSI sessions, NFS/SMB authentication and storage-native replication.

## Storage Target Model
Each target has:
- `code`: immutable operational identifier, e.g. `CAI-PACS-PRI-01`.
- `branch_id`: optional branch scope; blank means global.
- `company_code`: optional tenant/company grouping.
- `storage_type`: PACS, ARCHIVE, BACKUP, REPORTS or ATTACHMENTS.
- `role`: PRIMARY, ARCHIVE, BACKUP or DR.
- `protocol`: LOCAL, NFS, SMB, ISCSI, S3 or GATEWAY.
- `path`: the path visible to the RIS/PACS host/container.
- vendor/endpoint/mount_source/filesystem metadata for operators only.
- capacity/free space/health values updated by a non-destructive health check.

Do not store passwords, CHAP secrets, SMB credentials, S3 secrets or storage admin credentials in the RIS database.

## Vendor examples
### Dell EMC over iSCSI
1. Storage team provisions and masks a LUN to the PACS host(s).
2. Linux discovers/logs into the target and mounts the filesystem using UUID or multipath device.
3. Persist the mount in the OS using the approved multipath/iSCSI procedure.
4. Register the resulting path, e.g. `/mnt/pacs/cairo`, in RadBridge with protocol `ISCSI` and vendor `Dell EMC`.
5. Orthanc/PACS storage is pointed to the same controlled mount path only after a planned migration and verification.

### QNAP over NFS
Mount `qnap01:/PACS_CAIRO` at `/mnt/pacs/cairo`, then register the target as `NFS`. Use server-side export controls and least privilege.

## Branch/company naming convention
Recommended code: `<COMPANY>-<BRANCH>-<PURPOSE>-<ROLE>-<NN>`.
Examples:
- `AIR-CAI-PACS-PRI-01`
- `AIR-CAI-PACS-DR-01`
- `AIR-SHR-REPORTS-PRI-01`
- `AIR-CORP-BACKUP-01`

Codes should not be recycled after decommissioning. Preserve them in audit and migration records.

## Storage migration rule
Never change a PACS storage path and assume old studies moved. Use a controlled migration:
1. Freeze or coordinate writes.
2. Copy data to the target.
3. Verify item counts and checksums/storage verification.
4. Test read-back of representative studies and reports.
5. Switch the configured mount/path.
6. Monitor errors and free space.
7. Keep the old copy read-only for the approved rollback window.
8. Delete only under a separate approved retention/change process.

## DR objects
`ReplicationNode` identifies PRIMARY/DR/ARCHIVE/WITNESS nodes. `ReplicationPolicy` states what should replicate, where, transport, mode, RPO and RTO. `ReplicationState` stores observed lag and health. `FailoverEvent` records PLAN/TEST/PROMOTE/FAILBACK requests.

Supported policy vocabulary:
- Scope: PACS, DATABASE, REPORTS, ATTACHMENTS, CONFIG, ALL.
- Transport: DICOM_FORWARD, POSTGRES_STREAMING, RSYNC, STORAGE_NATIVE, S3_REPLICATION.
- Mode: ASYNC, SYNC, SCHEDULED.

## Recommended split by data type
- PostgreSQL: PostgreSQL streaming replication / managed DB replication. Test promotion and backups separately.
- PACS DICOM: DICOM forward to DR PACS and/or storage-native replication. DICOM-level verification provides logical protection from storage corruption.
- Reports/attachments: filesystem or object replication with checksums/versioning.
- Config: Git/versioned configuration + encrypted secrets outside Git + replicated deployment manifests.
- Backups: independent immutable/offline copy. Replication is not a backup.

## Safety boundary
RadBridge does **not** run destructive infrastructure failover directly from a browser request. The UI records and audits the desired DR action. Promotion/demotion is executed by a reviewed runbook or infrastructure automation with independent access controls. This protects against accidental split brain, double-primary databases and unsafe PACS path changes.

## Target resolution
`resolve_storage_target()` chooses the preferred active target by workload type + role, then scope precedence: exact branch/company, branch, company, global; lower priority wins. `GET /api/storage/resolve` exposes the resolved target to authorized integration/operations clients. Resolution does not mount storage or change Orthanc automatically.
