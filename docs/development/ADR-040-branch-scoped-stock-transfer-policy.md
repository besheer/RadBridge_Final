# ADR-040: Branch-scoped stock transfer policy

Date: 2026-10-14

## Decision

- A branch user may request stock only from an active `MAIN` warehouse that is the parent of an active `BRANCH` warehouse assigned to one of that user's permitted branches.
- The destination must be an active `BRANCH` warehouse assigned to a permitted branch. Cross-branch targets, substores, unrelated main warehouses and inactive warehouses are rejected by the server.
- Approval, rejection and dispatch require a central user with the matching permission. A branch user's permission string alone cannot grant these actions.
- Receipt is limited to a branch user authorized for the destination branch. Central users cannot mark branch stock received.
- Transfer listings, transfer details, related lines and warehouse relationships are constrained to valid central-to-branch transfers in the active request context.

## Rationale

The branch originates a request and the central warehouse controls release. Warehouse hierarchy is the source of the authorized central-store relationship; a submitted warehouse ID or a hidden form field is never trusted as authorization evidence.

## Verification and limits

Synthetic route tests cover valid requests, foreign branch listings, invalid source and target warehouses, branch denial of central actions, and central approval. PostgreSQL concurrency and live role/browser acceptance remain release gates. This policy does not constitute production deployment or a production security certification.
