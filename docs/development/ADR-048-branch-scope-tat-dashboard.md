# ADR-048: Branch-scope the TAT dashboard

Status: ported to the isolated draft PR #2 review branch, 2026-10-15; CI pending.

## Context

The TAT dashboard queried recent orders directly and had no branch-specific query. Unlike the readiness page, it did not use a dedicated branch filter, so a user with `orders.view` and a branch assignment could see other branches' cases and delay metrics.

## Decision

Add the TAT dashboard endpoint to the shared branch-scoped read guard. Existing all-branch users retain the current behavior.

## Validation and limits

The synthetic readiness branch-scope test also verifies the TAT page contains the user's case and omits a foreign-branch case. `ris/tests/test_readiness_branch_scope.py` passed 14 tests on the review branch. This does not certify every operational metrics route or replace role-based browser acceptance.

