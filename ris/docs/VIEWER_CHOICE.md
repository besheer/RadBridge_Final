# Doctor image viewer selection

The doctor worklist and report editor offer OHIF / Weasis. Existing Open Study
uses the doctor's saved default (OHIF initially). My Profile or the case viewer
chooser saves a per-user preference without changing reporting/editor settings.

Weasis is a locally installed desktop application; the RIS launch page uses its
documented custom protocol and XML manifest. Reports remain in RadBridge.

No additional persistent service or database migration. Authorized current Canary
is radbridge-ris-95fee0e-canary on 127.0.0.1:18092; previous R8 names in AGENTS
are historical and the existing authorized release workflow uses this Canary.

Weasis delivery uses a dedicated read-only capability expiring after 20 minutes.
Every manifest/instance fetch checks active doctor, reports.view, branch,
current ownership, verified demographic/exam matching and exact linked study.
The capability cannot call reporting writes or arbitrary PACS paths. Original
DICOM headers are verified against study, patient and SOP before original bytes
are returned; reassignment and reconciliation are rechecked before delivery.
Upstream credentials stay on the server and redirects are disabled. No-store,
no-referrer and nosniff response policies apply. Preference writes are audited
and chooser writes require a session CSRF token. Existing clinical image-only
and patient portal OHIF routes retain their contracts.

Native acceptance requires Weasis installed on the doctor's workstation; a
browser button alone does not prove the operating-system handler or desktop
viewer opened. Core server/permissions and synthetic UI tests are independent
of this workstation prerequisite. No Weasis installation is silently assumed.

Sources:
- https://weasis.org/en/basics/customize/integration/
- https://weasis.org/en/getting-started/weasis-protocol/
