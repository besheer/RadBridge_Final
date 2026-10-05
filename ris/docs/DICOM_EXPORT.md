# Original DICOM export

The signed doctor reporting API provides GET `/api/ohif/report/<order_id>/dicom-download?StudyInstanceUIDs=...&format=archive|media` behind the existing OHIF gateway token. `archive` exports original DICOM ZIP; `media` exports the Orthanc DICOMDIR ZIP for CD/USB preparation. This creates a ZIP, not a burned disc or ISO.

The assigned doctor's identity, reporting permission, branch scope, exact study UID and PACS demographic gate are checked before preparing the export and again after preparation. Every original object header must match the RIS patient ID, birth date and study UID. Parsing stops before pixel data; no image rewriting or pixel/anatomy recognition is performed. The legacy readiness gate remains authoritative.

Only server-held PACS credentials are used; redirects are disabled. The temporary file is unlinked, output is not publicly cached, and the success audit is DICOM_EXPORT_PREPARED with format, object count and size. This event records preparation, not proof of local delivery. There is no public Orthanc URL, persistent local cache, automatic local app launch or C-MOVE.

Limits: 1 GiB compressed ZIP, 4 GiB uncompressed objects, 20,000 files and 8 MiB per parsed header. Unsafe archive paths, malformed DICOM, mismatched identity, revoked access and changed case binding block delivery. Browser download is explicit; RadiAnt can open the downloaded ZIP locally.

Validation: isolated route/header tests plus the existing RIS suite; deployed UAT uses synthetic CODEX case 9 only and preserves FINAL report files and version history.
