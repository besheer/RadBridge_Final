# Source rollback and publication safeguards

Date: 2026-10-14. Scope: architecture port on `codex/radbridge-architecture-port` and draft PR #2. No deployment, production database/volume change, purchase or visibility change is authorized by these safeguards.

## Verified remote rollback points

Repository `besheer/RadBridge_Final` was verified private with write access. Before publishing newer local work, these reference branches were created:

| Reference | Commit | Meaning |
|---|---|---|
| `checkpoint/main-before-architecture-2026-10-12` | `9848d26bd847cc518485ab7d51879af6db86389d` | Actual main source before publication; not a fresh production data backup |
| `checkpoint/development-before-upload-2026-10-12` | `262484ed248312f1c8ec0ba9ea76d8f800500598` | Previously verified 24-service development head with nine successful checks |

These are rollback branches, not signed/immutable tags. Current GitHub branch metadata reported main unprotected. Rulesets returned an account-plan 403 requiring Pro for this private repository. Classic protection read returned a separate integration administration-permission 403. No branch protection is claimed to have been enabled. The repository stays private; no paid upgrade or collaborator invitation was made.

Desired policy when supported: prevent branch/reference deletion and force pushes, require pull requests and the nine development checks before merging, require conversation resolution and appropriately authorized review. Keep production deployment as a separate approved operation. Existing stronger rules must not be weakened. Restrict repository access to required accounts and revoke old credentials separately if exposure is found.

## Independent local rollback points

Local history is independently seeded and does not have the same commit IDs as GitHub. These annotated local tags identify source-only checkpoints:

- `checkpoint/local-contact-baseline-2026-10-12` at `c0b31edeb2415120508c89c3fe1a38276a00f1e9` (content baseline corresponding to remote development `262484ed`, not its Git identity).
- `checkpoint/local-architecture-28-services-2026-10-12` at `2773aa0d2215908eddfd35fb97c9d8f9509afa7d` (2,077 local SQLite tests passed, five skipped; not deployed).

A verified Git bundle and SHA-256 manifest may preserve this local history outside the checkout. A local bundle is not a full replica of the GitHub repository: historical cloud documents/assets omitted from the local seed must be obtained from GitHub. It is not a backup of patient images, reports, attachments, operational database, secrets or server configuration. Store a second backup on separate storage; a bundle on the same disk does not protect against disk failure.

## Publication discipline

The current main-based architecture port is commit `0d7b3b699e1ef6dfbf5bbbb300dcf3003ec49301`; all nine jobs passed in CI run `38533097682`. The earlier remote rollback branch `checkpoint/development-validated-2026-10-12` remains a separate, historical checkpoint at `eabe773cc91e6122bd9c5d3428c84230d2f298f8`. It is a mutable branch, not an immutable or signed release tag. Any subsequent code change must obtain CI on its own commit before claiming validation.

Never force-push the independent local branch over a GitHub branch. The architecture port was applied selectively on top of actual `main` in a separate branch, preserving the original development branch and the main-only blueprint/handover/viewer files. Keep `main`, production and the existing PR #1 untouched. PR #2 remains Draft until its scope and remaining release gates have been reviewed; this source-only work does not authorize merge or deployment.

Before publication inspect path/content differences, source-safety results and whether any file is omitted unexpectedly. Record local and remote source identities separately. Subsequent CI must run on the resulting remote commit; previous local/remote results are not its results.

## Automated source guard

`python tools/check_source_safety.py --history` checks current tracked content and reachable local Git blobs for operational/key/data paths and selected high-confidence provider tokens/private-key material. Output contains rule/path/line/blob only, never matched credential bytes. Example files remain subject to content checks. Unit tests cover redaction, forbidden paths, example tokens and unexpected key extensions.

SQLite CI fetches full history and runs this guard before tests. The guard is a heuristic, not proof of absence of every credential or patient data format. Full human review, account access controls, credential rotation when needed and external security testing remain necessary. Files ignored by Git may still contain sensitive local data and must never be added to an upload/archive accidentally.

If a real exposed credential is found, stop publication, restrict affected artifacts, rotate/revoke the credential with explicit authorization and plan a reviewed history repair. Do not print it, merely delete its current file, or rewrite remote history silently.

## Test server preparation

Use an independent target with independent database/files/secrets. The existing fresh-development Compose is RIS/PostgreSQL only; it does not provide a production restore/migration, full PACS/editor/viewer deployment or disaster recovery. See SERVER_TRANSFER_READINESS.md. No test-server host has been supplied or provisioned by this source-only work.
