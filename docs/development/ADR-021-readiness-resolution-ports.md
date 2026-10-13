# ADR 021: Readiness resolution dependencies

Status: implemented on the isolated development branch; external acceptance remains pending.

Five existing resolution workflows now receive an explicit repository and clock: clinical history, evidence-backed series aliases, image minimum overrides, and deactivation of aliases/overrides. Domain barriers and alias enrichment belong to `domain.readiness_resolution`; SQL locking, evidence queries and model creation belong to the readiness repository. Old imports/signatures remain aliases to one web compatibility owner.

The caller owns commit/rollback. Order locks and VERIFIED/FINAL/CANCELLED barriers precede evidence lookup or mutation. Series aliases require captured PACS evidence and the selected rule's required canonical series. Overrides cannot invent received images; replacing an active override flushes its deactivation before creating the replacement. Retry of an already inactive record creates no duplicate event. No workflow changes identity, DICOM data, reports, or transport status.

The legacy optional readiness-model argument and series alias scope behavior are preserved. Route permission/branch checks remain at the web edge. Searching RIS orders, evidence acquisition, broader readiness evaluation and exceptional approval authorization are not newly separated or expanded by this change. An image minimum override is an existing reviewed exception, not proof of scan completeness.

Validation: 53 focused SQLite tests passed, including direct repository-port tests and persisted synthetic evidence/alias/history/override operations. PostgreSQL clinical CI includes both new test files. Before/after schema and route capture and architecture checks must pass; full CI on the new commit remains required. The preceding insurance commit `29d9b8b8a6efd323ee158a6f7995a5c2afa638a4` passed all nine CI jobs (run 38157320020).
