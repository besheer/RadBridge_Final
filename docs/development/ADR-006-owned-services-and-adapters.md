# ADR 006: Canonical ownership for services, adapters, extensions and workers

Status: implemented on development; runtime compatibility migration remains explicit.

76 previously flat modules now live under `application.services`, `infrastructure.adapters`, `infrastructure.schema`, `web.extensions` and `workers`. `application/module_manifest.json` is the complete old-to-new map. Legacy module names alias the actual canonical module object, preserving exception identity, private helper imports and monkeypatches. Worker facades additionally retain direct script execution through `runpy`; workers are never started by importing the web composition root as part of this extraction.

14 application/adapter/extension modules previously imported `app` directly. They now resolve it through one lazy compatibility seam, `application.legacy_runtime.resolve_runtime`. Existing modules which already receive `m` explicitly continue doing so. New services must receive narrower dependencies; this resolver is not a fully decoupled repository or external-service port. The supported clinical runtime remains one composed application per process.

Versioned resources are located through `infrastructure.resources.RIS_ROOT`: font, UI catalogue, client-tool source, schema migration directory and historical maintenance CLI path. This path is not used for report or attachment storage, which retain their explicit configured directories.

No schema migration, worker scheduling, network destination, transaction boundary, clinical identity rule, compression policy or report finalization behavior is changed. Existing original DDL/migrations are retained. Source contract tests resolve compatibility paths to the actual canonical executable source; all runtime assertions remain necessary.

Worker and external-service behavior still needs separately provisioned synthetic integration testing, including queue restart recovery, partial DICOM failures and editor callback failures. The development Compose stack only provisions RIS/PostgreSQL. No external images, production credentials, clinical records or host security collectors are added.
