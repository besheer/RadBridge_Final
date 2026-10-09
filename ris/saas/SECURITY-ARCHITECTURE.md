# RadBridge v5.28 Secure Multi-Tenant Foundation

## Isolation decision
RadBridge uses **one isolated application stack per customer** rather than adding `tenant_id`
to every clinical table.

Each tenant receives:
- dedicated PostgreSQL database and Docker volume;
- dedicated Orthanc/PACS database and credentials;
- dedicated reports, attachments, uploads and backup volumes;
- dedicated private Docker network;
- independent application secret and database/PACS passwords;
- independent public hostname and local application port.

This deliberately favors patient-data isolation over the lower infrastructure cost of a shared
clinical database.

## Why this is safer for the current codebase
The existing RIS was designed as a single-organization application. Retrofitting a tenant column
into hundreds of queries creates a high risk that one missed filter exposes another organization's
patients. Separate databases make that class of query bug unable to cross customer boundaries.

## Required production controls
1. Put every RIS hostname behind a TLS reverse proxy/WAF. Never expose port 8000 publicly.
2. Keep PostgreSQL un-published. It exists only on `tenant_private`.
3. Do not publish the Orthanc HTTP UI directly. If required, expose it through authenticated TLS.
4. DICOM port should be restricted by firewall/VPN to known modality/site IPs.
5. Store tenant `.env` files as root-only secrets; for larger deployments migrate secrets to
   Docker Secrets/Vault/KMS.
6. Encrypt server disks and off-site backups. Keep backup encryption keys separate.
7. Use MFA/SSO for the future SaaS control plane and privileged customer administrators.
8. Central platform administrators must not automatically gain access to clinical databases.
9. Log provisioning, backup, restore, suspend and delete operations in a separate control-plane audit log.
10. Test backup restore for each release before declaring it production-ready.

## SaaS control plane (next layer)
A separate control-plane service should contain only:
tenant id, company name, hostname, subscription/plan, status, quota, deployment reference,
billing metadata and non-clinical audit events.

Do **not** put patient records, reports, PACS credentials, clinical attachments, or clinical DB
passwords in the control-plane database.

## Tenant lifecycle
PROVISIONING -> ACTIVE -> SUSPENDED -> ARCHIVED -> DELETION_PENDING -> DELETED

Deletion should require re-authentication + MFA + typed tenant name + delay/approval, followed by
cryptographic/volume deletion according to the retention policy.
