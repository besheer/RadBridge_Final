# DR Runbook — Operator Checklist

## Before an incident
- Confirm Primary and DR node codes, storage codes, AE Titles, IPs and DNS names.
- Record RPO/RTO for Database, PACS, Reports, Attachments and Config.
- Test backups independently from replication.
- Perform scheduled DR drills and record them as `TEST` events.
- Verify that DR hosts can reach modalities/PACS peers but do not create two active MWL/PACS writers unintentionally.

## Failover decision
1. Declare incident and open change/incident reference.
2. Confirm Primary is unavailable or isolated.
3. Inspect replication lag and last successful checkpoint.
4. Prevent split brain: fence/isolate Primary before promotion where applicable.
5. Record a `PROMOTE` request in RadBridge.
6. Promote PostgreSQL DR using the approved PostgreSQL procedure.
7. Activate DR PACS/storage endpoints and validate mounted filesystems.
8. Switch DNS/reverse proxy/routes as designed.
9. Validate: login, registration, MWL, DICOM C-ECHO, new study ingest, old study read, reporting, finalize and audit.
10. Monitor error logs, queue depth and replication state.

## Failback
1. Do not simply power the old Primary back into production.
2. Rebuild/resynchronize it from the current authoritative DR node.
3. Verify data consistency.
4. Schedule a controlled reverse transition.
5. Record `FAILBACK` and change reference.
6. Re-enable normal replication direction and monitor.

## Minimum drill evidence
Keep incident/change ID, timestamps, last replicated checkpoint, measured RPO, measured RTO, validation results and responsible operator in audit/operations records.
