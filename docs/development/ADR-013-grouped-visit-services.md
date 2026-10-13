# ADR 013: Grouped visit services with explicit evidence

Date: 2026-10-11. Status: implemented on the development branch.

`VisitAssignmentService` owns visit creation, member resolution, offer-readiness checks, doctor preference and grouped assignment. It receives a repository and explicit callbacks for returned-case/readiness evidence, active load, capacity, special qualification and case mutation. It imports no web framework, SQLAlchemy, legacy runtime or infrastructure implementation.

`SqlAlchemyVisitRepository` owns visit/order/profile/booking/offer/source queries and the existing PostgreSQL transaction advisory lock. It extends the assignment row repository, with all sessions/models supplied by composition. Query ordering, order-row locks and source-center checks are preserved. Visit identity stays explicit; a patient ID alone never creates a group. Conflicting patient, branch or source evidence rejects the group.

The legacy paths alias `web.compatibility.assignment_visit_grouping`, which supplies the existing live qualification and mutation callbacks. Legacy keyword payloads remain accepted at that edge; the injected case-mutation callback receives the caller's payload unchanged. Assignment commits, rollbacks and auditing remain caller-owned.

Grouped assignment preserves full-group modality/branch qualification and capacity, returned/readiness barriers, single-case delegation and the longest member deadline. The service only flushes, so callers can roll back the complete group after a later member failure. Existing permission and clinical-scope checks remain authoritative.

Validation: 98 existing assignment/distribution/visit/coordinator/receiving/ownership tests passed locally; 52 focused direct-port/visit/coordinator/transaction tests also passed. Direct-port tests reject mismatched patient/branch/source and verify a shared longest deadline. A subprocess imports the service without runtime/database/web dependencies. The new tests are included in the isolated PostgreSQL assignment suite; full CI remains required on the commit.

This completes explicit dependency composition for these five visit workflows. Broader coordinator preview, auto-distribution evidence, deadline workers, reporting, finance and other use cases still require their own boundaries and integration acceptance. No production migration or deployment is included.
