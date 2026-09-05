# Database & Migration Guide

## Database

Production is designed for PostgreSQL. SQLAlchemy ORM models currently live in `app.py`.

Major domains include branches/users/roles, patients/orders/appointments, clinical workflow, reporting, PACS matching/routing, inventory, finance, communications, AI integrations, storage/backup and audit records.

## Source of truth

The ORM model definitions are the code-level schema contract. `docs/CODE_MAP.md` provides a generated model inventory, but always verify the model definition before changing schema.

## Migration policy

1. Never edit an already-applied migration.
2. Add one migration per coherent schema change.
3. Prefer additive, backward-compatible migrations.
4. For destructive changes, use expand/migrate/contract over multiple releases.
5. Back up the DB before production migrations.
6. Test upgrade against a realistic copy of production data.
7. Document downgrade/rollback limitations.

## Identity fields that require special care

- Patient ID
- Accession Number
- StudyInstanceUID / Orthanc study identifiers
- External ERP/reference IDs
- Report version/finalization references

Changes to these fields can break matching, reporting, portal links or PACS reconciliation.

## Audit data

`AuditLog` should remain append-oriented. Avoid rewriting historical audit entries.

## Useful schema checks

Run:

```bash
python schema_check.py
python preflight.py
```

When adding a model or migration, also regenerate the code map:

```bash
python tools/generate_code_map.py
```

## v5.32.0 storage / DR tables
- `storage_location`: extended with protocol, role, branch/company scope, vendor/mount metadata and health/capacity.
- `replication_node`: DR topology endpoint.
- `replication_policy`: desired replication relationship with scope/transport/mode/RPO/RTO.
- `replication_state`: observed replication health, lag, pending data and checkpoint.
- `failover_event`: audited DR plan/test/promote/failback request.

The application database stores no SAN/NAS/iSCSI/SMB/S3 secrets.
