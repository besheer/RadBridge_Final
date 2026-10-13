# ADR-040: Branch-scoped stock transfer policy

- Status: Proposed; implementation blocked on workflow approval
- Date: 2026-10-13
- Scope: branch-limited inventory users and stock transfers

## Context

The transfer routes currently query `StockTransfer` by primary key and do not
authorize the action against the source or target warehouse. The transfer list
also returns the latest 300 transfers globally. Warehouse ORM filtering alone
does not secure these routes because a transfer has source/target warehouse
foreign keys rather than a `branch_id` or `warehouse_id` column.

The workflow has distinct request, approval, dispatch, and receive permissions.
Dispatch removes stock from the source warehouse; receive adds stock to the
target warehouse. A user allowed to receive for one branch must not gain the
ability to dispatch stock from another branch. Cross-branch transfers still
need a controlled way to move stock between the two branch workspaces.

## Proposed authorization behavior

1. A branch-limited user can list and open a transfer only if its source or
   target warehouse belongs to an allowed branch.
2. A request may involve the user's allowed warehouse and a counterpart
   warehouse. The request must not expose unrelated transfer records or make
   unrelated warehouses selectable.
3. Approval and rejection require the existing approval permission and a
   transfer visible under rule 1. The organization must decide whether approval
   is central-only or may be performed by either involved branch.
4. Dispatch requires the existing dispatch permission and an allowed source
   warehouse.
5. Receive requires the existing receive permission and an allowed target
   warehouse.
6. Unrestricted users continue to follow the existing permission checks.
7. Audit records must preserve actor, transfer, action, and timestamp. Failed
   scope checks must not mutate stock, transfer status, or movement records.

## Required design details before implementation

- Define how a branch requester selects a counterpart warehouse without
  exposing the full warehouse directory.
- Define the approval authority for transfers crossing branches.
- Decide whether `MAIN` warehouses are centrally controlled and which branch
  roles may request replenishment from them.
- Add tests for unrelated-branch list/detail denial, source-only dispatch,
  target-only receive, central approval, and no stock mutation on denial.
- Preserve existing permission checks; branch scope is an additional guard.

## Consequences

Until this policy is approved and implemented, branch-limited users must not be
considered safely isolated for `/inventory/transfers` or its detail/action
routes. Existing branch warehouse and stock guards do not close this gap. No
code behavior is changed by this proposed ADR.
