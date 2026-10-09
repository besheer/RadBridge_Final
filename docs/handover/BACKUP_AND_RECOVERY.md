# Backup, recovery and GitHub update policy

## What this repository protects

The reviewed source snapshot supports code inspection, continuation, comparison and recovery of **uploaded** files. Subsequent commits preserve changes from the import onward. The server checkpoint tag pins the complete original tracked source/history on that server, but is not an independent off-server Git backup.

GitHub snapshot exclusions are intentional: binary documentation/assets, legacy backups, patient data/storage, database dumps, credentials/private configuration. Consequently a clone alone cannot reproduce the entire deployed application or restore the hospital's state.

## Full recovery set still required

| Component | Required separately | Validation |
|---|---|---|
| PostgreSQL | Consistent encrypted backup including schema, records and relevant metadata | Restore into isolated PostgreSQL, constraints and application checks |
| Reports and attachments | Versioned files and their recorded content hashes/paths | Cross-check referenced versions, FINAL immutability and readable attachments |
| PACS | Orthanc image storage and its corresponding index/database/config | Study/series/instance inventory and UID-level retrieval checks |
| Operating configuration | Docker/Compose or controlled container spec, networks, mounts, proxy, workers, schedules and host services | Reconstruct connectivity without exposing management ports |
| Secrets | Encrypted separate custody for application/editor/PACS/SMTP/VPN/storage keys and credentials | Authorized recovery, rotation policy and no Git exposure |
| Binary UI/runtime assets | Verified non-sensitive original assets omitted by the snapshot | Build, template and viewer parity |
| Audit and queue state | Persistent audit/event and any transport/retry records | Recovery preserves history, pending attempts and partial-send accounting |

Select retention, encryption, off-server storage and access ownership with the operator. Record a required recovery point objective (RPO) and recovery time objective (RTO); neither is currently established by this GitHub upload. A backup-worker file or success email is insufficient without a restore exercise.

## Restore rehearsal order

1. Inventory the recovery set and checksums privately; choose a consistent recovery point.
2. Build an isolated host/network with no patient-data access from public development tools.
3. Restore DB and file/PACS storage together; restore compatible source/image and private operating configuration.
4. Disable real outbound delivery, assignment notifications and DICOM transfers during validation.
5. Verify identities, branches, roles, report versions, attachments, study counts, queue persistence and audit continuity.
6. Exercise representative allowed/denied workflows with an approved test scope.
7. Document restore time and gaps. Any real service cutover requires a separate operating decision.

## Updating this repository

After an accepted release, export a fresh reviewed source snapshot from the authoritative checkout. Scan the whole export, not only `.env`. Inspect binary assets before including them. Update additions, modifications **and deletions**; copying new files over an old checkout can leave removed code behind.

Create a coherent commit referencing the original source revision and acceptance evidence. Update `CHECKPOINT_MANIFEST.json`, documentation baseline, exclusions and operational release notes. Use an annotated release/checkpoint tag if the maintainer chooses a tag policy. Verify repository privacy and affected file/blob hashes after upload. Preserve unrelated user changes; avoid force pushing, rewriting the private import history or uploading old server history before a dedicated historical secret scan.

There is no recurring/scheduled GitHub backup automation configured by this handover. Updates remain an explicit maintainer action. Never commit real `.env`, database archives, exported users, report files or patient screenshots, even to a private repository.
