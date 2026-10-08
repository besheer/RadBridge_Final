# Report editor DOM initialization fix

The report editor placed dictation and edit-lease JavaScript in page_title. The base template renders that block before content, so the lease initializer finds no web-report-form and exits; draft saves then correctly fail the server lease guard. Dictation listeners are likewise never attached.

Move both existing initializers and the lease status element to the end of content, after the editor/upload forms and dictation controls. No JavaScript behavior or backend guard is changed. FINAL still omits the lease script; missing/wrong/foreign editor tokens cannot bypass server checks.

Canonical source: /opt/radbridge/current, resolving to the existing release checkout. The historical R8 path/service names in root AGENTS.md do not exist; current source/image/mount contract was read before this fix. This source has no bind mount into the running RIS. Dedicated fix branch; no edits in a running container and no database/PACS changes. Source version remains unchanged for this focused repair.

Regression tests use real rendered HTML to verify parsing order, real acquired-lease draft saving, missing-token denial, competing-lease denial, FINAL immutability and direct-URL foreign-case denial. Browser UAT uses disposable SQLite and synthetic data only.


Validation: original Arabic/English rendering failed DOM-order checks; fixed rendering passes. Full reference suite: 1644 passed, 2 PostgreSQL-only tests skipped on SQLite; isolated PostgreSQL run: all 7 new tests passed. Chromium browser UAT saved English and Arabic drafts and retained FINAL readonly behavior, with no page errors/failed requests/unexpected error responses. Existing telephony 403 is expected role denial. Arabic narrow layout is a documented pre-existing defect: 390px viewport / 670px body both before and after initializer placement; not changed by this repair. Browser tests use a private disposable PostgreSQL database, fake RIS cases and mocked PACS; no production writes or sends.

Deployment is not performed by source validation or this commit. New persistent image/service replacement requires the root AGENTS explicit approval boundary. Existing production image remains the prior user CSV release until authorized deployment.
