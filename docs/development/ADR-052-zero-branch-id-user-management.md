# ADR-052: Reject zero branch IDs in delegated user management

## Context

Branch-limited account managers must create and edit accounts only within branches they are allowed to manage. The request guard treated a parsed `branch_id` of `0` as if the field were absent because it used a truthiness check. The legacy account handlers interpret an empty or false-like branch value as `None`, which creates an unassigned account or moves an existing account into the global/unassigned scope.

## Decision

For branch-scoped requests, any supplied branch ID must be a member of the actor's allowed branch set, including zero and other false-like values. The existing missing-branch barrier remains in effect for account creation and reassignment.

## Validation

The branch-scope regression test posts `branch_id=0` to both account creation and same-branch account edit. Both requests must return 403, create no account and leave the existing account assigned to its original branch. `test_readiness_branch_scope.py` passes locally. This is a targeted authorization fix; it does not replace broader role-based browser acceptance.
