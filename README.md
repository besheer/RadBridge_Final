# RadBridge — architecture, documentation and handover

بوابة الدخول لتوثيق وتسليم RadBridge للمطور أو الأيجنت التالي.

## Current development architecture

The isolated `refactor/development-foundation` branch implements architecture changes reviewed in [draft PR #1](https://github.com/besheer/RadBridge_Final/pull/1). Main and production are unchanged. This branch is not an approved production release.

Start with [development setup](docs/development/README.md), [implementation and remaining gates](docs/development/IMPLEMENTATION_STATUS.md), [measured progress](docs/development/PROGRESS.md) and the [executable code map](ris/docs/CODE_MAP.md). ADRs in `docs/development/` describe preserved contracts, explicit workflow dependencies and remaining compatibility seams.

The captured schema/route inventory remains 160 tables and 546 registrations. All 949 extracted RIS-entry-point functions and 76 migrated modules have canonical owners. Ownership completion does not establish complete dependency inversion or external integration; progress percentages must use a stated, reviewed denominator.

## Historical checkpoint and blueprint

[Technical handover](docs/handover/README.md) and [Blueprint v1.0](docs/blueprint/README.md) describe the recorded source checkpoint; the [architecture-change validation plan](docs/blueprint/VALIDATION_PLAN.md) remains the release-gate reference. Creating that original blueprint was documentation-only. The subsequent development branch implements separately documented source changes.

Historical source baseline: `cf59dc1b4fb07d23434251ef6d1a4ba20ed64bb0`, dated 2026-10-09. Reviewed GitHub source snapshot: `28473d9cb111a904da8107b0a6d49cbb0c53bb96`. These are checkpoint identities, not the current development head.

| Guide | Contents |
|---|---|
| [دليل الاستخدام بالعربية](docs/handover/USER_GUIDE_AR.md) | الاستقبال والفني والتمريض والمنسق والطبيب والعلاج الإشعاعي |
| [Historical architecture](docs/handover/ARCHITECTURE.md) | Recorded services, boundaries, modules and workflow |
| [Operation and release runbook](docs/handover/OPERATIONS.md) | Development checks, deployment, migration and rollback |
| [Workflows and roles](docs/handover/WORKFLOWS_AND_ROLES.md) | Registration, readiness, reconciliation, reporting and staff work |
| [Radiotherapy handover](docs/handover/RADIOTHERAPY.md) | Manual approved plans, PET/CT links, sessions and permissions |
| [Backup and recovery](docs/handover/BACKUP_AND_RECOVERY.md) | What GitHub protects and what a full restore still needs |
| [Security operations](docs/handover/SECURITY.md) | Authentication events, country policy, VPN and access reviews |
| [Acceptance and backlog](docs/handover/ACCEPTANCE_AND_BACKLOG.md) | Recorded checks, deferred items and new-environment verification |
| [Historical route inventory](docs/handover/ROUTE_INVENTORY.md) | Generated static routes and declared permission guards at the checkpoint |
| [Historical ORM inventory](docs/handover/ORM_INVENTORY.md) | Generated table, column and foreign-key declarations at the checkpoint |

This private repository contains a reviewed text source snapshot and isolated development work. Binary assets/documents, potential credentials, patient data and old code backups are excluded from the original checkpoint; see [CHECKPOINT_MANIFEST.json](CHECKPOINT_MANIFEST.json). Development-specific restored assets are documented with their licenses and hashes. It is not a complete disaster-recovery backup or a guaranteed full PACS/editor one-command installation. The original Git history remains on the server.

Historical `AGENTS.md`, README files, image labels and deployment examples may name older environments. The current owner's explicit isolated-GitHub instruction governs this development task; it does not authorize live/stage deployment. Verify actual resources and release authorization before operating them.
