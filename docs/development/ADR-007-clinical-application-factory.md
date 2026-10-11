# ADR 007: Isolated clinical composition and complete model registration

Status: implemented and covered by synthetic tests; release gates remain open.

## Composition

`web.factory.create_clinical_app(configuration)` composes the current executable entry source into a fresh runtime namespace. Handlers are installed from the same canonical modules and receive that instance's dependencies. There is no copied implementation file. The runtime is registered on its Flask application's extensions, and the compatibility resolver uses the construction context or active Flask context before falling back to legacy `app`.

Construction uses a context-local environment snapshot; it never modifies `os.environ`. Supported overrides are explicitly listed by `CLINICAL_SETTINGS`: database, secret, file directories, cookies and runtime URL settings. Other host/provider feature configuration remains process-level and is not accepted as an instance override. Bootstrap is always disabled by this factory: initialization/migrations remain separate explicit operations. Legacy `app:app` and worker CLI facades remain compatible entry points. Development Docker uses `web.factory:create_clinical_app()`.

Clinical query-scope listeners check their owning Flask application. They are registered for cleanup, preventing one instance from applying another instance's scope. `dispose_clinical_app` releases listeners, sessions, engine pools and the private runtime registration of a stopped factory instance; it refuses the legacy application.

## Complete schema ownership

Nine models formerly constructed inside extension registration now belong to canonical infrastructure model modules: six radiotherapy models, replacement settlement and two revision models. All 160 ORM models are registered once. Revision columns retain the original report/version copies and their distinct uniqueness constraints. RT relationships resolve the same canonical mappers by name. Settlement update/delete guards remain active and are installed once per canonical class.

The before/after schema and route contracts remain identical (160 tables, 546 routes). No migration or data transformation is introduced. Complete model registration also makes those tables visible before an explicitly enabled legacy fresh-bootstrap operation; this is an initialization-order correction, not permission to run that operation on existing data.

## Evidence and limits

Tests construct two applications with distinct databases, secrets and storage paths, identical user IDs/usernames and independent role dictionaries. Actual authenticated user pages and contact queries return only their own records. Scope-listener tracing verifies each application's queries invoke only its own listener. Environment and registration cleanup are checked. Existing radiotherapy, revision, settlement and scope tests remain mandatory.

This supersedes the one-clinical-instance-per-process limitation in ADRs 004–006 for the supported factory settings. It does not complete all narrow service ports, create automatic tenant partitioning, provision external services or approve production deployment. External integration and browser UAT remain release gates.
