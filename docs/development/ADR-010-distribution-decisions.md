# ADR 010: Distribution decisions over explicit facts

Date: 2026-10-11. Status: implemented on the development branch.

## Decision

`domain.assignment.distribution` owns start-timeout selection and candidate ordering. Deadline selection retains the original rule matching, specificity, minimum-image threshold, urgency percentage and 60-second floor. An explicitly priority-specific rule is not scaled again.

Candidate ordering receives immutable facts: a caller index, doctor ID, online state, active and pending counts, capacity, last turn and weight. It returns caller indices, preserving repeated candidates and original object identity at the compatibility edge. It excludes doctors whose active work plus pending reservations fills their capacity, then applies the existing LEAST_ACTIVE, ROUND_ROBIN or LONGEST_WAITING key. Unknown modes retain the historical LEAST_ACTIVE fallback.

The compatibility entry point still gathers clinical-scope, visit qualification, pending-offer and history evidence through the existing queries. Full candidates are skipped before history queries, preserving the existing query/control flow. This change does not bypass authorization, readiness or transaction locks and does not move evidence acquisition into the domain.

## Validation and limits

Domain tests cover capacity reservations in all modes, online/history precedence, workload and weighting ties, explicit STAT rules and missing deadline rules. Existing runtime tests verify last-turn ordering, pending offers, deadline snapshots, visit grouping, receiving barriers and coordinator assignments. The focused suite passed 101 tests locally. Domain import-boundary checks reject framework or persistence imports; schema and route snapshots remain unchanged.

Ranking facts are separated from decisions, but evidence acquisition, special-case qualification and assignment mutations still require explicit application interfaces. ADR 009's repository service remains in use. No production change, migration or external delivery is included.
