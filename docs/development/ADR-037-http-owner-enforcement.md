# ADR 037: HTTP owners and a package-wide Flask import gate

Status: implemented locally on the isolated development branch; full suite outcome recorded in implementation status.

Six existing modules contained Flask request/session/abort/response/route code but were owned under application/services: staff worklist filters, procedure staff workflow, user CSV transfer, draft report notices, correction report editor and the legacy booking handler. They now belong to web/extensions, or web/compatibility for booking. Exact file SHA-256 contents were verified unchanged during relocation. Legacy aliases and the 76-entry canonical-owner manifest were updated together; no new service port is counted for relocation.

The architecture checker now rejects direct Flask imports in every application/services file, including those not registered in port_contracts. Tests independently verify rejection for unregistered services and acceptance for web extension owners. This is a static direct-import gate, not certification of transitive dependencies or complete dependency inversion.

The SQL and transaction orchestration still present in those web modules remains unfinished work. Three direct SQLAlchemy imports remain in coordinator bulk assignment and technician queue services, outside registered ports. Broad Bindings, runtime resolution and injected model/HTTP callbacks remain distinct debt; relocating files does not remove it.

Focused results: 135 behavioral/route/module/factory tests passed across the affected features, plus six checker/helper guard tests. Before/after runtime captures retain exactly 160 tables and 546 registered routes. The registry still has 27 explicit service boundaries at this ownership step. PostgreSQL/browser/provider acceptance is separate.
