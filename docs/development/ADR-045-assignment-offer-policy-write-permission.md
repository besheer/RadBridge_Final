# ADR-045: Require management permission for offer policy changes

Status: implemented locally on `refactor/development-foundation`, 2026-10-15.

## Context

The admin assignment-offer settings endpoint allowed POST changes to its global policy under `users.view`, a read permission. This also exposed an architectural dependency gap: the route implementation had no declared `has_perm` or `abort` bindings for a write authorization check.

## Decision

Keep GET access under `users.view`; require `users.manage` or global permission before changing the offer policy. Declare both authorization dependencies in the component manifest and composition binding.

## Validation and limits

Synthetic HTTP tests confirm read-only users can view but not modify the settings, while managers can save. Component-boundary tests pass. The policy remains global; this change does not introduce branch-specific offer configuration.
