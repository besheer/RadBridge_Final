# ADR-042: Branch-scope the coordinator manual doctor picker

Status: implemented locally on `refactor/development-foundation`, 2026-10-15.

## Context

The coordinator manual-assignment handler scoped candidate orders to the actor's branch, but its doctor query was global. The preview path accepted a doctor selected from that query and did not independently enforce that the doctor belonged to the same permitted registration branches. This could expose foreign-branch clinician names and allow attempted cross-branch case assignment.

## Decision

Add the manual-assignment endpoint to the existing request-level branch scope. Restrict `User`, doctor assignment profiles and availability records to users in the permitted branches for this endpoint, along with the existing scoped order and case-linked records. Global users retain the existing all-branch path.

## Validation and limits

Synthetic route coverage verifies that a branch coordinator sees only same-branch doctors and that a forged preview request selecting a foreign-branch doctor is rejected without creating assignments. The focused manual-assignment and assignment-monitor suites pass locally. This is a targeted endpoint guard, not a complete authorization audit or browser acceptance result.
