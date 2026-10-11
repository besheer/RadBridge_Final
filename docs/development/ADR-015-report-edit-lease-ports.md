# ADR 015: Explicit report editing lease dependencies

Date: 2026-10-11. Status: implemented on the development branch; PostgreSQL CI required.

`domain.reporting.edit_policy` owns role/action authorization, FINAL protection, lease token hashing, shared exception identity and the immutable lease state. `application.services.reporting.edit_lease_service` receives persistence, a clock, grouped-order locking and reading-start callbacks explicitly. It has no framework, infrastructure, SQLAlchemy or runtime imports. The SQL adapter owns the original row locks, lease queries, upsert and token/user-scoped deletion. Legacy import paths alias the single web compatibility composition edge.

Acquisition retains group, order, report and lease lock ordering. Assigned-doctor ownership is refreshed after acquiring the order lock. Active foreign ownership or a different token blocks renewal; expired leases can be replaced. Role and FINAL checks happen before locks. The successful upsert precedes the reading-start callback. Transactions, audit and surrounding authorization remain caller-owned.

Validation: 78 focused tests passed locally and one PostgreSQL-only test was skipped locally. Direct dependency tests cover lock order, refreshed assignment denial, foreign token denial, naive UTC expiry normalization, FINAL protection and framework-free imports. The dedicated PostgreSQL test exercises actual locks/upsert, renewal and token-scoped release. Original schema/routes must remain identical.

The first PostgreSQL reporting run exposed an existing synthetic revision fixture whose branch code exceeded VARCHAR(20). The fixture now uses a shorter random suffix; no schema or clinical validation was relaxed. The prior report commit passed SQLite, Docker and all three other PostgreSQL suites, but its reporting job failed and must be rerun on this commit.

No production change is included. Revision lifecycle/editor callback dependencies and broader transaction/crash acceptance remain separate unfinished work.

Follow-up PostgreSQL validation caught SQL statements mapped to incorrect adapter operations during extraction. The adapter now maps order-owner read, report lock, lease lock and upsert to their original statements and parameters. The real PostgreSQL acquisition/renewal/release test remains mandatory; fake service ports alone did not detect this adapter defect.
