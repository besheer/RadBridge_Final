# ADR 036: Read-only assignment monitoring evidence

Status: implemented locally on the isolated development branch; CI publication is separate.

Assignment monitoring previously obtained all runtime models and query/capacity helpers through legacy_runtime. The canonical legacy owner now belongs to web compatibility. Application projections receive a read repository, doctor reader, policy reader, capacity function, automatic-assignment type set and clock.

The SQL adapter retains existing ordering, status predicates and ORM query scope behavior. The application excludes VERIFIED/FINAL reports, drops offers outside the remaining order set, counts visit-linked examinations, ignores assignment records belonging to a different doctor, and preserves manual/started deadline behavior. Presence remains read-only, UNKNOWN when absent, and online only within the existing five-minute window unless OFFLINE. It creates no presence, profile or policy rows and makes no commit.

Route permissions and coordinator read-only controls remain at the web edge. This extraction preserves the pre-existing query visibility, pending-offer expiry interpretation and window behavior; it does not establish a new branch restriction, fix every aggregate visibility policy or claim scalability over an unlimited case history. These are explicit review/acceptance gates.

Validation: 53 focused tests passed across new independent projections, existing authenticated monitoring routes/distribution behavior, facade identity and multi-instance factory checks. Tests verify report/orphan-offer exclusion, linked reservations, manual/started/stale-owner deadlines, disabled reclaim, presence threshold and empty-order reads. Schema and URL captures remain exactly 160 tables/546 registrations. Complete local suite results are recorded in implementation status; PostgreSQL assignment adds both new projection tests and existing monitor routes.
