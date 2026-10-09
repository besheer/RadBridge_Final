RIS Web v5.15 — QA + Architecture Stabilization

ADDED
1. Central workflow_engine.py
   - One-step forward transitions.
   - Role-aware transition decisions.
   - Supervisor/Super Admin override path.

2. EventOutbox
   - EXAM_STATUS_CHANGED
   - EXAM_STATUS_OVERRIDE
   - REPORT_FINALIZED hooks where the existing finalization path supports it.
   - Foundation for Notifications / HL7 / FHIR / SAP consumers.

3. Alembic scaffold
   - alembic.ini
   - migrations/env.py
   - migration for event_outbox
   IMPORTANT: existing production DB should be stamped/baselined deliberately.
   Do not blindly run downgrade/upgrade on production before backup.

4. Automated tests
   - tests/test_workflow_engine.py
   - tests/test_source_integrity.py
   - tests/test_permissions_matrix.py
   - UI smoke placeholder
   - scripts/run-playwright-smoke.py
   - scripts/dicom-smoke.py

5. One-command runner
   ./ris-test-all.sh

6. Staging
   docker-compose.staging.yml
   Port 18090, separate PostgreSQL and separate volumes.
   It can point to a TEST Orthanc via TEST_ORTHANC_URL.

7. Admin QA page
   /admin/qa
   Event outbox status and quick diagnostics.

NOTES
- This release preserves the current RIS/PACS features.
- It does not replace all legacy status-setting code yet; it centralizes the exam-status transition gate first.
- Full HL7/FHIR consumers are intentionally left for the next integration phase.
