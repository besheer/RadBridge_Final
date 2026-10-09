# Workflow and role handover

## Core workflow

1. Reception registers patient identity and the order/accession under the correct branch and procedure.
2. Staff prepare and execute the exam according to its configured responsibility policy.
3. PACS reception/matching links incoming images to the true RIS order, with exception review for incomplete or incorrect demographics.
4. Readiness evaluates relevant imaging and clinical/document requirements before assignment.
5. Coordinator assigns or redistributes eligible cases within the permission model and handles exceptions and follow-up.
6. Doctor opens the assigned study, edits a working report, explicitly saves a draft, verifies and finalizes it.
7. Correction/replacement workflows preserve the original FINAL and audit subsequent actions.

These are separate dimensions: imaging reception, exam execution, assignment readiness and report state. `FINAL` alone is not a reason to rewrite PACS status as complete. Conversely, `RECEIVING` should not silently be assumed ready. Review the shared readiness/assignment services and tests when changing these gates; do not repair one screen label while leaving other assignment entry points permissive.

## Responsibilities

| Role | Intended operational work | Boundaries |
|---|---|---|
| Reception | Registration, order/booking and permitted preparation | Patient/order identity and branch access must remain auditable |
| Technician | Imaging-device execution, technical notes, permitted images/attachments/consumables | No report editing; readiness is not inferred from image count alone |
| Nursing | Preparation, notes and consumables; start/end where procedure policy permits | No report editing or manual RT dose/plan entry |
| Coordinator | Readiness, documents, delay, assignments, exceptions and follow-up | Cannot bypass clinical readiness or silently repair identity |
| Radiologist | Permitted case/image review and report workflow | Assignment, branch and clinical scope; immutable final version |
| RT physician | Record externally approved RT plan and revisions, link PET and schedule | Separate role, no automatic promotion of all radiologists |
| Branch manager | Permitted oversight within branch | Actual stored role permissions apply |
| Administrator | User, permission, rule and operating configuration | Privileged changes require authorization and audit |

The table describes intended responsibilities, not an exhaustive permission grant. Stored `Role.permissions_json` and user profile scope are authoritative. Do not grant `*` as a workaround. Finance, helpdesk and other roles require review of their actual permission sets before assigning access.

## Staff procedure policies

`procedure_staff_workflow.py` supports per-procedure owner/mode and requirement flags with auditing and frozen execution policy for started exams. The prior staff release configured imaging procedures for TECHNICIAN and ultrasound for NURSING while retaining existing image requirements. Six interventional codes were explicitly configured for both staff roles: `IR-US-BIOPSY`, `IR-CT-BIOPSY`, `IR-US-DRAIN`, `IR-CT-DRAIN`, `IR-PICC`, `IR-CVC`.

The owner's decision that nurses may start/end depends on the **exam code**; a modality name alone cannot decide all responsibilities. ECG catalog/workflow work was deferred. Do not create procedure prices or clinical requirements as placeholders without a new approved policy.

## Access, filters and transfers

`clinical_scope.py` handles modality/device/room scope for relevant clinical roles in addition to branch and route permissions. A corrupt configured scope fails closed. No configured scope has different semantics from an explicit restrictive scope: inspect the policy before changing default access. `staff_worklist_filters.py` stores user-specific worklist preferences; a saved filter must never expand authorization.

`user_csv_transfer.py` handles user CSV import/export. Review role, branch and scope validation, duplicate handling and password/account setup; do not import a CSV as an authorization bypass. Real user exports are not part of this repository backup.

## Patient matching and manual correction

Use the incoming PACS study as the source row and the confirmed true RIS case as the target row. A similarly named patient is insufficient evidence. Verify patient ID/issuer, accession, exam/branch and supporting records using the current reconciliation workflow. Record the reason and permitted approval path. Cases belonging to another patient need documented identity correction rather than indiscriminate linking or shared images.

## Reports and viewers

ONLYOFFICE autosave updates a working copy; explicit Save Draft commits a RadBridge report version. Verify must operate on the saved version, and Finalize locks that version. Callback failures require reviewing document service reachability, callback authentication and the commit ledger; extending a timeout alone is not proof of a fix.

`viewer_choice.py` declares OHIF, Weasis and RadiAnt. Current operational preference is OHIF/Weasis; RadiAnt client installation/licensing was deferred. A declared launch route does not prove client installation. Check WebGL/rendering capabilities, DICOM access and study-specific authorization for OHIF. Image/measurement transfer into the report needs separate end-to-end acceptance; do not infer delivery from a button or request history.

For replacement settlements, the owner's accepted rule is transfer only for a FINAL REPLACEMENT, calculated by the replacement consultant's entitlement rules; if payment was posted, keep it and record an explicit reversal/adjustment. Review `replacement_settlements.py` and relevant ledger tests before financial changes. This documentation task does not certify every production settlement.
