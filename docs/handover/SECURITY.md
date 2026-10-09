# Security and access operations handover

## Components and ownership

`ris/security_dashboard.py` exposes privileged security views and country-policy functions. Host authentication events and monitoring data are collected separately; a web UI cannot replace host firewall, SSH, VPN or intrusion-detection controls. The recorded host components include `radbridge-security-collector.service` and its timer, Fail2ban policies and WireGuard. Their complete operating configuration and keys are excluded from GitHub.

At RT release acceptance, the security collector returned no recorded errors and VPN readiness passed. This is a dated acceptance result, not proof that every event is fresh or that no intrusion occurred. Inspect the current collection timestamp, component health, configuration and audit events before relying on the dashboard.

## Routine review

- Check failed/successful web and SSH authentication events with a restricted operator account. Avoid exporting real identities/IP event logs into developer documentation.
- Correlate time, source, user, reason and action; a failed login alone is not proof of a successful compromise. Document findings and preserve original audit evidence.
- Review actual Fail2ban jail settings for retry counts, time windows, ban durations and exemptions. This document intentionally does not invent a universal "ban after N attempts" value.
- Verify collector freshness, SSH/firewall settings and private reverse-proxy configuration. Access logs must redact viewer bearer-capability paths.
- Verify that forwarded client IPs are accepted only through trusted proxies; source `client_ip()` rejects malformed chains rather than trusting arbitrary headers.
- Check country-data availability and freshness before changing geography rules. Record whether current policy is disabled, allow-list or deny-list, and how UNKNOWN/private/VPN addresses are handled in the implementation.

## Country and VPN policy

The owner's requested geography scope is the entire website, including doctors and branches. Do not infer an active allow/deny policy from this request or from an available screen. Read the current stored policy and inspect its effect through an authorized test path before enabling changes. Maintain an approved recovery/administrator access path.

WireGuard access for authorized users from blocked countries was requested. Provisioning, delivery of private client configuration, expiry/revocation and audit must be done through the approved current host workflow. Never publish private keys, QR codes or user tunnel configurations in this repository. A ready VPN service does not prove a particular user's tunnel is installed or allowed.

The owner still requires password SSH access for `radbridgs` at this checkpoint. Do not disable it or rotate authentication methods without validating the owner's working recovery access. Inspect live SSH settings privately; this document does not reproduce them.

## Role changes and incident response

Role grants and branch/modality/device/room scope require explicit need and auditing. Saved filters, CSV transfers and viewer URLs do not grant access. Nursing and technician accounts must not receive report editing permission. RT nursing cannot enter a plan or dose.

If a compromise is suspected, preserve evidence, identify affected identities/services, revoke relevant sessions/keys with the operating owner, and assess data exposure before restoring service. Do not delete logs, broadly prune containers or restore an old database to hide a state discrepancy. Keep incident notes and sensitive evidence in restricted storage separate from the developer repository.

These are operating review steps. No new firewall, SSH, Fail2ban, country or VPN setting was changed by the documentation upload.
