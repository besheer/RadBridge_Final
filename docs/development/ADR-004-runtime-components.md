# ADR 004: Extract executable handlers with explicit compatibility bindings

Status: implemented on the development branch; not approved for production.

## Decision

The remaining 949 top-level functions in `ris/app.py` are owned by 24 executable modules: application components and web routes for assignment, clinical execution, communications, finance, identity, imaging, inventory, operations, readiness, registration, reporting and shared behavior. `app.py` installs them in their original order, preserving decorator evaluation, endpoint names and initialization timing. ORM classes already belong to infrastructure models and independent policies to domain packages.

Each installer receives an explicit list of its existing dependencies through `application.dependencies.Bindings`. Lookup remains live so existing monkeypatches and late initialization retain their behavior. An undeclared dependency raises an error. These bindings are a compatibility mechanism, **not authorization, dependency inversion completion, or a multi-application factory**. The legacy `globals()` lookup remains available for existing dynamic checks. Some components still depend on each other through the composition module.

## Contracts

- Existing 160-table schema and 546 route registrations compare identically before and after extraction.
- `application/component_manifest.json` records owner, installer, dependency names and original source hash for every extracted function.
- `web/source_contract.py` inspects the actual executable handlers for existing static contracts and permission catalogues. It stores no duplicate clinical implementation. The source hash test checks all 949 bodies, including decorators and literal content.
- Existing runtime authorization, branch, clinical workflow and transactional tests remain mandatory. Matching source/schema alone does not establish clinical acceptance.
- Function implementation modules and qualified names change. Old serialized Python functions are not a supported migration contract; inventory custom integrations before release.
- Implicit module globals such as `__name__` must also be bound to the composition root. They cannot fall back to the component module's identity; existing clinical/viewer services use that identity to resolve models and access checks. The full runtime suite verifies those paths.

## Remaining work

Replace compatibility projections progressively with narrow use-case ports and explicit transactions. Separate settings and application assembly; inventory and extract existing external-service adapters and worker entry points. A genuinely isolated `create_app()` must not retain shared mutable legacy runtime state. Run the complete synthetic suite, PostgreSQL contracts and Compose checks, then external editor/PACS fault tests and role-based UAT before merge/deployment. This change does not provision external services, certify clinical completeness, or change production data.

## Rollback

Revert the extraction commit as a code-only change before release. It adds no database migrations or data transformation. Deployment rollback, once separately authorized, must use the normal immutable-release procedure and its matching dependencies; do not edit running containers.
