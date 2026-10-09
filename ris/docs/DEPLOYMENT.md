# Deployment, Upgrade & Rollback

## Prerequisites

- Docker Engine + Docker Compose plugin.
- External Docker network `ris-network`.
- Orthanc/PACS service reachable as `ris-pacs` on that network, or environment values adjusted accordingly.
- Persistent host storage for PostgreSQL, reports, attachments and backups.

## Security before production

`docker-compose.ris.yml` contains development/example `ChangeMe_*` values. Replace all passwords and `SECRET_KEY` using protected environment configuration before production. Do not commit real secrets into the package.

## Standard upgrade procedure

1. Back up PostgreSQL, reports and attachments.
2. Save the currently running package/version and compose/environment files.
3. Extract the new version into a new release directory.
4. Compare environment variables and compose changes.
5. Apply new DB migrations if the release includes them.
6. Build the application image.
7. Run preflight/compile/template checks.
8. Start/recreate `ris-web`, `pacs-worker`, `backup-worker` as needed.
9. Verify application login, DB health, Orthanc health, worklists, report opening and PACS queue.
10. Keep the prior release available until verification is complete.

## Suggested commands

```bash
python -m py_compile app.py workflow_engine.py pacs_worker.py backup_worker.py
python tools/generate_code_map.py
python preflight.py

docker compose -f docker-compose.ris.yml build
docker compose -f docker-compose.ris.yml up -d
```

## Rollback

Application-only rollback: restore the previous release image/files and recreate services.

Schema rollback is more sensitive. If a migration is not safely reversible, restore the pre-upgrade database backup rather than improvising destructive SQL.

## Health checks after deployment

- PostgreSQL container healthy.
- `ris-web` HTTP endpoint responds.
- `/api/reporting/health` responds as expected.
- Orthanc/PACS reachable.
- `pacs-worker` logs show intake/transfer loop without repeated errors.
- Backup worker can see configured storage and DB.
