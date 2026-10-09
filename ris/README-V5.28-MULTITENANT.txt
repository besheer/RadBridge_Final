RadBridge v5.28 Secure Multi-Tenant Foundation

Architecture chosen: isolated stack per customer.

This package intentionally does NOT retrofit tenant_id into clinical tables.
Instead, every company gets its own RIS app instance, PostgreSQL DB, PACS,
reports/attachments/uploads volumes, secrets and private network.

See:
  saas/SECURITY-ARCHITECTURE.md
  saas/PORTAINER.md
  saas/new-tenant.sh
  saas/backup-tenant.sh
  saas/restore-tenant.sh

This is the safer migration path for the current single-company codebase and
preserves all v5.27.4.1 features.
