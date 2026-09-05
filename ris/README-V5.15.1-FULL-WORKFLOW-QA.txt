RIS Web v5.15.1 — Full Workflow QA

Adds:
- Full pytest scenario suite covering reception, workflow rules, nursing models, PACS routes,
  reporting routes, patient portal, finance, permissions, duplicate patient safety,
  sticker routes and EventOutbox.
- Full live HTTP workflow smoke runner.
- Extended role matrix regression tests.
- One-command QA runner:
  TEST_BASE_URL=http://127.0.0.1:18090 DICOM_HOST=127.0.0.1 DICOM_PORT=4242 ./ris-test-full-workflow.sh
- Staging log scan for critical Traceback/UndefinedColumn/TemplateSyntaxError/InternalError.

This release is QA-focused. It does not add production workflow features.
