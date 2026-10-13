# ADR 018: Original-lot inventory return dependencies

Date: 2026-10-11. Status: implemented on the development branch; full CI required.

`domain.inventory.return_policy` owns finite-positive quantity validation and net return credits grouped by original lot and original unit cost. `application.services.inventory.return_service` owns return orchestration over explicit repository, default warehouse, actor and movement dependencies. `SqlAlchemyInventoryReturnRepository` owns order locking, usage evidence, expiry-ordered locked lot queries and return row construction. Compatibility imports alias the web composition edge.

Returns retain the original lot, warehouse/item and unit cost. Missing original lot evidence, malformed prior returns or quantities greater than the net issued amount reject before movement. WASTE is excluded from refundable usage. Order locking precedes usage reads, and all expected original lots are locked and validated before stock movement. The existing inventory-movement callback remains composed at the edge; consumption/movement services are not yet separated. Callers retain commit/rollback ownership.

Validation: 34 inventory/ownership tests passed locally; a combined inventory/settlement/ownership run passed 69 tests after fixture adjustments. New direct-port tests cover split lots/costs, excess return, mismatched lot evidence and invalid prior-return evidence, plus imports without runtime/database/web dependencies. Existing tests retain expiry, reservation, repeated-return and cross-case barriers. Schema/routes remain identical for 160 tables and 546 registrations.

CI adds an isolated PostgreSQL inventory suite. Its fixtures now use valid branch lengths and an actual synthetic technician row for foreign-key integrity. The previous finance CI run passed 45 tests but failed its missing-CSRF route fixture: request rollback erased the uncommitted synthetic actor. That test now uses a nested savepoint for expected request rollback, modeling a production actor that already exists in a committed transaction. The production CSRF handler is unchanged. Both new suites require green checks on this commit.

No stock migration, production data, schema change or deployment is included. Inventory consumption, general movement and operational transaction/recovery boundaries remain unfinished.
