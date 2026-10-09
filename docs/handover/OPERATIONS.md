# Operation, development and release runbook

## Recorded deployment, not a new deployment instruction

Production application URL: `https://rispacs.radbridges.com`. Source symlink: `/opt/radbridge/current`; its recorded resolved checkout is `/opt/radbridge/releases/9cc0967fdd23f186c06e519e65e2eea9948b0d4a`. The directory name is historical; `git rev-parse HEAD` is authoritative.

| Service | Recorded container | Host binding |
|---|---|---|
| Current RIS | `radbridge-ris-95fee0e-canary` | `127.0.0.1:18092` → 8000 |
| Stopped RIS rollback | `radbridge-ris-rollback-radiotherapy-20261009` | Previous service configuration retained |
| OHIF | `radbridge-ohif-clean-canary` | Recorded host port 18096 |
| ONLYOFFICE | `radbridge-onlyoffice-clean-canary` | Recorded host port 18097 |

Current RIS image at release: `radbridge-ris:radiotherapy-cf59dc1-20261009`, ID `sha256:4681ea9477e6853494a63f8d5729f8343591e5fc777970d6aa1bb3b881bd8804`. Rollback RIS image: `radbridge-ris:staff-workflow-a7dcd44-20261009`. Re-inspect before operating these resources: names, ports and image availability can change after this checkpoint.

### Read-only first checks on the host

```sh
git -C /opt/radbridge/current rev-parse HEAD
git -C /opt/radbridge/current status --short
docker inspect --format '{{.State.Health.Status}}' radbridge-ris-95fee0e-canary
docker inspect --format '{{.Image}}' radbridge-ris-95fee0e-canary
```

Do not print complete container environment/inspect payloads or patient-bearing logs. Private deployment configuration is not in GitHub. Resolve actual networking, mounts and reverse-proxy upstream privately through the operating owner. Follow the repository's operational command protocol on that host; the examples above show the command bodies.

## Development tests: synthetic environment only

Restore any required omitted non-sensitive assets before expecting full UI/build parity. Review `ris/requirements.txt`, `ris/Dockerfile`, test fixtures and any required external service mocks. The commands below are a developer recipe, **not a new installation verified in this documentation task**.

```sh
cd ris
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
export DATABASE_URL='sqlite:///:memory:'
export RADBRIDGE_BOOTSTRAP_ON_IMPORT=0
export SECRET_KEY='SYNTHETIC-DEVELOPMENT-ONLY-CHANGE-THIS'
export REPORT_DIR="$(mktemp -d)"
export ATTACHMENT_DIR="$(mktemp -d)"
python -m pytest -q --disable-warnings
```

`tests/conftest.py` forces an in-memory SQLite database before importing `app` and creates/drops only that test schema. Never reuse a production DSN for tests. The PostgreSQL concurrency test needs an independently provisioned temporary PostgreSQL database and a test-only fixture adaptation: the standard conftest ignores a PostgreSQL DSN. The prior release used PostgreSQL 16 with no published ports and synthetic credentials; its runner is retained on the maintainer's workspace, not supplied as a turnkey PG runner here.

## Compose and configuration

`ris/docker-compose.ris.yml` and other Compose files are source references. They include historical container names, URLs, host ports, workers and volumes; they do **not** reproduce the recorded live canary configuration. Do not run them against the live host as an upgrade shortcut.

Relevant environment names include `DATABASE_URL`, `SECRET_KEY`, `RADBRIDGE_BOOTSTRAP_ON_IMPORT`, `RIS_ADMIN_PASSWORD`, `REPORT_DIR`, `ATTACHMENT_DIR`, `PACS_ORTHANC_URL`, `PACS_ORTHANC_USER`, `PACS_ORTHANC_PASSWORD`, and module-specific viewer/editor/security settings. Check actual source usage rather than copying values from old examples. Supply real secrets privately, outside Git. Use the `postgresql+psycopg2://` driver with this dependency set.

`bootstrap_db.py` invokes schema creation, migrations and seed functions. Treat it as an explicit fresh-development initializer requiring review; never run it blindly on production. Bootstrapping is disabled on the recorded live RIS service with `RADBRIDGE_BOOTSTRAP_ON_IMPORT=0`.

## Release sequence

1. Pin the exact source revision and verify a clean working tree. Read current operating instructions and authorization.
2. Make the change on a dedicated branch. Inspect existing contracts and add relevant policy/role tests.
3. Validate imports and templates in the runtime; run the meaningful test suite and synthetic PostgreSQL checks when affected.
4. Review Arabic/English desktop and mobile pages, direct URL denial, console errors and failed requests.
5. Commit; build one candidate image from the verified source. Track file hashes, base image and dependencies. Do not patch a running container.
6. Apply only the reviewed additive migration if needed; preserve existing records. RT uses `radiotherapy_migration.apply(m)` for six tables only.
7. Privately preserve the current container config; perform a controlled replacement on the same port while retaining an exact rollback target.
8. Verify public login, authenticated affected routes, worker health, persisted state, callbacks and unchanged unrelated services. Record acceptance.
9. Remove only explicitly inspected obsolete temporary resources. Retain the current and rollback image/service. Update the GitHub snapshot and documents after acceptance.

## Rollback decision

A code rollback is not a database restore. At this release, the older stopped RIS container is the immediate rollback target. Verify its ID/image/configuration before any swap; avoid simultaneous listeners on the same host port. Route traffic back only after health/authenticated checks. Retain RT tables and records if reverting application code. Do not drop tables, overwrite reports or restore an old DB merely to undo a UI release. Restore actions require a separate incident decision and a tested recovery plan.
