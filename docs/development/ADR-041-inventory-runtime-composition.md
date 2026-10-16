# ADR 041: Inject inventory transaction runtime

Status: implemented on the isolated architecture PR, 2026-10-14.

## Context

Inventory use and return handlers called a compatibility adapter that obtained the application runtime from a process-global resolver. The domain return policy and original-lot repository were already explicit, but the composition edge remained implicit.

## Decision

The inventory component passes its declared runtime bindings to the adapter for order locking and original-lot returns. The component manifest and `app.py` composition list the ORM models, session and movement/warehouse callbacks used by the adapter. The adapter has no fallback to the global runtime resolver.

## Validation and limits

A regression test forbids runtime resolution while a synthetic case consumes and returns stock. Inventory safety and return-service suites pass. The change preserves the existing caller transaction boundary and return policy; it adds no schema change and performs no production operation. This narrows two inventory call paths but does not separate inventory consumption, general stock movement, warehouse lifecycle or branch-accurate legacy balances.
