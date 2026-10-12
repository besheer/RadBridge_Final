# RadBridge Decision Engine — Phase 1

Independent DICOM Router error classification with a branch-scoped audit trail and human-review API. It has its own PostgreSQL database and Compose project. The local deterministic rules are the default. Jev and OpenAI Decisions are optional, mutually exclusive suggestion providers, each requiring an explicit provider selection and a separate disabled-by-default flag. The service does not connect to the RadBridge clinical database, process DICOM pixels, or execute a suggested action.

## Local setup

1. Copy `.env.example` to `.env.local` and replace the synthetic database password.
2. Create a local RSA keypair. The private key belongs only to the trusted RadBridge identity signer; mount the public key in this service. Never commit either key.

```sh
mkdir -p secrets
openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:3072 -out secrets/dev-identity-private.pem
openssl pkey -in secrets/dev-identity-private.pem -pubout -out secrets/decision-jwt-public.pem
```

3. Start this Compose project from this directory:

```sh
docker compose --env-file .env.local -f compose.yaml up --build -d
docker compose --env-file .env.local -f compose.yaml ps
```

The API is bound to loopback at `http://127.0.0.1:18081`; PostgreSQL has no published port. The public-key mount is read-only. Database schema upgrades run from versioned Alembic migrations before the API starts. Stop with `docker compose --env-file .env.local -f compose.yaml down`; use `down --volumes` only when deliberately removing this isolated synthetic database.

## Optional Jev adapter

Jev calls are disabled by default. They require `JEV_ENABLED=true`, a server-side `JEV_API_KEY`, and either `DECISION_PROVIDER=jev` or `DECISION_PROVIDER=auto` with Jev in `DECISION_PROVIDER_ORDER`. Keep the key in the deployment secret manager or protected server environment; never put it in Git, browser code, command history, this chat, or logs. The server code calls TypeSafe's fixed `https://api.typesafe.ai/v1/systemone` endpoint, with a four-second total timeout and redirects disabled. `JEV_MODEL` defaults to the documented `jev-latest` alias; confirm model availability for the account before enabling calls.

The adapter sends only the fixed machine codes `C_STORE_FAILURE` or `INVALID_DICOM_DATA` and a retry count. It does not send branch, actor, source/destination AE identifiers, patient/order data, reports, image pixels, or arbitrary error text. Unknown codes never go to Jev. Invalid, low-confidence, timed-out, refused, or unexpected results do not change the case: a validated category is saved only as a suggestion and the case remains `NEEDS_REVIEW` with `execution_allowed=false`. No automatic retry or provider failover is performed. Test with synthetic fixtures/mocked HTTP only; this repository does not make a live Jev request.

Jev's public API contract is documented at [TypeSafe API](https://api.typesafe.ai/docs) and [OpenAPI schema](https://api.typesafe.ai/openapi.json). The API key is not required for local rules-only or mock tests.

## Optional OpenAI Decisions adapter

