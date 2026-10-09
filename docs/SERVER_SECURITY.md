# Server security and managed access 1.0

The dashboard is `/admin/security`. Only active SUPER_ADMIN accounts can access
the page, including direct routes. Wildcard permissions on another role do not
grant host security administration. Writes require CSRF, the administrator's
current password, and an audited reason. Passwords and client private VPN keys
are never recorded in audit details.

## Data boundaries

The root-only collector reads SSH and sudo journal records, UFW block events,
the dedicated minimal Nginx security log, and LOGIN/LOGIN_FAILED audit records.
It stores a separate security SQLite database and sanitized status JSON, exposed
read-only to RIS. The application receives no Docker socket, host log mount,
host command execution, or WireGuard server private key. The collector is a
systemd oneshot timer, every minute, with a persistent journal cursor and
deduplicated event identifiers. Data is retained for 30 days. SSH/sudo/kernel
start with seven days of available journal; HTTP observations begin when the
minimal security log is installed. Existing login audit events are backfilled.

HTTP 401/403/404/429/5xx are rejected/error requests, not proof of an attack or
even an authentication attempt. Sudo events do not capture every command typed
inside a root shell. This is visibility and access hardening, not a forensic
attestation that the server is uncompromised. Collector errors and stale data
must be displayed, not converted to zero attempts. Times are UTC.

Nginx overwrites X-Forwarded-For, and only the exact configured proxy addresses
may supply it to the application. Header chains and malformed values are not
trusted. Existing generic audit, attributed audit, and failed login audit use
the same normalized client address. No original URI, query, clinical identifier,
cookie, password or authorization header is recorded in the HTTP security log.

## Country policy

Local DB-IP Lite CSV is checked against the provider's published CSV checksum,
converted into an indexed IPv4/IPv6 SQLite database, and mounted read-only.
CC BY 4.0 attribution appears on the page. No client address is sent to a lookup
API. The current dataset must be refreshed within 90 days; the page shows its
release date. Activation rejects missing/stale data. A runtime dataset failure
suspends the country restriction rather than silently causing a site outage;
this must be treated as an operational warning.

Policy modes: disabled, allow selected countries only, deny selected countries.
Unknown/private addresses have an explicit allow/deny choice. Policies are
immutable audit snapshots with a version check and PostgreSQL advisory lock.
The current administrator's normalized source address is a visible recovery
exception. Loopback service requests are preserved. The managed VPN network is
an exception only when the host controller is fresh and WireGuard is ready.

The Nginx country auth gate protects normal public content. Existing imaging
and reporting auth gates retain their original authentication and incorporate
the application country guard. HTTPS redirects, ACME challenges and the empty
service-worker-disable response remain control/redirect exceptions. The country
policy concerns HTTP site access, not the SSH/UDP handshake ports. It is not a
replacement for authentication, and VPNs can change apparent country.

Emergency recovery from an SSH root session, if an administrator's ISP changes:
use the existing administrator credentials through an SSH tunnel to localhost
and disable the policy from the dashboard. Do not mutate patient data or delete
audit history. A direct loopback request is deliberately permitted.

## Managed WireGuard

Interface: wg-radbridge. UDP endpoint: 198.244.185.119:51820.
Tunnel network: 10.77.240.0/24, server 10.77.240.1. Server routes are checked
before installation. Each client has a distinct /32, a unique public key and an
active RadBridge owner. At most five active devices per owner. Addresses are
not reused automatically; this first pool provides 253 lifetime allocations.
Expanding or changing the network requires a separate reviewed host change.

Client private keys are generated using X25519 only for the one-time response,
with a configuration download and QR. They are never stored in DB/session/log.
Lost configurations must be revoked and replaced. Only public keys and assigned
addresses enter audited desired state. The root controller independently
validates keys, addresses and duplicate allocation before wg syncconf, updates
the persistent root-only configuration, and displays applied peer/handshake
state. Revocation and user deactivation are applied within the one-minute
collector interval; stale/failed synchronization is visible. No per-device peer
configuration is accepted from arbitrary shell text in the web application.

Clients route only 10.77.240.1/32 through the tunnel. A VPN-only DNS resolver maps
rispacs.radbridges.com to 10.77.240.1, retaining the normal TLS hostname. Other DNS
queries use the configured upstream resolver. The VPN does not provide Internet
routing, SSH, database access, or lateral access to Docker/MPLS networks. Owned
INPUT and FORWARD/DOCKER-USER rules restrict it to tunnel DNS and HTTP/HTTPS.
RadBridge account authentication, role, branch and clinical scope still apply.

The Ubuntu WireGuard AppArmor profiles remain enabled. Firewall setup is a
separate root-only systemd service required before wg-quick, rather than a Python
PostUp hook. Temporary controller configuration files stay inside /etc/wireguard
with mode 0600 and valid interface-length basenames; no profile is weakened.

## SSH protection and operations

Fail2ban protects SSH ports 22 and 2238: eight failures within ten minutes,
one-hour temporary ban. The current administrative source is explicitly exempt.
Existing password login for radbridgs and key login for root are preserved.
No host reboot or broad package upgrade is part of this feature. The initial
audit found a pending reboot and cached upgrades; schedule those separately.

Do not publish reports asserting guaranteed intrusion prevention. Validate an
actual client handshake, private DNS, login over the tunnel, and peer withdrawal,
plus source tests, PostgreSQL UAT, mobile/desktop rendering and cleanup.
