# ADR-050: Scope doctor assignment profile management

Status: ported to the isolated draft PR #2 review branch, 2026-10-15; CI pending.

## Context

The doctor-profile administration page used `users.view` for both reading and editing, listed all doctors/profiles, and trusted a posted user ID without checking that it belonged to the manager's branch. It can also control availability, modalities and assignment eligibility.

## Decision

Keep page read access under `users.view`, require `assignment.manage` or global permission for writes, branch-scope the doctor/profile queries, and validate the posted doctor through the scoped `User` query before creating or updating a profile. Declare the new model and authorization dependencies in the component manifest and generated composition bindings.

## Validation and limits

Synthetic HTTP tests verify that a branch manager cannot see or edit a foreign-branch doctor's profile and that a read-only user cannot edit a profile. `ris/tests/test_assignment_offer_branch_scope.py` passed 5 tests on the review branch. This does not define per-doctor delegation within a branch or cover non-HTTP background assignment changes.

