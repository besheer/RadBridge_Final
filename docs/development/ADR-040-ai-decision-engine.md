# ADR 040: Guarded AI decision routing

Status: isolated Decision Engine with deterministic rules and optional Jev/OpenAI Decisions adapters implemented in `decision-engine/`; both external adapters are disabled by default. Provider choice is a server-side configuration, with no automatic provider fallback. Production integration remains proposed. The service has its own Compose project and PostgreSQL database. No production workflow or clinical database was changed.

## Context and goal

RadBridge may later use a structured decision service for narrow operational classification. The routing layer must prefer deterministic policy, select only an eligible provider for an explicitly approved task, and send uncertain or unavailable results to a human. A model response is evidence for a suggestion; it never grants permissions or performs a RIS/PACS action.

The provider adapters considered are TypeSafe Jev and OpenAI Decisions. Their beta/early-access APIs, quality, latency, availability, data terms, and prices can change. These are pluggable adapters, not dependencies of the core application. A provider must not be selected in production until a versioned evaluation and data-protection review passes.

## Non-goals and prohibited decisions

The engine does not diagnose images, assign clinical acuity or emergency priority, decide patient identity, match or merge a PACS study, alter an order, certify image completeness, assign a physician, finalize a report, authorize access, suppress an alarm, or send/retry a DICOM transfer. Existing deterministic rules and authorized human workflows retain those responsibilities.

Initial candidate tasks are limited to non-clinical, nonbinding classification of sanitized DICOM transport error text and Helpdesk ticket routing. A screenshot task is separately opt-in and may use OpenAI Decisions only after sensitive content has been removed. No DICOM image pixels, reports, patient names/IDs, accessions, clinical notes, or credentials are sent to an external model by default. Human review is required before a suggested category is used to change work queues or communicate externally.

## Application boundary

Current Phase 1 boundary:

```text
decision-engine/app
  -> typed DICOM router error contract
  -> deterministic rules
  -> branch-scoped decision + audit persistence
  -> human review API (classification only; no action execution)
```

The optional Jev and OpenAI Decisions providers are narrowly scoped infrastructure adapters. They accept only the fixed DICOM error codes `C_STORE_FAILURE` and `INVALID_DICOM_DATA` plus a bounded retry count, store validated category/confidence/model and token usage, and keep status at `NEEDS_REVIEW`. Each provider requires both explicit server-side selection and its own feature flag. Neither sends AE/branch/patient identifiers or arbitrary error text. Every external response remains a suggestion and cannot cause an action. Tests use mocked HTTP; no live vendor credential is needed.

Future provider-neutral application service (not implemented):

```text
web route / worker
  -> application.services.ai_decision_engine.DecisionEngine
       -> task registry + deterministic policy
       -> eligibility and approved provider-selection policy
       -> typed provider port
            -> TypeSafe Jev adapter (implemented, disabled by default)
            -> OpenAI Decisions adapter (implemented, disabled by default)
       -> decision validation + confidence policy
       -> human-review queue port
       -> audit / metrics ports
```

The future application service should receive ports; it must not import vendor SDKs. Provider adapters belong in infrastructure. Phase 1 is an isolated acceptance service and does not alter the existing RadBridge service-port count. Production authentication gateway, UI and deployment wiring remain unimplemented. Phase 1 chooses at most one provider using deployment configuration; the proposed policy-driven multi-provider selector is future work.

Proposed request contract:

```text
DecisionRequest {
  request_id, task_code, task_version, branch_id, actor_id,
  evidence: sanitized typed fields,
  sensitivity: PUBLIC | INTERNAL | RESTRICTED,
  allowed_actions: []
}
```

Proposed response contract:

```text
DecisionResult {
  outcome: RULE | MODEL_SUGGESTION | HUMAN_REVIEW | UNAVAILABLE,
  selected_value?, probabilities?, confidence?, refusal?,
  provider?, model?, policy_version?, reason_code, latency_ms
}
```

Provider input is built from a task-versioned schema and an explicit field allowlist. A caller cannot provide its own provider, prompt, choice list, or model name. Choices, score levels, thresholds, timeout, data class, fallback policy, and permitted fields are server-owned configuration. Unknown task versions fail closed.

## Routing policy

