# ADR 022: Read-only RIS candidate search

Status: implemented on the isolated development branch; full CI required.

Candidate SQL filtering is owned by an explicit session/model repository. Bounded search orchestration belongs to the application layer and exact/partial match weighting belongs to the domain layer. The old `search_ris_orders(Order, Patient, query, limit)` keyword API delegates from the existing compatibility module through the caller's model query session, retaining the configured ORM scope guards.

Preserve the existing seven SQL search fields, numeric order-ID search, descending ID candidate window, 1–100 limit and exact-match weights/tie-breaking. SQL limiting precedes ranking; this change does not search an expanded candidate window or escape user wildcard semantics. Empty queries perform no retrieval. Searching by name can locate a candidate but cannot establish identity or authorize reconciliation. No identity matching, correction, transport or approval rules change.

Validation: 36 focused SQLite tests passed across search, resolutions, workspace permissions and module ownership. Search tests exercise exact/partial ranking, ties, bounded retrieval, independent repositories and persisted SQL phone/national-ID/UID/numeric-ID searches. The compatibility signature returns the same ORM records; synthetic tests retain accession/patient identity. PostgreSQL clinical CI includes the new search files. Broader readiness evaluation/evidence acquisition and web permission ownership remain unchanged and unfinished boundaries.
