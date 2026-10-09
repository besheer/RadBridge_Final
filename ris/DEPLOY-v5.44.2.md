# v5.44.2 deployment runbook

Do not deploy directly over the live container without completing the validation steps below.

## 1. Pre-deployment backup

Run the existing automated backup service and verify its checksum/restore process before cutover.

## 2. Build image

```bash
cd /opt/ris-pacs/releases/v5.44.2-production-stabilization
./scripts/v5442_preflight.sh

docker build --no-cache \
  --build-arg RADBRIDGE_VERSION=5.44.2 \
  -t radbridge-ris:v5.44.2-production-stabilization .
```

## 3. Required runtime settings

Keep the existing production values for DATABASE_URL, SECRET_KEY, Orthanc credentials, mounts, networking and other integrations.

Add/confirm:

```text
RADBRIDGE_ENV=production
SESSION_COOKIE_SECURE=1
SESSION_COOKIE_SAMESITE=Lax
RADBRIDGE_TRUSTED_ORIGINS=https://ris.dynuddns.net
RADBRIDGE_REPORTING_TOKEN=<strong-random-service-token>
```

Keep `RADBRIDGE_BOOTSTRAP_ON_IMPORT` unset/0.

## 4. Reporting Agent

The legacy desktop reporting agent was unauthenticated. v5.44.2 protects the reporting API with a short-lived accession-scoped token embedded in the `risreport://` link.

Update/reinstall `downloads/RIS-Reporting-Agent-Auto-v2.zip` on reporting workstations before production cutover if they use the desktop Word workflow.

## 5. Staging smoke test

Use a restored copy of the production database, not the production database itself.

Required workflow checks:

1. Existing Patient -> branch -> examination -> date/time -> Save Patient & Visit.
2. New Patient -> duplicate check -> examination -> Save.
3. Smart Intake -> approved identity -> patient -> selected examination prefill -> order.
4. Verify Order row commits before MWL call.
5. Verify successful MWL changes order status to SCHEDULED.
6. Simulate MWL failure and confirm the order remains saved with MWL_ERROR and a FAILED outbox event.
7. Communications page/queue as SUPER_ADMIN, CASE_COORDINATOR, RECEPTION and CALL_CENTER.
8. Anonymous request to `/api/reporting/cases/<accession>` must return 401.
9. Authenticated radiologist/report editor access must succeed.
10. Updated Reporting Agent must load, save draft and finalize.
11. PACS worker must continue processing without schema/model errors.

## 6. Production cutover

Use a compose override that changes only the `ris-web` image first. Do not use `--remove-orphans`.

```bash
docker compose \
  -f docker-compose.yml \
  -f docker-compose.v5.44.2-production-stabilization.yml \
  up -d --no-deps --force-recreate ris-web
```

Then:

```bash
EXPECTED_IMAGE=radbridge-ris:v5.44.2-production-stabilization \
./scripts/v5442_health_check.sh ris-web
```

Review the access/error logs after registration attempts:

```bash
docker logs --since 10m ris-web
```

## 7. Rollback

Rollback image:

```text
radbridge-ris:v5.44.1-simple-intake
```

v5.44.2 introduces no database schema migration, so application rollback does not require database downgrade.
