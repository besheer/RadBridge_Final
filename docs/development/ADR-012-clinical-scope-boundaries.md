# ADR 012: Clinical scope policy, access and persistence boundaries

Date: 2026-10-11. Status: implemented on the development branch.

Domain clinical.scope validates stored scope values and operator configuration against a supplied modality/device/room catalog. Invalid configured scopes remain invalid and deny access; absence retains the original unrestricted-scope semantics independently of role permissions. Disabled scope still returns before any catalog query.

ClinicalScopeAccess receives an explicit repository and validated scope. Inactive actors or invalid scopes do not query order evidence. SqlAlchemyClinicalScopeRepository receives session/models, a profile-settings reader and optional predicate callback. It owns catalog/profile/order-match queries; infrastructure builds the original modality/device/room intersection predicate and retains branch/AE identity and configured device IDs.

web.extensions.clinical_scope owns CSRF, permission/audit behavior, routes, request guards, ORM loader criteria and per-app listener lifecycle. Both old imports alias this extension, preserving predicate overrides and existing callers. This change grants no new permission and introduces no schema migration or endpoint.

Validation: 107 local scope/factory/CSV/technician/ownership/distribution tests passed, followed by 67 scope/dependency/factory/CSV/ownership tests after the explicit disabled-scope early-return correction. Subprocess tests import the domain/service without Flask, SQLAlchemy or runtime; tests reject corrupt scopes and ambiguous devices and use supplied evidence. CI adds an independent PostgreSQL scope matrix suite. Complete CI on this commit remains required. External integration, browser UAT and release acceptance remain unfinished.

No production change was performed.
