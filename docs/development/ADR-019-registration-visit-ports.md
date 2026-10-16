# ADR 019: Registration validation and visit reservation ports

Date: 2026-10-11. Status: implemented on the development branch; full CI required.

`domain.registration.patient_validation` owns patient field/date/sex validation with supplied rules, field validator and current date, plus role-based registration branch selection. `application.services.registration.visit_registration` owns visit selection and reserved-visit assignment with explicit repository and creation, authorization, capacity, qualification, assignment, audit and clock callbacks. The SQL adapter owns visit/member/profile/appointment/offer queries, PostgreSQL advisory locking, refresh, row locks, cancellation and flush.

The old module aliases `web.compatibility.registration_policy`, which retains UI rule construction, persisted patient extra-field lookup, current-user access and legacy assignment wiring. Legacy model keyword payloads stay at composition; the service receives an assignment callback. Broader patient creation, scheduling/booking and external Worklist/insurance use cases remain unfinished boundaries.

Visit identity remains patient, branch and date. Existing manual reservations persist across device registrations. Visits with FINAL/cancelled/saved reporting work or active automatic/started assignments reject membership changes. Manual choice requires permission, an active clinical doctor, whole-visit modality/branch qualification and capacity. Membership updates cancel old pending offers before audit/flush. Reserved assignment rechecks doctor qualification including booked special examinations. No automatic assignment or withdrawal is introduced for manual reservations.

Validation: 74 focused local tests passed, including existing registration/check-in, age/calendar, grouped assignment and ownership suites. New direct tests cover supplied rule/date validation, branch scope, mismatch rejection before locks, capacity rejection before mutation, preserved reservations and FINAL membership barriers. Imports require no database/web/runtime. Schema/routes remain identical for 160 tables and 546 registrations.

CI adds PostgreSQL registration contracts. The mismatch fixture now supplies mismatched patient/branch/date inputs rather than corrupting saved foreign keys; it retains the original fail-closed assertion. The preceding inventory commit 7d0a22a6c57bd3f19266e13f5a2ee3fdddbe9ddb passed all eight CI jobs, including reporting, finance and inventory PostgreSQL suites plus full SQLite and Docker smoke. New checks remain required on this commit.

No production, patient data, schema migration or deployment change is included.
