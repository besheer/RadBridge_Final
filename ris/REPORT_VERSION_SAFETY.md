# RadBridge Unified Clinical Report Safety

One logical Report exists per RIS Order.

Editors are transports only:
- Browser
- Microsoft Word
- ONLYOFFICE
- Manual DOCX Upload

They MUST NOT create independent report identities.

Every accepted change creates an immutable ReportVersion.

Clinical authority:
- DRAFT is never authoritative.
- Only the newest VERIFIED version is authoritative.
- A newer DRAFT does not invalidate the prior VERIFIED version.
- When the newer version is VERIFIED, it becomes authoritative.
- FINAL/FINALIZED versions cannot be overwritten.
- Post-final correction requires ADDENDUM/AMENDMENT.

Concurrency:
Every editor saves against base_version.
If base_version != current_version, save is rejected.

Document safety:
DOCX must be structurally valid before commit.
Patient ID and Accession validation remains mandatory.

Audit per version:
- editor/user
- username/display name
- editor type
- created timestamp
- base version
- SHA-256
- verification actor/time
- finalization actor/time

Duplicate protection:
Identical SHA-256 must not create a second version.
