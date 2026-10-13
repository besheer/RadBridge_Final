# ADR 024: Read-only operations snapshot dependencies

Status: implemented on the isolated development branch; new full CI required.

Dashboard aggregation receives an explicit read-only repository, readiness projection and clock. SQL filtering, sorting, bounded queries and lease evidence belong to the infrastructure repository. The web compatibility owner preserves the original keyword signature and helper exports; root and former application imports remain aliases. The existing route still owns authentication and access decisions.

Preserve descending order windows, active assignments, pending offers, terminal attention exclusion, PACS review/quarantine windows and recent event limits. The RECEIVING barrier is a read-only domain projection: it can display BLOCKED without overwriting stored readiness. The application/repository issue no mutations, flush or commit. Aggregate counts remain window-based, not whole-database totals.

Lease SQL now declares timestamp result types explicitly, ensuring SQLite returns datetime values and PostgreSQL retains timezone handling. A persisted synthetic lease test exercises expiry comparisons rather than only checking for screen/code presence. Existing broad auxiliary query scopes, including global lease statistics, are preserved; a separate authorization/branch review remains a release gate. This extraction does not certify those aggregate visibility policies or expand access.

Validation: 11 focused SQLite tests passed, including ranking/metrics projection, terminal exclusion, receiving barriers, independent repositories, persisted timestamp handling, facade identity and read-only source checks covering all executable owners. PostgreSQL clinical CI includes both new runtime/dependency files. The scheduler commit `8494b04402f11e53f4d47160c0d981a8da307423` passed all nine CI jobs (run 38166655249). Schema/route capture and new full CI remain required.
