# Testing Checklist

Before releasing:

```bash
python -m py_compile app.py workflow_engine.py pacs_worker.py backup_worker.py
python tools/generate_code_map.py
python preflight.py
python schema_check.py
```

Also run project-specific smoke/self-tests where the required services are available:

```bash
python smoke_test.py
python stabilization_self_test.py
python live_self_test.py
```

## Minimum clinical regression checks

- Login/role permissions.
- Patient search and new registration.
- Order/accession creation.
- Scheduling/worklist.
- Technician exam status.
- PACS intake and RIS/PACS match.
- Technician PACS Send and deliberate Resend.
- C-ECHO/destination test.
- Failed transfer → Retry.
- Pending transfer → Cancel.
- Radiologist reporting and finalization.
- Coordinator flow.
- Report/attachment access.
- Audit trail.
- Backup configuration and latest run state.

Never certify production readiness from unit/syntax tests alone; PACS/DICOM behavior requires an integration test against a non-production Orthanc and test destination.
