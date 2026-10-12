# RadBridge Decision Engine — Phase 1

Independent, rules-only DICOM Router error classification with a branch-scoped audit trail and human-review API. It has its own PostgreSQL database and Compose project. It does not connect to the RadBridge clinical database, call Jev/OpenAI, process DICOM pixels, or execute a suggested action.

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

The API is bound to loopback at `http://127.0.0.1:18081`; PostgreSQL has no published port. The public-key mount is read-only. Database schema upgrades run from the versioned Alembic migration before the API starts. Stop with `docker compose --env-file .env.local -f compose.yaml down`; use `down --volumes` only when deliberately removing this isolated synthetic database.

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

Phase 1 supplies deterministic rules, audit, idempotency, authentication and review APIs. It does not supply the proposed visual Decision Center, existing RadBridge login integration, production deployment, a Redis worker, Jev/OpenAI adapters or automated execution. Those need separate implementation and review. Later vendor calls remain disabled until de-identified evaluation, data-protection approval, shadow-mode acceptance and explicit per-task thresholds pass.