The OpenAI adapter is disabled by default. It requires `OPENAI_DECISIONS_ENABLED=true`, a server-side `OPENAI_API_KEY`, and either `DECISION_PROVIDER=openai` or `DECISION_PROVIDER=auto` with OpenAI in `DECISION_PROVIDER_ORDER`. The key must be provided through an approved secret store; it must never be committed or exposed to a browser. `OPENAI_DECISIONS_MODEL` is currently restricted to `gpt-6-luna`. The adapter uses the documented `POST /v1/decisions` endpoint with one fixed choice question; the exact request/response contract and model support may change during the public beta, so verify the official [OpenAI Decisions guide](https://developers.openai.com/api/docs/guides/decisions) before enabling it.

The OpenAI adapter sends only the fixed machine codes `C_STORE_FAILURE` or `INVALID_DICOM_DATA` and a retry count. It does not send branch, actor, source/destination AE identifiers, patient/order data, reports, image pixels, or arbitrary error text. The response must contain exactly one valid category answer and a complete probability set. The validated category, confidence, model and normalized category probability map are persisted and included in the review API; raw provider payloads are not retained. Refusals, malformed results, timeouts, and unsuccessful responses fall back to the deterministic rule result and create a safe audit event. A validated category is only a suggestion; the case remains `NEEDS_REVIEW` with `execution_allowed=false`. The service does not automatically fail over to Jev or make a live API request in tests. Configure `DECISION_PROVIDER=rules` for rules-only behavior.

## Provider selection

Deterministic rules always run first. A conclusive rule result never calls an external provider. For an ambiguous allowlisted error, `DECISION_PROVIDER=jev` or `openai` pins one provider; `DECISION_PROVIDER=auto` checks the server-owned `DECISION_PROVIDER_ORDER` list and picks the first provider whose own enable flag and API key are both present. The default order is `jev,openai`, but the mode remains `rules` in `.env.example`. Invalid or duplicate provider names fail closed to rules. Provider selection is recorded in the audit log. A selected provider's timeout, refusal, or bad response does not trigger a second provider; no runtime failover, quality-based ranking, cost-based selection, or dynamic latency selection is implemented.

Enabling either hosted provider sends the allowlisted operational error code and retry count to that provider for processing. Use synthetic data for development and obtain the required privacy/security approval before sending real operational events. The adapter has no local API key and this repository has not been tested with a live provider credential.

## Authentication contract

The trusted gateway signs an RS256 JWT with its private key. This service checks `iss`, `aud`, `exp`, `sub`, `branch_id`, and `roles`. It grants access to the actor and branch in that signed assertion, never to identity or branch fields in the request body. `HELPDESK` may classify; `HELPDESK_SUPERVISOR` and `ADMIN` may review within their branch; `SUPER_ADMIN` may review across branches. A production proxy must authenticate the existing RadBridge session and issue these short-lived assertions. Do not expose this service directly to the Internet.

## Endpoints

- `GET /health/live` and `GET /health/ready`
- `POST /api/v1/decisions/evaluate` — task `DICOM_ROUTER_ERROR` only; accepts bounded source/destination identifiers, a registered error code, retry count and request ID. No arbitrary free text, patient data, DICOM data, provider selection or requested action is accepted.
- `GET /api/v1/reviews` — branch-scoped pending cases
- `POST /api/v1/reviews/{decision_id}` — accept/reject a classification with a controlled reason code. Review never executes a retry, changes a PACS destination, modifies a RIS case, or authorizes another action.
- `GET /api/docs` — API schema, only when reachable from the local trusted network.

Repeated request IDs with identical actor and evidence are idempotent. Reuse with different evidence/actor returns a conflict. Unknown error codes, data-quality and transfer failures, and exhausted retries enter human review. All classifications and reviews have append-only audit events; the case row records the current human-review outcome.

## Safe synthetic token for local acceptance

Use a test-only private key outside Git to sign a short-lived token whose claims match `.env.local`:

```json
{"iss":"radbridge-development-identity","aud":"radbridge-decision-engine","sub":"helpdesk-1","branch_id":"branch-1","roles":["HELPDESK"],"exp":1792000000}
```

Keep the signing code and token local. Never paste the token or private key into Codex, source control, issue descriptions or logs. The example claim values are synthetic and do not prove a connection to the existing RadBridge login. Until the trusted gateway is implemented, the service is a local isolated acceptance environment only.

## Phase boundaries

Phase 1 supplies deterministic rules, audit, idempotency, authentication and review APIs. Jev and OpenAI Decisions are isolated optional suggestion providers, both disabled by default and tested with mocks only. The visual Decision Center, existing RadBridge login integration, production deployment, a Redis worker and automated execution are not implemented. Enabling either provider for real operational data requires a separate privacy/security review, de-identified evaluation and explicit task approval. All provider suggestions require human review.
