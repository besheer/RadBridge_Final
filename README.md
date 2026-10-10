# RadBridge — documentation and handover

بوابة الدخول لتوثيق وتسليم RadBridge للمطور أو الأيجنت التالي.

**Start here:** [Technical handover](docs/handover/README.md).

**Project blueprint / المخطط المعماري:** [Blueprint v1.0](docs/blueprint/README.md), including the [architecture-change validation plan](docs/blueprint/VALIDATION_PLAN.md). These are documentation/design files; no architectural refactor or production deployment was performed.

Source baseline: `cf59dc1b4fb07d23434251ef6d1a4ba20ed64bb0`, dated **2026-10-09**. Reviewed GitHub source snapshot: `28473d9cb111a904da8107b0a6d49cbb0c53bb96`.

| Guide | Contents |
|---|---|
| [دليل الاستخدام بالعربية](docs/handover/USER_GUIDE_AR.md) | الاستقبال والفني والتمريض والمنسق والطبيب والعلاج الإشعاعي |
| [Architecture and code map](docs/handover/ARCHITECTURE.md) | Services, boundaries, modules and workflow |
| [Operation and release runbook](docs/handover/OPERATIONS.md) | Development checks, deployment, migration and rollback |
| [Workflows and roles](docs/handover/WORKFLOWS_AND_ROLES.md) | Registration, readiness, reconciliation, reporting and staff work |
| [Radiotherapy handover](docs/handover/RADIOTHERAPY.md) | Manual approved plans, PET/CT links, sessions and permissions |
| [Backup and recovery](docs/handover/BACKUP_AND_RECOVERY.md) | What GitHub protects and what a full restore still needs |
| [Security operations](docs/handover/SECURITY.md) | Authentication events, country policy, VPN and access reviews |
| [Acceptance and backlog](docs/handover/ACCEPTANCE_AND_BACKLOG.md) | Recorded checks, deferred items and new-environment verification |
| [Route inventory](docs/handover/ROUTE_INVENTORY.md) | Generated static routes and explicitly declared permission guards |
| [ORM inventory](docs/handover/ORM_INVENTORY.md) | Generated table, column and foreign-key declarations |

This private repository contains a **reviewed text source snapshot**. Binary assets/documents, potential credentials, patient data and old code backups are excluded; see [CHECKPOINT_MANIFEST.json](CHECKPOINT_MANIFEST.json). It is not a complete disaster-recovery backup or a guaranteed one-command installation. The original Git history remains on the server. No production configuration is changed by this documentation commit.

The files under `docs/handover/` describe this checkpoint and supersede conflicting historical descriptions **for this checkpoint only**. Existing `AGENTS.md`, legacy README files, image labels and deployment examples may name older environments. Verify actual resources and the current owner's instructions before operating them.
