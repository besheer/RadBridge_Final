# ADR 042: Inject insurance-readiness runtime

Status: implemented on the isolated architecture PR, 2026-10-14.

## Context

The insurance-readiness service already used a repository, but its web compatibility adapter resolved database models and actor permissions from a process-global runtime. The DICOM Worklist sender, approval routes and work-order conversion depend on this gate to prevent dispatch before required authorization evidence is complete.

## Decision

Pass the composed runtime explicitly to the insurance actor guard, approval-readiness adapter and work-order readiness check. Declare newly used permission/model/session dependencies in the component manifest and app composition bindings. The adapter no longer calls `application.legacy_runtime.resolve_runtime`.

## Validation and limits

Regression tests forbid global runtime lookup during synthetic approval routing and the outbound Worklist guard; insurance workflow, readiness-port and handler-source contracts pass (46 focused tests). Authorization status rules and caller transaction behavior remain unchanged. This narrows composition only; external payer connectivity, retries and full staging acceptance remain separate work.
