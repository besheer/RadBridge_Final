# Development foundation — phase 1

This branch implements the first small architecture step without deploying to production. The legacy app remains a modularizing monolith; routes, DB tables and clinical rules are unchanged.

## What changed

- Pure readiness policy moved to `ris/domain/readiness.py`. The old module re-exports the same functions for existing callers.
- Added behavioral/purity contracts and a synthetic-only test runner.
- Added dedicated `compose.dev.yaml`, a development Dockerfile/initializer and example environment settings. Existing historical deployment files are not used.
- Captured exact resolved dependency versions in `development/constraints.txt`; install with the existing requirements plus those constraints.
- CI defines a full SQLite suite and an isolated PostgreSQL RT/readiness contract suite. Neither job deploys or uses production credentials.

## Start local RIS development (Ubuntu/Docker Compose v2)

```sh
cp development/.env.example development/.env.local
# Edit development-only credentials before using the local login.
docker compose --env-file development/.env.local -f compose.dev.yaml up --build -d
docker compose --env-file development/.env.local -f compose.dev.yaml ps
```

Open `http://127.0.0.1:18080/login`; the development seed creates the initial admin according to the existing seed function and the local password. The DB is not published to the host. The explicit initializer accepts only the Compose-local development database and never drops tables. It is not a migration/restore tool for existing production.

Only RIS/PostgreSQL are included in this first development stack. Real PACS, OHIF deployment, ONLYOFFICE, VPN/host collectors, omitted binary assets and external destinations are not provisioned by this Compose file. Image/editor clinical workflows require a separately reviewed synthetic integration setup. No external worker or delivery is started by default. The repository's conservative export omissions remain documented in CHECKPOINT_MANIFEST.json.

Stop with `docker compose --env-file development/.env.local -f compose.dev.yaml down`. Keep volumes for reuse. Do not use `down -v` against data you need to keep. Ignore `.env.local` and generated patient/report files in Git.

## Tests

```sh
python -m venv .venv
. .venv/bin/activate
python -m pip install -r ris/requirements.txt -c development/constraints.txt
python tools/run_tests.py
```

The runner forces in-memory SQLite and temporary report/attachment/backup directories. PostgreSQL mode requires an isolated `radbridge_dev_test` database owned by `radbridge_test` at localhost/127.0.0.1/postgres, with `postgresql+psycopg2` driver. Set RADBRIDGE_TEST_DATABASE_URL privately and run `python tools/run_tests.py --postgres`; the fixed suite resets only that synthetic database's schema. It copies/adapts fixtures in a temporary directory; production and repository fixtures are not modified.

## Next boundaries

After accepting this stage, extract one additional policy seam at a time and preserve callable/route/data contracts. Do not mass-rewrite app.py or introduce microservices before the validation gates in docs/blueprint/VALIDATION_PLAN.md. This PR does not make the repository a complete PACS/ONLYOFFICE deployment or disaster-recovery package.
