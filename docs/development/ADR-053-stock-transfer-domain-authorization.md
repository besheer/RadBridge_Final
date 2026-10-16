# ADR-053: Isolate stock-transfer authorization decisions

- Status: Accepted
- Date: 2026-10-16
- Scope: isolated architecture port / draft PR #2

## Context

Stock-transfer request, central approval/rejection/dispatch, and branch receipt rules were embedded in a Flask request guard that also loads warehouses and transfers through SQLAlchemy. This made a core authorization decision difficult to test independently from HTTP and persistence behavior.

## Decision

Move the pure authorization rules into `domain.inventory.transfer_policy`:

- A branch may request stock only for an authorized destination branch and only from its linked central warehouse.
- Approve, reject, and dispatch are central actions requiring the explicit central-approval capability.
- Receipt is permitted only to a user authorized for the transfer's destination branch.
- Unknown actions fail closed.

The same domain module owns the valid status transitions: REQUESTED to APPROVED or REJECTED, APPROVED to REJECTED or DISPATCHED, and DISPATCHED to RECEIVED. Invalid transitions return no next state. Route handlers continue to own persistence, stock movement, audit, and transaction boundaries.

Keep request parsing, permission resolution, warehouse relationship queries, HTTP denial, and ORM query filtering in the existing web extension. The domain module takes primitive values and imports no framework or persistence code.

## Consequences

The authorization and lifecycle rules have direct parameterized tests and can be reused by a future transfer application service. The existing runtime transaction and transfer routes remain coupled to the compatibility layer; this ADR does not claim that the stock-transfer workflow has been fully extracted.

## Validation

`test_inventory_transfer_domain_policy.py`, `test_inventory_transfer_policy.py`, and `test_inventory_transfer_branch_scope.py` cover the extracted rules. Architecture and source-safety checks pass. No schema, route contract, persistence structure, or production environment was changed.
