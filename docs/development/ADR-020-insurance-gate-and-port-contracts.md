# ADR 020: Insurance readiness and enforced workflow port ownership

Date: 2026-10-11. Status: implemented on the development branch; full CI required.

`domain.registration.insurance` evaluates the latest insurance decision and contract requirement. `InsuranceReadiness` receives an explicit latest-decision repository; the SQL adapter owns descending decision-ID lookup. The legacy module aliases web compatibility composition, retaining actor/branch/role permission guards and the shared outbound gate. Paid amount or a legacy approval reference never substitutes for an authoritative approved decision with its reference. Optional insurance only bypasses absent decisions or explicit NOT_REQUIRED; an unresolved existing decision remains blocking.

`application/port_contracts.json` now maps eleven actually separated application services to persistence adapters and composition edges. The architecture checker verifies these files exist and rejects direct infrastructure, web, Flask, SQLAlchemy, requests or legacy-runtime imports in these services. Broader compatibility modules are explicitly excluded from this claim and still require migration. The generated code map includes all 76 legacy owners and the eleven port boundaries with source links.

Validation: 75 focused insurance/registration/ownership tests passed locally. Explicit evidence tests cover missing/blank/pending/approved/NOT_REQUIRED decisions and independent repositories; existing runtime tests verify authorization, audit and actual outbound-network blocking. Schema/routes remain identical for 160 tables and 546 registrations. Insurance tests join the isolated PostgreSQL registration suite. Their fixture now uses a valid branch length and a persisted synthetic actor ID for event foreign keys; role/branch denial assertions remain intact.

Registration commit ba44e3feeb0e4be288a28b97abb5049b97d03eac passed all nine CI jobs, including seven PostgreSQL suites, full SQLite and Docker smoke. The new insurance/port-contract commit needs its own green checks. No production, schema/data migration or deployment change is included.
