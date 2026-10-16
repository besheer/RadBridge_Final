# ADR 031: RT course state and support records

Status: implemented on the isolated development branch; new full CI required.

Course state changes, scoped notes and manual consumable records use explicit persistence and actor/scope/audit policies. The repository owns started/completed session evidence and support record creation, reusing the session repository's course-before-fraction locks. A shared application context helper provides those locked scope checks to both session and support commands; it is declared and enforced as a helper, not counted as another workflow boundary.

Preserve the original course state graph, version/reason checks, started-session terminal barrier and exact active-plan/completed-session count for closing. Terminal courses cannot reopen. Notes with a session reference require the same course and device scope before creation. Notes preserve course version. Nursing/support record permissions remain separate from the dose-command actor guard; no report editing permission is granted.

Consumables are manual quantity/unit records: their audit still states `stock_posted: false`, and the commands do not change session dose/state, stock or billing. Cancelled/NOT_GIVEN attempts and terminal courses reject new consumables. Existing record-specific checks and allowed note kinds are unchanged.

The architecture checker and generated code map now include explicitly declared shared application helpers. Three negative import tests ensure helpers cannot conceal Flask, SQLAlchemy or legacy runtime dependencies. Other mixed legacy services are not certified by this extension.

Validation: 66 focused tests passed locally (one existing optional test skipped), including direct state/support/session dependencies, actual RT routes, scoped device/branch behavior, factory isolation and import enforcement. PostgreSQL clinical includes the new support dependency file. Session commit `1095b010e0500f2e6acb34fe568ae1eaa97383d8` passed all nine jobs (run 38213659798). New schema/route invariance and full CI remain required.

All existing manual RT mutations now have explicit application services. Worklist/detail projections, registration/configuration and external treatment-device acceptance remain web/integration responsibilities requiring further review; this does not certify a treatment controller or full RT deployment.
