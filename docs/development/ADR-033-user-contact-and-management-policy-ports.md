# ADR 033: Contact storage and delegated management policy

Status: implemented on the isolated development branch; new full CI required.

Contact input validation, protected-role constants, access-review labels and delegated management hierarchy belong to pure identity policy modules. Contact read/write operations receive an explicit profile repository and settings reader. The repository preserves the original profile lookup/create/default department/add/flush behavior; caller commits remain unchanged.

The web compatibility owner retains old signatures, runtime composition, aborts, route/permission catalogue inspection and cache identity. Both legacy imports alias that one owner. Hierarchy checks retain active actors, SUPER_ADMIN behavior, protected target checks and permission-subset assignment; route-level users.manage checks remain authoritative and separate. Access-review labels are informational, not authorization grants.

Contact saving changes only the contacts preference subobject and supplied department/specialty fields. Existing reporting/clinical scope preferences and omitted fields remain intact. Contacts do not send messages, expose unrelated settings, transfer credentials or alter role/branch membership. CSV workflow authorization still invokes the same hierarchy policy for skipped rows and new users; its staging/apply dependencies remain unfinished.

Validation: 102 focused tests passed locally across direct contact/hierarchy dependencies, actual contact/admin routes, CSV round trips/stale preview/escalation/credential exclusions and facade identity. A first local run hit transient host MemoryError during unchanged route-source AST reconstruction; the affected check and the full focused group subsequently passed without weakening assertions. PostgreSQL scope adds direct contact, contact access and CSV tests.

The preceding RT read commit `5d6cf461a7614474bd63ac98ebd4b75593ff4554` passed all nine jobs (run 38215994034), including 2,017 SQLite tests (five skipped). New schema/route invariance and complete CI remain required. Broader user creation/edit/import transactions and route catalogue lifecycle remain explicit unfinished work.
