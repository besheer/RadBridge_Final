# ADR 023: Readiness scheduling and refresh dependencies

Status: implemented on the isolated development branch; new full CI required.

Configuration validation, interval selection and eligibility are pure domain policies. Refresh and automatic scheduling receive explicit persistence/evaluation/audit/clock dependencies. The repository owns SQL candidates, order/report locks, PostgreSQL advisory-lock connections, audit persistence and commit/rollback operations. HTTP registration, permission/branch checks, CSRF, settings publication and manual notifications belong to the web extension; both legacy import paths alias that same owner.

Preserve paused defaults, invalid settings failure, oldest-first candidate window (500), batch/time budgets, per-modality timing, report lock contention detection, terminal-case barriers, per-case commit/rollback and the existing advisory lock key. A busy worker performs no retrieval. Lock release remains in a finally block. This deliberately retains the original worker's transaction ownership; it does not claim a caller-owned transaction for the whole batch.

Refresh still forces failed PACS evidence to BLOCKED with the specific unavailable/not-linked/identity-mismatch blocker and updated facts hash. An unchanged automatic refresh does not duplicate its audit; actor-triggered refresh retains actor audit. Evaluation itself remains an injected compatibility dependency, not a provisioned PACS integration. Process scheduling and external transport lifecycle are unfinished.

Validation: 35 focused SQLite tests passed (one PostgreSQL-only lock test skipped). Direct dependency tests cover pause/busy/terminal/contended-report/budget/batch/error/cleanup/audit paths. Persisted synthetic SQL tests check candidate exclusion, order/report locking and readiness persistence using flush instead of commit so fixture rollback can clean up. A separate PostgreSQL test uses two actual connections to verify busy locking and reacquisition after release; clinical CI includes both new test files. Scoped search commit `1c6f6f6120819497bac0fabb28965eea86939051` passed all nine jobs in run 38166426996. Schema/route invariance and new full CI remain required.
