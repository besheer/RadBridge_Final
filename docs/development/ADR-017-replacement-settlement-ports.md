# ADR 017: Replacement entitlement policy and settlement ports

Date: 2026-10-11. Status: implemented on the development branch; full CI required.

`domain.finance.settlement_policy` owns monetary validation/rounding, explicit rule specificity, duplicate-rule rejection, basis/percentage limits, frozen amount evidence and preview fingerprints. It receives candidate rules and approved discounts as explicit facts. Discount evidence remains lazy at composition to preserve rejection order for missing/invalid rules.

`application.services.finance.settlement_workflow` owns planning and confirmation through explicit repository and actor, original financial owner, replacement rule, finalized version and audit policies. The SQL adapter owns evidence queries, order/revision locks, settlement lookup and flush. The old mixed module belongs to `web.extensions.replacement_settlements`; compatibility aliases preserve event-guard/error identity and HTTP registration. Signing, CSRF, permission/branch guards and cash-entry guards remain at that edge.

Only an approved FINAL REPLACEMENT can transfer entitlement. Earlier unsettled replacements, unknown original ownership, changed preview evidence and incomplete payout verification remain barriers. Confirmation locks order then revision, revalidates signed evidence, returns known identical settlements idempotently and flushes before auditing. It never edits original financial disbursements, order/report FINAL status or the original clinical assignment. Successful commit/rollback remain caller-owned.

Validation: 79 focused tests passed locally. Tests cover explicit rule selection, ambiguity before discount consumption, independent ports, preview changes, idempotent confirmation, audit ordering and preservation of original order/cash records. The architecture checker passes; before/after structures remain identical for 160 tables and 546 routes. CI adds a dedicated isolated PostgreSQL finance suite; it must pass before review.

The corrected report-lease adapter commit f57be1b513953900230c49ae38ef8b1cd4ce6e05 passed PostgreSQL reporting, including actual lease locking/upsert/renewal/release, alongside clinical/assignment/scope suites and Docker smoke. Full SQLite completion on that commit and all checks on this commit remain required.

Other finance/collection/daily closing/inventory use cases remain unfinished boundaries. This is an isolated architecture branch, with no production, cash data, schema migration or deployment change.
