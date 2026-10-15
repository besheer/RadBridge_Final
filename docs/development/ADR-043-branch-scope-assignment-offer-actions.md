# ADR-043: Branch-scope assignment offer actions

Status: implemented locally on `refactor/development-foundation`, 2026-10-15.

## Context

The offer-start action accepted a case ID under `assignment.manage` without the branch read guard, then called shared candidate selection. The manual offer-expiry action also processed order-linked offers and assignments without a request branch scope. A branch-scoped manager could therefore target a foreign case or trigger work outside the manager's branch.

## Decision

Apply the branch-scoped request guard to offer start and manual expiry. Scope order-linked ORM work, and scope candidate users, assignment profiles and availability records to the permitted branches. Global users retain their existing all-branch behavior.

## Validation and limits

Synthetic HTTP tests verify that a foreign-branch order is denied, candidate lookup excludes foreign-branch doctors, and the expiry route sees only offers linked to the manager's branch. The actual scheduled background worker has no request context and requires a separate scheduler authorization/scope review.
