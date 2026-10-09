# RadBridge Reporting Agent V2 Contract

The desktop agent is an optional compatibility bridge for doctors who need a
locally installed editor. The primary reporting workflow remains the rebranded
OHIF workspace with ONLYOFFICE and the browser editor.

An Agent V2 release must satisfy all of these conditions before its package is
published:

1. Receive a short-lived `X-RadBridge-Case-Token` scoped to one order and one
   authenticated doctor. A global reporting token is not accepted.
2. Acquire, renew, and release the server-side report lease. A second editor
   must receive `REPORT_EDIT_LOCKED` while a valid foreign lease exists.
3. Use only the authoritative server endpoints for `DRAFT`, `VERIFIED`, and
   `FINAL`. A `FINAL` report is immutable; later work requires the approved
   addendum or reopen workflow.
4. Never overwrite the authoritative clinical report file directly. Uploads
   include the expected report version and checksum and are committed by the
   RIS transaction layer.
5. Preserve patient ID, accession, order ID, Study Instance UID, report version,
   doctor identity, and editor type in the server audit trail.
6. Keep downloaded working files in a restricted temporary directory and remove
   them when the session closes. Do not retain credentials or patient data in
   logs or configuration.
7. Show RadBridge branding and clear status for save, conflict, expired token,
   validation failure, and successful server commit.
8. Pass signed-package, update, rollback, and end-to-end acceptance tests before
   the download route is enabled.

Until an Agent V2 artifact passes this contract, a missing legacy
`RIS-Reporting-Agent-Auto-v2.zip` package is an expected disabled state and must
not block the OHIF/ONLYOFFICE release.
