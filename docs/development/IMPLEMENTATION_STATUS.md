# Architecture implementation and remaining gates

Date: 2026-10-11. Scope: development source only; no production writes or deployment.

Clinical release metadata remains 5.46.9. Architecture work is a development refactor, not a released clinical version. Canonical ownership is implemented throughout the reviewed RIS source, but clean dependency inversion and external-service acceptance are not complete.

## Owned areas

| Area | Executable ownership | Remaining dependency work |
|---|---|---|
| Patient registration, scheduling, insurance | `domain.registration`, `application.services.registration`, registration components/routes | Narrow database/configuration interfaces; external RIS connectors are separate integrations |
| Technician, nursing, procedures, radiotherapy | `domain.clinical`, `application.services.clinical`, clinical components/routes | Explicit use cases and transaction ownership; treatment-device integration not supplied |
| Readiness and exceptions | `domain.readiness`, `domain.readiness_checks`, `application.services.readiness` | Separate evidence acquisition from DB-backed orchestration |
| Assignment and coordinator work | `domain.assignment`, `application.services.assignment`, injected assignment query repository | Policy/count/capacity queries are separated; remaining ranking, qualification and mutation orchestration needs narrow dependencies |
| PACS matching, identity, viewers | `domain.imaging`, `application.services.imaging`, `infrastructure.adapters.imaging`, imaging routes and viewer extension | Provisioned synthetic PACS transport/failure acceptance |
| Reporting, revisions, editor, exports | `domain.reporting`, `application.services.reporting`, `infrastructure.adapters.reporting`, reporting routes/extensions | Editor callback fault acceptance and explicit storage/transaction interfaces |
| Payments, collection, settlements | `application.services.finance`, finance components/routes | Narrow unit-of-work and settlement dependencies; retain existing exact-once contracts |
| Inventory and consumables | `application.services.inventory`, inventory components/routes | Narrow stock repository interfaces; no stock data migration |
| Users, clinical scope, security | `application.services.identity`, identity components/routes, security extension | Keep role/branch checks authoritative; host collection/VPN services remain external |
| Communications, AI and telephony | communication components/routes, communication adapter and extensions | External-provider configuration and reviewed integration testing |
| Operations, storage, administration | operations components/routes and extensions | Operational adapter separation and provisioned recovery tests |
| Data, migrations, workers, resources | `infrastructure.models`, `infrastructure.schema`, `workers`, `infrastructure.resources` | Explicit worker lifecycle and production upgrade acceptance |

`application/component_manifest.json` maps all 949 extracted functions and declared dependencies. `application/module_manifest.json` maps all 76 migrated modules. Compatibility files at the RIS root point to the real modules, not separate implementations.

## Proven invariants

Before/after captures compare the same 160 database tables and 546 route registrations, including column types/defaults, constraints, indexes, URL methods and endpoints. No migration or data transformation is added. Tests cover all original handler source hashes and facade object identity. Runtime suites retain authorization, branch scope, receiving assignment barriers, immutable reports, reconciliation, inventory and settlement assertions. Matching structure alone is insufficient to approve deployment.

## Explicit unfinished gates

1. Replace `Bindings` and `legacy_runtime` with narrow use-case dependencies. Existing m-based extension interfaces remain compatibility APIs, not a completed dependency inversion.
2. Run provisioned synthetic ONLYOFFICE/PACS/viewer failure scenarios: callback delay/loss, reassignment, partial transfer, queue restart and destination storage confirmation. The local Compose stack contains RIS/PostgreSQL only.
3. Run role-based browser UAT and review the architecture PR. Production upgrade, rollback rehearsal, merge and deployment require a separate release decision.

Clinical factory isolation is implemented for supported database, secret, storage, cookie and runtime URL settings, with authenticated two-instance and scope-listener tests. Host/provider feature settings remain process-level; extending per-instance configuration requires explicit contracts and tests. All 160 models are registered in infrastructure before composition. See ADR 007.

The 949 component installers now belong to 32 modules: 12 application component modules, 12 route modules and eight web helper modules. Eighty installers were reassigned to web ownership without changing their original handler bodies. HTTP dependencies are checked at the component boundary; mixed extension registration/service modules still need narrower interfaces. See ADR 008.

The clinical factory commit `1bc4840a1ae5fa02c9fe5b9b7a2a225724ba9573` passed the complete SQLite suite (1,814 passed, three skipped), PostgreSQL contracts and the independent Docker Compose smoke test in GitHub Actions run 38118087675. Later commits require their own green checks before review.

Distribution query separation is implemented in ADR 009. The legacy module manifest now explicitly points the still-coupled distribution entry points to `web.compatibility`; old import paths remain aliases to that single implementation. The new application query service has no runtime resolver or framework imports and is tested with independent repositories/sessions.

See ADRs 001–009 and the existing blueprint validation plan. Do not interpret a screen, a passing source assertion, or a module name as evidence of a complete external integration.
