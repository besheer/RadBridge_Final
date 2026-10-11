# Architecture implementation and remaining gates

Date: 2026-10-11. Scope: development source only; no production writes or deployment.

Clinical release metadata remains 5.46.9. Architecture work is a development refactor, not a released clinical version. Canonical ownership is implemented throughout the reviewed RIS source, but clean dependency inversion and external-service acceptance are not complete.

## Owned areas

| Area | Executable ownership | Remaining dependency work |
|---|---|---|
| Patient registration, scheduling, insurance | Patient validation and explicit visit registration/reservation ports; registration components/routes | Broader patient creation, booking/scheduling and insurance still need narrow interfaces; external RIS connectors are separate integrations |
| Technician, nursing, procedures, radiotherapy | `domain.clinical`, `application.services.clinical`, clinical components/routes | Explicit use cases and transaction ownership; treatment-device integration not supplied |
| Readiness and exceptions | `domain.readiness`, `domain.readiness_checks`, `application.services.readiness` | Separate evidence acquisition from DB-backed orchestration |
| Assignment and coordinator work | `domain.assignment`, explicit query/transaction/visit services and repositories | Policy/count/capacity, ranking/deadlines, single-case and grouped-visit mutations and offer acceptance are separated; coordinator preview, distribution evidence and workers still need narrow dependencies |
| PACS matching, identity, viewers | `domain.imaging`, `application.services.imaging`, `infrastructure.adapters.imaging`, imaging routes and viewer extension | Provisioned synthetic PACS transport/failure acceptance |
| Reporting, revisions, editor, exports | `domain.reporting`, explicit report commit service/repository/artifact store, reporting routes/extensions | Commit ports are separated; revisions, finalization, callbacks and exports still need use-case dependencies and external fault acceptance |
| Payments, collection, settlements | Explicit replacement settlement policy/workflow/repository; finance components/routes | Replacement transfer ports are separated; collection, closing, broader unit-of-work and cash-entry dependencies remain unfinished |
| Inventory and consumables | Explicit original-lot return domain/service/repository; inventory components/routes | Consumption and general stock movement still need narrow transaction/repository interfaces; no stock data migration |
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

Candidate ordering and start-timeout selection now execute in the pure domain layer over explicit facts (ADR 010). The compatibility layer still gathers scoped visit and availability evidence and handles mutations; those remain unfinished interfaces.

Assignment mutations and offer acceptance now execute through explicit repository/policy ports (ADR 011). Legacy signatures are compatibility wrappers. Clinical qualification and grouped-visit callbacks still originate at the compatibility edge; this is not complete inversion of the whole assignment workflow. PostgreSQL CI adds an independent assignment suite.

See ADRs 001–019 and the existing blueprint validation plan. Do not interpret a screen, a passing source assertion, or a module name as evidence of a complete external integration.

Patient field/date/sex validation and visit selection/reserved assignment receive explicit rules/evidence/repository dependencies (ADR 019). CI adds PostgreSQL registration coverage. The preceding inventory commit 7d0a22a6c57bd3f19266e13f5a2ee3fdddbe9ddb passed all eight CI jobs; new registration checks require their own success before review.

Original-lot returns use explicit quantity/credit policy, repository and movement dependencies (ADR 018). CI adds PostgreSQL inventory coverage and corrects the finance missing-CSRF fixture's rollback boundary; finance and inventory require green results on the new commit. The earlier corrected lease adapter commit passed all six CI jobs.

Replacement entitlement planning/confirmation executes through explicit policy/evidence/persistence/audit ports (ADR 017), retaining original cash disbursements and FINAL-only/idempotency barriers. PostgreSQL reporting passed on the corrected lease adapter commit f57be1b513953900230c49ae38ef8b1cd4ce6e05; the finance suite is newly added and requires its own green CI result.

Correction request/review transitions execute through explicit repository/evidence/audit/notification/clock policies (ADR 016). Document/reference resolution and editor/finalization still compose at the web extension edge. The PostgreSQL reporting suite also exposed synthetic full-name/foreign-key fixture defects, repaired without schema changes or weaker permission checks; a successful reporting CI run is still required.

Report edit leases now use explicit persistence/clock/assignment dependencies (ADR 015). The prior report commit passed five of six CI jobs; the new PostgreSQL reporting job exposed an oversized synthetic branch code, corrected in its fixture. Full checks must pass on this commit before review. Role, FINAL, ownership and token-scoped release contracts remain authoritative.

Report saving now executes through explicit persistence and immutable artifact ports (ADR 014), with independent dependency, retry, FINAL, stale-base and failed-flush tests. The grouped-visit commit 688bcd4f36476d79f9da01745bf56e20c7bf1404 passed all five CI jobs. The new reporting commit requires its own full checks; broader editor/revision and post-return transaction/crash acceptance remain unfinished.

Clinical scope validation/access/persistence is separated in ADR 012. Request and ORM guards remain web responsibilities, with compatibility aliases preserving registration and patch state. The qualification evidence service uses an explicit repository; broader user lifecycle and other use-case dependencies remain unfinished. CI adds a separate PostgreSQL scope suite. The assignment transaction commit 1ec0d5cc6054af50a8e82e6acb7cd6a6281454a3 passed all four CI jobs, including both PostgreSQL suites and 1,836 SQLite tests (three skipped).

Grouped visit creation/member checks/readiness/preference/assignment receive explicit repository and policy dependencies (ADR 013). Qualification callbacks still compose at the web compatibility edge; coordinator preview, distribution evidence and worker lifecycle remain unfinished. Scope commit 6c011ba64fe7ce9410768dee181317396c6b02e4 passed all five CI jobs, including clinical/assignment/scope PostgreSQL suites and the full SQLite suite.
