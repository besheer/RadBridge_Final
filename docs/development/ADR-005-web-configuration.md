# ADR 005: Explicit web configuration and shell construction

Status: implemented on the development branch.

`infrastructure.settings.WebSettings` captures an environment mapping explicitly. `web.factory.create_web_app` constructs an independent Flask shell without database initialization, filesystem creation, bootstrap writes or workers. The legacy composition root supplies its own import name and original resource directory, so template/static lookup and SQLite instance-path behavior remain compatible.

Configuration values, limits and cookie behavior match the previous implementation. This extraction intentionally does not change the historical secret/database defaults: development Compose already supplies isolated values; production hardening is a separate authorized configuration change.

Shell independence has a synthetic test. It does not imply that two fully composed clinical applications can coexist in one Python process: legacy orchestration still owns shared globals. `app:app` remains the supported WSGI entry point until that dependency migration is completed and verified. No migrations or production changes are included.
