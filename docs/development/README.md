# RadBridge architecture development

Updated: 2026-10-16. This is an isolated modular-monolith architecture port prepared on `codex/radbridge-ready-for-review` to update draft PR #2 against GitHub `main`. It has not been merged/deployed to production. Clinical release metadata remains 5.46.9; architecture commits are not a new deployed release.

## Current source structure

- `ris/domain`: framework-free policies for assignment/readiness/identity/reporting/finance/inventory/registration/manual RT.
- `ris/application/components`: existing executable orchestration owners; compatibility bindings still require further inversion.
- `ris/application/services`: 29 registered narrow service boundaries, with application/repository/composition owners in the port registry.
- `ris/infrastructure`: 160 models in 14 model modules, unbound SQLAlchemy extension, repositories/adapters/resources/settings.
- `ris/web`: factory, routes/helpers/extensions and compatibility composition. Six former Flask service owners now live here with unchanged behavior (ADR 037).
- Original entry-point ownership: 949 functions in 32 component/route/helper modules; 76 migrated modules retain canonical legacy aliases. Registered routes remain 546. These are inventories, not a whole-project completion percentage.

Explicit boundaries cover assignment queries/mutations/grouped visits/monitoring; clinical scope/contacts; report save/edit leases/correction review; replacement settlement; original-lot returns; registration visits/insurance/demographic requests/appointment creation; readiness resolution/search/refresh/operations snapshot; collection/closing evidence/mutations; manual RT course, external plan record, session commands, support and read projections.

The latest architecture work adds branch scope to assignment monitoring, manual assignment, offer actions and the TAT dashboard; separates management permissions for offer-policy, doctor-profile and communication settings writes; and rejects zero-valued branch IDs in delegated user management (ADRs 045–052). The preceding port boundaries inject runtime explicitly into assignment-monitor routes (ADR 044) and branch collection authorization (ADR 043); ADR 042 does the same for insurance authorization and the outbound Worklist gate, and ADR 041 for stock locking and original-lot returns. ADR 038 creates an appointment for an existing patient through persistence/device-routing/slot-lock/restriction/actor/audit ports. Web composition still authorizes the branch and owns savepoint/commit/rollback, form parsing, flashes and redirects. Other booking/rescheduling/check-in workflows remain unfinished.

The returned-document prerequisite service (ADR 039) reads required history through a repository and receives quality-rule and attachment-count dependencies. It grants no review approval, identity correction or image-completion authority. Legacy technician/assignment/return handlers retain their signatures, scope and transaction ownership.

## Validation evidence

Current code/test head `79966a52a365cc2070c95bb06f30e40f5c4b0cc3` passed all nine GitHub Actions jobs in [run 38717259044](https://github.com/besheer/RadBridge_Final/actions/runs/38717259044): 2,152 SQLite tests passed, five skipped, all seven PostgreSQL suites passed, and the isolated development Docker smoke passed. The subsequent documentation head `b4b7b869ae9b1aed2d35253515892c139aed99aa` passed all nine jobs in [run 38717781992](https://github.com/besheer/RadBridge_Final/actions/runs/38717781992). These checks do not certify external PACS/editor/viewer behavior, browser role UAT, disaster recovery or production readiness.

The checker enforces domain/model/registered-port import rules and rejects direct Flask imports anywhere in application/services, including unregistered modules. The current static seam audit finds no direct Flask, SQLAlchemy, requests, web or infrastructure imports in `application/services`. Legacy application components still contain direct SQLAlchemy imports for schema/maintenance work; broad compatibility bindings, runtime resolution and injected model/HTTP callbacks remain coupling outside the narrow service boundaries. Passing guards does not certify every old service or integration.

## Source checks (Python 3.12)

From repository root on Ubuntu:

```sh
python -m venv .venv
. .venv/bin/activate
python -m pip install -r ris/requirements.txt -c development/constraints.txt
python tools/check_architecture.py
python tools/run_tests.py
python tools/audit_dependency_seams.py --output /tmp/radbridge-dependency-seams.json
```

On Windows use the virtual environment's Python and an appropriate output path. The runner forces synthetic SQLite and temporary report/attachment/backup directories. Unit/contract tests block real provider HTTP. The census reads source/manifests only, without importing the app, reading environment values, querying databases or calling providers. Counts are static evidence locations, not executed calls, vulnerabilities or completion percentages.

PostgreSQL accepts only the dedicated `radbridge_dev_test` database/user `radbridge_test`, driver `postgresql+psycopg2` and localhost/127.0.0.1/`postgres`. Set `RADBRIDGE_TEST_DATABASE_URL` privately, then run `python tools/run_tests.py --postgres --postgres-suite registration`. Available suites: clinical, assignment, scope, reporting, finance, inventory, registration. This mode resets only the guarded synthetic schema and adapts fixtures in a temporary source copy. Never use operational data.

Registration includes demographic/appointment creation dependencies and routes; finance includes delivery readiness; assignment includes monitoring. Those additions passed the published PostgreSQL suites. Returned-document evidence and inventory-runtime composition are included in the current test suites; exact commit-specific CI evidence is recorded in [implementation status](IMPLEMENTATION_STATUS.md).

## Fresh development deployment (Ubuntu / Docker Compose v2)

```sh
cp development/.env.example development/.env.local
# Set independent development-only credentials locally.
docker compose --env-file development/.env.local -f compose.dev.yaml up --build -d
docker compose --env-file development/.env.local -f compose.dev.yaml ps
```

Open `http://127.0.0.1:18080/login`. The initial admin follows the seed function and local password. The database is not published to the host. The explicit initializer accepts only the Compose-local development database; it is not a production migration/restore tool. Stop with `docker compose --env-file development/.env.local -f compose.dev.yaml down`; retain volumes when needed.

The stack includes RIS/PostgreSQL only. PACS, OHIF deployment, ONLYOFFICE, external workers, host collectors/VPN, all omitted binary assets and external destinations are not provisioned. Orthanc loopback defaults refer to the RIS container, not the host. Image/editor workflows require a separately configured synthetic integration environment. Export omissions remain in checkpoint/completeness metadata.

Development WSGI uses `web.factory:create_clinical_app()`; `app:app` remains compatible. Supported per-instance database/secret/storage/cookie/runtime-URL settings are isolated; some provider/host flags remain process-level (ADR 007).

## Remaining gates and references

Continue replacing broad Bindings/runtime and mixed orchestration. Open work includes readiness evidence/coordinator previews/workers, editor callbacks/finalization/exports and DB-file recovery, broader cash/stock transactions, patient/new-booking/reschedule workflows, staff execution/CSV apply, auxiliary query visibility and provider/host lifecycle.

Provision external synthetic PACS/editor/viewer acceptance and browser role UAT; test delayed/lost callbacks, partial transfer/retries, restart/recovery, role/branch visibility and upgrade/rollback/backup restoration. Unit tests and ownership do not close these gates. Production merge/deployment needs a separate release decision.

- [Implementation status](IMPLEMENTATION_STATUS.md): boundaries and commit-specific evidence.
- [Progress measures](PROGRESS.md): inventories and limits of percentage estimates.
- [Server transfer readiness](SERVER_TRANSFER_READINESS.md): development versus full clinical transfer.
- [Code map](../../ris/docs/CODE_MAP.md), [port registry](../../ris/application/port_contracts.json), component/module manifests.
- ADRs 001–051 document decisions and limitations. Consolidated status above is current.

Regenerate the code map with `python ris/tools/generate_code_map.py` after ownership changes. Historical blueprint/handover documents describe earlier snapshots; compare them with the actual reviewed commit.
