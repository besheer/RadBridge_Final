# ADR 045: Branch-scope assignment monitoring

Status: ported to the isolated draft PR #2 review branch, 2026-10-15; CI pending.

## Context

The admin assignment monitor and coordinator assignments page require assignment/report-coordination permissions, but they were absent from the request-level branch-scope allowlist. Their monitoring queries include open cases, active assignments, offers, doctor profiles and availability states, so branch-scoped users with those permissions could see information from other branches.

## Decision

Apply the existing registration-branch scope to both monitor endpoints. Restrict case-linked records through the scoped order IDs; restrict doctor users, assignment profiles and availability states to users assigned to permitted branches. Global users keep the existing all-branch behavior. This is a visibility guard and does not change assignment permissions or workflow transitions.

## Validation and limits

The synthetic route regression covers both monitor endpoints; `ris/tests/test_assignment_monitor.py` passed 10 tests on the review branch. This does not certify branch scope across unreviewed endpoints or replace role-based browser UAT.

