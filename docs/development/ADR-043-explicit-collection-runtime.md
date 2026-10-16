# ADR 043: Inject branch-collection runtime

Status: implemented locally on the isolated architecture PR, 2026-10-14.

## Context

Reception collection authorization and branch checks already used a small application service and repository, but the compatibility edge resolved the active application runtime globally. The helper is used by permission evaluation, receipt/payment/refund routes and registration-time payment collection.

## Decision

Pass runtime explicitly to both collection-policy entry points. Route/component composition supplies the binding set; required branch, session, current-user and abort dependencies are declared in the component manifest and app composition. The collection adapter no longer calls `application.legacy_runtime.resolve_runtime`.

## Validation and limits

The synthetic collection test makes global runtime resolution fail, then verifies reception permission evaluation and same-branch payment routing (34 focused route and component-boundary tests passed). Branch rules and payment transaction behavior are unchanged. This narrows composition only; it does not certify all finance paths or eliminate the legacy global stock ledger.
