# ADR 027: Manual RT validation and HTTP ownership

Status: implemented on the isolated development branch; new full CI required.

Amount precision/range validation, required text and local scheduled-time conversion belong to a framework-free domain module. The existing RT registration/routes, permissions, transaction logic and externally approved plan/session records belong to the web extension. Root and former application imports alias the same web owner, re-exporting the actual domain helper functions and infrastructure models.

This preserves input limits, Cairo timezone/ambiguity behavior, UTC persistence and every existing plan/session rule. It does not change prescriptions, clinical approval requirements, session delivery, nursing permissions or any treatment-machine control. No additional explicit RT transaction port is claimed; those use cases remain mixed at the web edge and require further separation.

Validation: 29 focused tests passed locally, with one optional existing test skipped. They cover manual plans/session idempotency, completed-session immutability, stale versions, course state, nursing scope, wrong attachments, device/branch intersections, factory/module identity and standalone domain import without web/database/runtime dependencies. The move initially missed a timezone import still required by a route; restored before upload and all focused tests reran successfully. Clinical PostgreSQL CI includes the new domain tests.

The preceding daily closing workflow commit `a1351f412d4068a49b87a6181fbdabd66de92a9c` passed all nine jobs in run 38167336491, including 1,961 SQLite tests (five skipped). The consolidated implementation status now distinguishes implemented ownership/ports from unfinished integration and release gates. New schema/route and full CI results remain required.
