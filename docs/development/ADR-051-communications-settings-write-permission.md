# ADR-051: Require management permission for communication settings

Status: ported to the isolated draft PR #2 review branch, 2026-10-15; CI pending.

## Context

The communication provider settings and message-template writer both accepted mutations under `users.view`, which is also used for read access. Provider endpoints, transport configuration and message bodies affect outbound communications.

## Decision

Preserve the read permission but require `users.manage` or global permission for channel-setting changes and communication-template creation/updates. Declare the route's authorization bindings explicitly in the component manifest and composition root.

## Validation and limits

Synthetic HTTP tests confirm view-only users are denied and users with management permission can save both settings and templates. `ris/tests/test_admin_communications_permissions.py` passed 2 tests on the review branch. Other legacy administrative settings still need endpoint-by-endpoint review.

