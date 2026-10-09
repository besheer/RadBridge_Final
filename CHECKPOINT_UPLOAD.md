# RadBridge — reviewed source checkpoint

Original server commit: `cf59dc1b4fb07d23434251ef6d1a4ba20ed64bb0`.
Checkpoint date: 2026-10-09.

This private repository contains a reviewed current source snapshot of RadBridge RIS and OHIF, not the original Git history. Consult `CHECKPOINT_MANIFEST.json` for file hashes and exclusions.

Production patient images, databases, private environment configuration, credentials and private keys are excluded. Legacy code backups and binary documentation/assets are also omitted; this is not a complete disaster-recovery backup or an immediately deployable package with every binary asset. The complete tracked source remains pinned by Git tag `checkpoint/radbridge-20261009T202252Z` on the server.

The runtime release passed 1778 tests (3 skipped), plus 22 isolated PostgreSQL tests and desktop/mobile browser checks. This upload does not deploy or change production.

Application code and dependencies: `ris/`, `ris/requirements.txt`, `ris/Dockerfile`; viewer source: `ohif/`. Use dummy environment values when preparing a separate development environment. Review deployment paths and local settings before running any included operational scripts.
