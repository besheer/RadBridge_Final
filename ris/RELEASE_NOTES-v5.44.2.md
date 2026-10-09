# RadBridge v5.44.2 Production Stabilization

This release is a stabilization release derived from the live v5.44.1 production application snapshot. It intentionally avoids schema changes and large architectural rewrites.

## Critical fixes

- Registration form now disables inactive patient-mode controls. Hidden New Patient fields can no longer block Existing Patient submission through browser HTML validation.
- Save Patient & Visit is now an explicit submit button with a stable diagnostic id.
- The registration page no longer emits the attachment JavaScript inside the page-title breadcrumb block.
- Registration commits the RIS database transaction before sending MWL or starting smart assignment.
- Registration writes MWL and assignment outbox records before commit and records post-commit delivery success/failure.
- Attachment files created during a registration that fails its database commit are cleaned up.
- Communications staff role checks now recognize the production role names SUPER_ADMIN and CASE_COORDINATOR while retaining legacy aliases.
- Reporting case/draft/finalize APIs now require an authenticated RIS session, a short-lived accession-scoped reporting-agent token, or an explicit service token.
- Desktop Reporting Agent package updated to forward the accession-scoped case token.

## Security hardening

- SESSION_COOKIE_HTTPONLY enabled.
- SESSION_COOKIE_SAMESITE defaults to Lax.
- SESSION_COOKIE_SECURE defaults on for HTTPS public URLs.
- Explicit cross-origin unsafe browser requests for authenticated sessions are rejected when an Origin header is present.
- Production mode refuses weak/missing SECRET_KEY and the known Orthanc development password.
- Initial admin bootstrap now requires RIS_ADMIN_PASSWORD instead of silently using a known default.
- docker-compose.ris.yml no longer embeds example database/application/PACS passwords.
- Runtime patient data and the embedded OHIF runtime secret file are excluded from this source release.

## Code/release correctness

- APP_VERSION = 5.44.2
- BUILD_NAME = production-stabilization
- Fixed missing comma between inventory.reports and backup.view.
- Removed duplicate CALL_CENTER role declaration.
- Removed shadowed duplicate ai_case_context; retained the richer verified-image-AI implementation.
- Gunicorn access/error logging enabled to stdout/stderr.
- Docker image gets OCI version metadata.
- Source is packaged from the live production application tree rather than the partial v5.44 overlay.

## Database

No schema migration is required for v5.44.2. Do not run Alembic stamp/upgrade against the current production database as part of this release.

## Deployment prerequisites

1. Take and verify the automated database backup.
2. Keep `RADBRIDGE_BOOTSTRAP_ON_IMPORT` unset/0.
3. Set `RADBRIDGE_ENV=production`.
4. Keep the existing strong `SECRET_KEY` and `ORTHANC_PASSWORD`.
5. Configure a strong `RADBRIDGE_REPORTING_TOKEN` if a service integration needs non-session access.
6. Reinstall/update RIS Reporting Agent for users of the desktop Word workflow before enforcing the protected reporting API.
7. Build and test this image against a restored staging copy of production before cutover.

## Rollback

The production rollback target remains `radbridge-ris:v5.44.1-simple-intake`. No database schema change is introduced, so application rollback does not require a database downgrade.
