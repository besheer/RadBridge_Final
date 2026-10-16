# ADR-043: Branch-scope assignment offer actions

Status: ported to the isolated draft PR #2 review branch, 2026-10-15; CI pending.

## Context

The offer-start action accepted a case ID under `assignment.manage` without the branch read guard, then called shared candidate selection. The manual offer-expiry action also processed order-linked offers and assignments without a request branch scope. A branch-scoped manager could therefore target a foreign case or trigger work outside the manager's branch.

## Decision

Apply the branch-scoped request guard to offer start and manual expiry. Scope order-linked ORM work, and scope candidate users, assignment profiles and availability records to the permitted branches. Global users retain their existing all-branch behavior.

## Validation and limits

Synthetic HTTP tests verify that a foreign-branch order is denied, candidate lookup excludes foreign-branch doctors, and the expiry route sees only offers linked to the manager's branch. `ris/tests/test_assignment_offer_branch_scope.py` passed 5 tests on the review branch. The actual scheduled background worker has no request context and requires a separate scheduler authorization/scope review.

