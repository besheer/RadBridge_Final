# Persistence ownership and compatibility

The legacy web module declared 151 ORM classes alongside request handlers. These definitions now belong to eleven modules under `ris/infrastructure/models`. `ris/infrastructure/extensions.py` owns the unbound SQLAlchemy extension. The web composition initializes it explicitly.

Model bodies, table names, column definitions, defaults, constraints and relationships are unchanged. Existing `app.ModelName` references remain aliases to the single canonical class. No second mapper or table registry is introduced. No migration or production data change is needed for this extraction.

Before and after extraction, a fresh synthetic runtime exposes the same 160 tables and 546 URL rules, methods, arguments and endpoints. A standalone persistence test loads the schema without importing the web runtime and verifies isolation between two in-memory application databases. Existing clinical, reporting, assignment and permission suites remain required.

The eleven owners are identity, registration, clinical, communications, inventory, finance, assignment, readiness, imaging, reporting and operations. This is a shared PostgreSQL schema inside a modular monolith. Ownership does not mean separate databases or microservices.

Legacy request orchestration and remaining root-level services still require subsequent extraction. This change alone does not complete the architecture or authorize deployment. Compatibility imports are temporary entry points; new persistence consumers should import canonical classes.
