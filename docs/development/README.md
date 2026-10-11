# RadBridge architecture development

This branch implements a modular monolith on an isolated development branch. It has not been deployed to production. The data and route contracts are preserved; see [implementation status](IMPLEMENTATION_STATUS.md) for the distinction between implemented ownership boundaries and remaining runtime coupling.

## What changed

- Pure readiness policy moved to `ris/domain/readiness.py`. The old module re-exports the same functions for existing callers.
- Added behavioral/purity contracts and a synthetic-only test runner.
- Added dedicated `compose.dev.yaml`, a development Dockerfile/initializer and example environment settings. Existing historical deployment files are not used.
- Captured exact resolved dependency versions in `development/constraints.txt`; install with the existing requirements plus those constraints.
- CI defines a full SQLite suite and an isolated PostgreSQL RT/readiness contract suite. Neither job deploys or uses production credentials.
- All 160 ORM definitions belong to 14 canonical infrastructure model modules, with one shared unbound SQLAlchemy extension.
- Ten independent policy modules moved into the domain packages; legacy imports retain module/object identity.
- 949 executable handlers belong to 32 web/application modules with explicit compatibility dependencies. HTTP helpers and request hooks belong to the web layer; application components do not receive HTTP framework dependencies.
- 76 existing services, adapters, extensions and worker modules moved into owned packages. Legacy import and CLI facades preserve callers.
- Web settings and clinical application construction are independent per supported instance settings. Development WSGI uses `web.factory:create_clinical_app()`; `app:app` remains compatible. See ADR 007 for configuration/lifecycle contracts.
- Distribution policy, active-case and capacity queries execute through an explicitly injected service/repository pair. Remaining distribution orchestration is marked as web compatibility; see ADR 009.
- Start-deadline and candidate-ordering decisions execute in `domain.assignment.distribution` over supplied facts, preserving the existing distribution keys; see ADR 010.
- Assignment mutation and offer acceptance receive explicit repository and policy ports; PostgreSQL CI checks clinical and assignment suites separately. See ADR 011.

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

Ownership extraction is implemented across the listed areas. Continue replacing compatibility bindings with narrow use-case dependencies, preserving callable/route/data contracts. Synthetic unit/contract tests block real HTTP transport; external-service acceptance belongs in a separate reviewed integration environment. Do not introduce microservices before the validation gates in docs/blueprint/VALIDATION_PLAN.md. This branch does not make the repository a complete PACS/ONLYOFFICE deployment or disaster-recovery package.

Clinical scope validation, access decisions and SQL queries have distinct owners (ADR 012); web registration retains CSRF, guards and listener lifecycle. PostgreSQL CI runs clinical, assignment and scope suites independently.

Grouped visit workflows now execute through explicit evidence/repository/policy ports (ADR 013), preserving patient/branch/source identity, qualification, capacity and deadline behavior.

Report saving, editing leases, correction request/review, replacement entitlement settlement, original-lot inventory returns and visit registration now have explicit workflow/evidence/repository dependencies (ADRs 014–019). Insurance readiness uses latest-decision evidence (ADR 020); readiness resolution mutations use explicit repository and clock ports (ADR 021). Read-only RIS search has explicit query and ranking ownership (ADR 022). Readiness scheduling and refresh use explicit dependencies while HTTP ownership remains at the web edge (ADR 023). Fourteen service boundaries are listed in `ris/application/port_contracts.json` and enforced by `python tools/check_architecture.py`; this does not claim all legacy use cases are migrated.

PostgreSQL CI runs independent `clinical`, `assignment`, `scope`, `reporting`, `finance`, `inventory` and `registration` suites. Select one locally with `python tools/run_tests.py --postgres --postgres-suite registration` (or another listed suite), using only the guarded synthetic database. SQLite runs the whole suite. Docker smoke checks the separate RIS/PostgreSQL development stack; external PACS/editor/viewer acceptance remains required.

Regenerate `ris/docs/CODE_MAP.md` with `python ris/tools/generate_code_map.py` after ownership changes. It links models, composed routes, legacy module owners and the explicit port registry to executable code.



