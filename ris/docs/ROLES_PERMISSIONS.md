# Roles & Permissions

Authorization is permission-based. Role defaults are defined in `ROLE_PERMS` and permissions are checked using helpers such as `has_perm()` and `require_perm()`.

Important operational roles include Reception, Call Center, Nursing, Technician, Radiologist, Case Coordinator, Cashier, Contracts, Inventory, Management, IT and Super Admin.

## PACS permissions

- `pacs.view` — PACS visibility/administrative views where applied.
- `pacs.transfer` — technician/manual DICOM send/resend operations.

## Rules for developers

- Every new state-changing route must have an explicit permission decision.
- Never rely on hiding a UI button as authorization; enforce on the server route.
- Branch scope must be enforced server-side.
- Super Admin wildcard permission should not be copied to ordinary roles.
- New permissions should be added to `ALL_PERMISSIONS` and assigned intentionally.
- Privileged changes should call `audit(...)`.

## Clinical workflow transitions

`workflow_engine.py` defines the allowed one-step workflow transitions by role. Supervisor/Super Admin override is explicit. Avoid bypassing it with direct status assignment in new code unless the action is an audited, intentional override.
