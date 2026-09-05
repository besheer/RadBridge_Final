RadBridge v5.29 Platform Control

Adds a separate SaaS control plane intended for:
  https://admin.radbridges.com

Capabilities:
- Platform Admin login
- Companies/Tenants list
- Add Company
- Subscription Plans
- Tenant lifecycle: PROVISIONING / ACTIVE / SUSPENDED / ARCHIVED / DELETION_PENDING
- Per-tenant provisioning ZIP for Portainer
- Platform-only audit trail
- No patient records and no clinical database credentials in the control-plane database

Security decisions:
- The Platform Admin container does NOT receive /var/run/docker.sock.
- It cannot directly browse tenant clinical databases.
- Provisioning bundles are downloaded explicitly and deployed in Portainer.
- Each tenant remains a separate DB/PACS/storage stack from v5.28.
- Session cookies are Secure/HttpOnly/SameSite=Strict and forms have CSRF tokens.
- Security headers are included.
- Platform database is on a private network.

Next production hardening before public launch:
- Put admin.radbridges.com behind HTTPS reverse proxy/WAF.
- Replace bootstrap password with SSO/MFA.
- Add rate limiting/fail2ban at reverse proxy.
- Encrypt off-site backups and rotate secrets.