1. Validate actor/branch scope, task registration, task version, field allowlist, payload size and sensitivity. Reject disallowed fields before any vendor call.
2. Run the deterministic evaluator first. If it returns a conclusive result, return `RULE`; do not call a provider.
3. If the rule returns `NEEDS_REVIEW`, check that this task explicitly permits model assistance, its data class is allowed by the organization’s approved provider configuration, and an adapter supports the input type. Otherwise enqueue `HUMAN_REVIEW`.
4. Select among eligible providers using a server-side versioned policy: task evaluation quality first, then data eligibility, availability, latency budget and cost. A lower price or latency never overrides data restrictions or minimum quality.
5. Send only the allowlisted normalized evidence. Phase 1 uses a bounded timeout, no retries, and a single explicitly configured provider. Do not fan out one request to multiple vendors.
6. Validate the returned answer against the exact task schema, allowed values, finite probabilities, refusal state, threshold and policy version. Invalid, refused, stale, low-confidence or conflicting output becomes `HUMAN_REVIEW`; it is never coerced into a valid choice.
7. Return a suggestion to the existing caller. A human with the existing branch-scoped permission reviews it. The human’s action goes through the existing workflow use case and its normal authorization/audit checks; the model cannot invoke tools or write records.

Provider failover is not implemented. A Jev timeout cannot silently send the evidence to OpenAI, or vice versa. The deterministic result remains in place and the case stays in human review.

## Confidence and review rules

Scores are not treated as calibrated merely because an API returns probabilities. For each task/provider/model/prompt version, thresholds are established from held-out, representative, labeled examples and approved false-positive/false-negative costs. Track calibration and confusion metrics by task and branch where sample size permits. A changed model, prompt, schema, threshold, or preprocessing version invalidates prior acceptance and returns the task to shadow evaluation.

Human review is mandatory when the task is not on the approved allowlist; data is incomplete or sensitive; no provider is eligible; the model refuses; output validation fails; confidence/probability falls below the tested threshold; providers disagree in an explicitly approved comparison experiment; the request times out; the circuit breaker is open; or the result could change a clinical, identity, authorization, financial, report, or image-transfer state.

The review item shows the sanitized evidence, model suggestion and confidence, rule result, reason for escalation, and version identifiers. It records reviewer, time, branch, accepted/overridden/deferred decision, and reason. Review queues obey normal branch scope. A reviewer cannot use this screen to bypass existing workflow permissions.

## Privacy, security and operations

- Keep API credentials only in a server-side secret manager or protected deployment environment. Never return them to the browser, log them, commit them, or put them in a request record.
- Use the minimum necessary, de-identified evidence. For every external task, document data fields, provider, processing region, retention, agreement eligibility, and approval. A provider’s HIPAA/ZDR feature statement alone does not authorize PHI use; required agreements, account configuration, jurisdiction and organizational review must all be satisfied. Until approved, external PHI tasks remain disabled.
- Persist only task/version identifiers, branch/actor references, provider metadata, result codes, probabilities, latency/cost units, review outcome and a keyed digest of normalized evidence where needed. Do not retain raw prompts, images, PHI, vendor response bodies, or secrets in application logs by default. Any diagnostic sample retention requires a separate policy and access controls.
- Apply per-branch quotas, global rate limits, maximum payload/token budgets, cost caps, provider timeouts and circuit breakers. Expose queue depth, review rate, timeout/error rate, latency percentiles, cost, refusal rate and task quality drift without exposing patient content.
- If all eligible methods fail, the workflow remains in its existing safe state and a review item is raised. No AI failure may mark a case ready, complete, matched, assigned, delivered, or final.
- Use request IDs and audit records to deduplicate retries. Keep provider calls outside database transactions; do not hold a clinical write lock while waiting on network inference.

## Rollout and acceptance gates

1. Agree the first operational task, prohibited fields, and labeled ground-truth source. No task is enabled by this ADR alone.
2. The isolated Phase 1 service provides a deterministic baseline, two optional adapters, schema validation, human queue and safe configuration. Unit tests use mocked adapters and synthetic inputs.
3. Run offline evaluation on a representative, de-identified holdout. Report per-class precision/recall, false-negative cost, calibration, refusal/abstention, P50/P95 latency, request failure rate, and cost per correct suggestion for both providers and the rules-only baseline.
4. Run shadow mode in an isolated test environment. Store only approved minimized telemetry; never let suggestions change live case state. Test timeouts, duplicate calls, malformed answers, provider disagreement, circuit breaker, branch isolation and vendor outage.
5. Obtain security/privacy and domain-owner approval, then limited user acceptance. Enable a task only with a reviewed versioned threshold and a documented rollback switch. The default for any missing setting is rules plus human review.

No comparative accuracy or latency winner is asserted here. Public vendor claims and list prices are inputs to an evaluation, not acceptance evidence for RadBridge.

## Consequences

The design permits Jev for text-only structured suggestions, OpenAI Decisions where an approved task needs its text/image input capabilities, and fixed code for deterministic invariants. It makes privacy eligibility and task quality constraints stronger than cost-based routing. The cost is additional adapters, evaluation datasets, review operations, configuration governance and monitoring. If a task cannot be made safe and measurable, it remains rules-only or human-reviewed.
