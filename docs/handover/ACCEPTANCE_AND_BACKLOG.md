# Acceptance, gaps and next work

## Recorded acceptance, scoped to this release

| Evidence | Result | Limit |
|---|---|---|
| Full RIS runtime suite | 1778 passed, 3 skipped | Historical release result; documentation did not rerun tests |
| Isolated PostgreSQL RT suite | 22 passed | Synthetic DB; includes concurrent idempotent completion |
| Synthetic bilingual RT pages | 8 checks, 1440/390 widths, no overflow/errors | Synthetic render, not real clinical treatment acceptance |
| Authenticated live RT GET and navigation | Desktop/narrow, no observed page/server/request failures | Read-only; no production clinical records created |
| Controlled RIS release | Healthy; config/mounts/networks retained; unrelated services unchanged | Snapshot in time, not continuous monitoring |
| RT schema migration | Six new tables; existing tables not altered | Separate additive migration, not a universal migration manager |
| GitHub source import | Private, 2913 source/manifest files + explanatory document | Reviewed text snapshot with explicit omissions |
| Blob verification after upload | App, RT module/migration/template, requirements and manifest matched | Representative critical files checked individually |

Release evidence is retained on the server under `/opt/radbridge/checkpoints/radiotherapy-manual-20261009/`; source/operational checkpoint is `/opt/radbridge/checkpoints/radbridge-checkpoint-20261009T202252Z-cf59dc1/`. Do not publish private container/authentication evidence files.

## Status definitions

**Release-tested** means an explicit result exists for the stated checkpoint and scope. **Source present / revalidate** means implementation is visible but new-environment or external clinical acceptance is not certified here. **Deferred / not built in this phase** identifies a known boundary. No feature becomes complete merely because a screen exists.

| Area | Status at this handover | Next action |
|---|---|---|
| Manual RT courses/plans/PET links/session ledger | Release-tested | Configure real devices/authorized specialist users and conduct an approved clinical workflow walkthrough |
| RT machine/TPS integration and automatic multi-target doses | Not built in this phase | Agree external contracts, safety policy and a new implementation scope |
| RT stock deduction/billing | Not built in this phase | Decide stock transaction and billing rules; current consumables are only a manual ledger |
| ECG catalog/workflow | Explicitly deferred | Obtain approved procedure codes, responsibilities and image/document requirements |
| Procedure technician/nursing policies | Prior release-tested; source present | Verify actual per-code metadata and scope in each branch |
| OHIF/Weasis | Source present / revalidate clients | Retest actual patient-authorized study opening and CPU/WebGL behavior in supported clients |
| RadiAnt | Integration paths present; client setup deferred | License/install supported client and perform controlled launch/data-access UAT if requested |
| Viewer image/measurement insertion into report | Historical request; fresh end-to-end proof absent from this handover | Review source and perform a synthetic capture/insert/save/verify scenario |
| Report editor/correction save | Source present / revalidate external callback path | Demonstrate persisted draft and immutable verified/final versions with the current ONLYOFFICE service |
| Manual PACS-to-RIS reconciliation | Prior release-tested; identity-sensitive | Verify top PACS/bottom RIS comparison and approved mismatch/correction path |
| Assignment readiness / RECEIVING blocking | Source present / revalidate all assignment entry points | Test single/bulk/automatic assignment with receiving and explicitly ready cases |
| Security/VPN dashboard and host collector | Source/recorded host checks present | Inspect current collector age, Fail2ban policy, VPN issuance/revocation and current country policy privately |
| Full disaster recovery | Not demonstrated by this upload | Collect separate backup set and rehearse a complete isolated restore |
| Independent branch DICOM gateway | Separate requested project | Review/reuse source under its own plan; do not apply its queue/validation assumptions to current production silently |
| Training videos, Arabic/English male narration | Requested earlier; delivery not evidenced in this checkpoint | Inventory existing recordings and agree role-by-role scenarios using synthetic cases |

This is not a declaration that every revalidation item is broken or unfinished. It distinguishes verified evidence from unverified current external behavior and historical requests.

## Recommended next maintainer tasks

1. Establish a full restore plan and complete the omitted-asset inventory before treating GitHub as a recovery system.
2. Validate a complete synthetic staff → coordinator → doctor → report workflow, plus a manual RT walkthrough with the correct branch/device roles.
3. Prioritize ECG or RT external/stock work only after the owner chooses the next scope.
4. Keep tests, route/schema inventories, handover baseline and GitHub source export aligned with each accepted release.
