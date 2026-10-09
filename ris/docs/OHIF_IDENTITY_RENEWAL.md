# Viewer identity renewal

POST /api/reporting/identity/<order_id> uses the active RIS cookie and a signed
original viewer subject. An expired signature is accepted only as a binding:
login, reports.view, reporting role, subject, order, current assignment, branch
when scoped, and exact StudyInstanceUID are rechecked before issuing a token.
Existing report APIs keep their five-minute expiry and edit lease requirements.
No report status, file or version changes. Successful renewal records an audit
without the token. Responses are JSON and no-store; GET never issues credentials.

The viewer shares an in-memory identity cache between its panel and ONLYOFFICE
wrapper. Renew before reporting requests, thirty seconds before expiry. Do not
change React identity props or remount an open document. Concurrent renewals are
deduplicated. Clinical requests are never replayed. Page-close lease release
uses the cached identity, with server lease expiry as its existing fallback.
HTML failures become a readable Arabic/English session message.

Validation: 19 authorization tests, 6 Node frontend tests, 1236 full RIS tests;
221 templates compile and application import passes. Runtime/browser acceptance
is recorded separately in the deployment checkpoint. No schema migration.
