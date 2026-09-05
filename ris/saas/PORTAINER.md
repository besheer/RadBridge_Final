# Portainer deployment model

Create one Stack per customer:
`radbridge_<tenant-id>`.

Use `saas/docker-compose.tenant.yml` as the stack definition and copy the tenant's generated
environment values into Portainer's Environment variables/secrets.

Recommended labels:
- tenant id
- environment (production/staging)
- owner
- backup policy

Never place multiple customers in the same PostgreSQL database or shared attachment/report volume
with this v5.28 architecture.

For Internet service, terminate HTTPS at a reverse proxy and route:
`customer1.radbridges.com -> 127.0.0.1:<tenant local port>`
`customer2.radbridges.com -> 127.0.0.1:<tenant local port>`
