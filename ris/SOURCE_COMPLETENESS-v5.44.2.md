# Source completeness

v5.44.2 is based on the `/app` tree copied from the running v5.44.1 production container, then sanitized and stabilized.

Included:
- main Flask application
- all live Jinja templates
- static assets and Word add-in
- PACS worker and support modules
- procedure catalog and workflow engine
- migrations and operational scripts
- reporting agent source package

Excluded intentionally:
- report-files/
- attachments/
- backups/
- test-runtime/
- runtime `.env` / secret files
- private keys / certificates
- Python caches
- historical duplicate app.py backup copies

Runtime data remains mounted from the production volumes and must never be baked into the Docker image.
