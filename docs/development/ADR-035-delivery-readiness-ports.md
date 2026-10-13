# ADR 035: Manual delivery evidence ports

Status: implemented locally on the isolated development branch; CI publication remains a separate gate.

The legacy delivery policy combined runtime lookup, SQL matching evidence, filesystem inspection, HTTP requests and identity decisions. The canonical compatibility owner now belongs to web composition. Original legacy module identity, callable signatures, METHODS, messages and manual delivery route permissions are retained.

DeliveryReadiness receives a current-match repository, report-file evidence adapter, PACS evidence adapter and demographic gate. It imports domain policy only. The repository has a read-only current-match query. Report files resolve inside REPORT_DIR, require nonempty PDF/DOCX candidates and invoke the existing patient-file validator; invalid candidates fall through to the next candidate. Orthanc evidence receives URL, HTTP getter and auth callback explicitly, retaining identifier escaping, status checks and eight-second request timeouts.

The service requires FINAL before inspecting a report file. Images require a current match and the existing demographic gate. Preview uses cached evidence without network requests; actual live image delivery checks the linked study identity before requesting statistics. Exact links compare RIS identity; manually confirmed/approved overrides compare the captured PACS identity. Unavailable or malformed live evidence and nonpositive instance counts block delivery.

This is read-only readiness for recording physical/manual delivery. It does not send mail/WhatsApp, ship DICOM, guarantee complete image acquisition, establish Storage Commitment, or implement a transfer retry queue. Existing delivery writes, audit, authorization and commits remain at the route. Existing cached-status and match-method behavior is preserved; broader policy decisions require separate review.

Focused validation: 43 tests passed, including existing authenticated delivery routes and factory/module identity checks. New tests verify stop-before-transport barriers, stop-before-statistics identity mismatch, manual-link captured identity, malformed/offline evidence, report root containment/empty/suffix rules, later-candidate fallback and escaped Orthanc transport contracts. Before/after captures remain exactly 160 tables and 546 registered web routes. The complete local suite result is recorded in IMPLEMENTATION_STATUS.
