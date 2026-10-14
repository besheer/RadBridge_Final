# ADR 044: Explicit runtime for assignment monitoring

Status: implemented locally on the isolated architecture PR, 2026-10-14.

## Context

The assignment-monitor web routes already received restricted component bindings, but their compatibility adapter resolved the active application runtime globally. Its monitoring projection also called assignment policy helpers that independently resolved that global runtime.

## Decision

Pass the route's declared runtime bindings into the monitoring adapter and into its policy/capacity query helpers. The two route components now declare their required database, model, policy and doctor-list dependencies in `app.py` and `component_manifest.json`. Keep the helper's implicit-runtime fallback only for legacy direct callers while those callers are migrated.

## Validation and limits

The monitor-route tests replace the global runtime resolver with a failure and verify both routes still render. The assignment monitor, distribution and component boundary suites passed locally (52 tests); architecture and source-safety scans passed. This narrows composition for the monitor routes only; other assignment routes and the compatibility fallback remain.
