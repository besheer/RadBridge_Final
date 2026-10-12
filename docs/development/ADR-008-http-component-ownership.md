# ADR 008: HTTP component ownership

Date: 2026-10-11. Status: implemented on the development branch.

## Context

The mechanical extraction in ADR 004 classified functions by route decorators. Some request hooks and helpers without route decorators consequently landed in application components while receiving Flask request, session, response or rendering objects through their compatibility bindings.

## Decision

Move existing installer bodies, without rewriting their handlers, according to their actual dependencies. App-decorated handlers and hooks belong to `web.routes`; other helpers receiving HTTP framework objects belong to `web.components`. Application components receive none of the listed HTTP framework dependencies. The manifest and composition-root imports point to the new executable owners; no second implementation is retained.

Eighty of the 949 installers change owner. The resulting partition contains 12 application component modules, 12 route modules and eight web helper modules. This supersedes ADR 004's original module count, not its compatibility and source-preservation contracts.

## Validation

All original handler source hashes remain checked. Before/after metadata still has the same 160 tables and 546 route registrations. Forty focused tests passed locally, including independent clinical factories, workflow/receiving barriers, report callback URLs and component ownership. CI reruns the complete SQLite suite, PostgreSQL contracts and Docker Compose smoke check on the committed revision.

## Limits

This establishes ownership for the extracted root handlers. It does not turn `Bindings` into narrow domain interfaces, remove `legacy_runtime`, or separate all registration code from the existing service extension modules. Those remain explicit work in IMPLEMENTATION_STATUS.md. No production migration, deployment or external PACS/editor integration is performed.
