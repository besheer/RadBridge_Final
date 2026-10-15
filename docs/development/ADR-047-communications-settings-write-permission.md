# ADR-047: Require management permission for communication settings

Status: implemented locally on `refactor/development-foundation`, 2026-10-15.

## Context

The communication provider settings and message-template writer both accepted mutations under `users.view`, which is also used for read access. Provider endpoints, transport configuration and message bodies affect outbound communications.

## Decision

Preserve the read permission but require `users.manage` or global permission for channel-setting changes and communication-template creation/updates. Declare the route's authorization bindings explicitly in the component manifest and composition root.

## Validation and limits

Synthetic HTTP tests confirm view-only users are denied and users with management permission can save both settings and templates. Other legacy administrative settings were identified by static scanning but still need endpoint-by-endpoint review.
