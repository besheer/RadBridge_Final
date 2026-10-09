"""Privileged security views; host monitoring is read-only and separately collected."""
import base64
import io
import ipaddress
import json
import os
import re
import secrets
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from functools import wraps

from flask import abort, request, session, render_template, redirect, url_for, Response, jsonify
from werkzeug.security import check_password_hash

POLICY_ACTION = 'SECURITY_COUNTRY_POLICY'
VPN_NETWORK = ipaddress.ip_network('10.77.240.0/24')

def valid_ip(value):
    try:
        ip = ipaddress.ip_address(str(value).strip())
        return ip.ipv4_mapped if getattr(ip, 'ipv4_mapped', None) else ip
    except ValueError:
        return None

def client_ip(req, trusted):
    peer = valid_ip(req.remote_addr)
    if peer is None:
        return None
    proxies = [ipaddress.ip_network(x.strip()) for x in trusted.split(',') if x.strip()]
    if any(peer in net for net in proxies):
        # Nginx overwrites this header; a chain or malformed value is not trusted.
        raw = req.headers.get('X-Forwarded-For', '')
        if not raw and peer.is_loopback:
            return peer
        return valid_ip(raw) if ',' not in raw else None
    return peer

def root(m):
    return Path(m.app.config.get('SECURITY_DATA_DIR') or os.environ.get('SECURITY_DATA_DIR', '/app/security-data'))

def ro_db(path):
    c = sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True, timeout=3)
    c.row_factory = sqlite3.Row
    return c

def country(m, ip):
    if ip is None:
        return 'UNKNOWN'
    if not ip.is_global:
        return 'PRIVATE'
    try:
        with ro_db(root(m) / 'countries.sqlite') as c:
            key = f'{int(ip):032x}'
            row = c.execute('SELECT last,country FROM ranges WHERE version=? AND first<=? ORDER BY first DESC LIMIT 1', (ip.version, key)).fetchone()
            return row['country'] if row and key <= row['last'] else 'UNKNOWN'
    except (OSError, sqlite3.Error):
        return 'UNKNOWN'

def geo_status(m):
    try:
        with ro_db(root(m) / 'countries.sqlite') as c:
            values = dict(c.execute('SELECT key,value FROM metadata').fetchall())
        stamp = datetime.fromisoformat(values['release_date'])
        age = (datetime.utcnow() - stamp).days
        return {**values, 'ready': 0 <= age <= 90, 'age_days': age}
    except (OSError, sqlite3.Error, KeyError, ValueError):
        return {'ready': False}

def current_policy(m):
    row = m.AuditLog.query.filter_by(action=POLICY_ACTION).order_by(m.AuditLog.id.desc()).first()
    if not row:
        return {'id': 0, 'mode': 'disabled', 'countries': [], 'unknown': 'allow', 'rescue_ip': ''}
    try:
        data = json.loads(row.details)
        assert data['mode'] in ('disabled', 'allow', 'deny')
        return {**data, 'id': row.id}
    except (ValueError, KeyError, AssertionError):
        return {'id': row.id, 'mode': 'disabled', 'countries': [], 'unknown': 'allow', 'rescue_ip': '', 'invalid': True}

def policy_decision(policy, ip, code, geo_ready=True, vpn_ready=False):
    if policy['mode'] == 'disabled':
        return True, 'POLICY_DISABLED'
    if ip and ip.is_loopback:
        return True, 'LOCAL_SERVICE'
    if ip and vpn_ready and ip in VPN_NETWORK:
        return True, 'MANAGED_VPN'
    if ip and str(ip) == policy.get('rescue_ip'):
        return True, 'ADMIN_RESCUE'
    if not geo_ready:
        return True, 'GEO_DATABASE_UNAVAILABLE_POLICY_SUSPENDED'
    if code in ('UNKNOWN', 'PRIVATE'):
        return policy.get('unknown') == 'allow', 'UNKNOWN_COUNTRY'
    selected = code in policy.get('countries', [])
    allowed = selected if policy['mode'] == 'allow' else not selected
    return allowed, 'COUNTRY_ALLOWED' if allowed else 'COUNTRY_BLOCKED'

def snapshot(m):
    try:
        data = json.loads((root(m) / 'status.json').read_text())
        age = (datetime.utcnow() - datetime.fromisoformat(data['updated_at'])).total_seconds()
        return {**data, 'fresh': 0 <= age < 180, 'age_seconds': int(age)}
    except (OSError, ValueError, KeyError):
        return {'fresh': False, 'vpn': {'ready': False}, 'error': 'COLLECTOR_NOT_CONNECTED'}

def vpn_rows(m):
    creates = m.AuditLog.query.filter_by(action='SECURITY_VPN_CREATE').order_by(m.AuditLog.id).all()
    revoked = {r.entity_id for r in m.AuditLog.query.filter_by(action='SECURITY_VPN_REVOKE').all()}
    result = []
    for row in creates:
        try:
            data = json.loads(row.details)
            user = m.db.session.get(m.User, int(data['user_id']))
            data.update(id=row.id, created_at=row.created_at, enabled=str(row.id) not in revoked and bool(user and user.active), username=user.username if user else 'REMOVED_USER')
            result.append(data)
        except (ValueError, KeyError, TypeError):
            continue
    return result

def vpn_desired(m):
    return [{k: r[k] for k in ('id', 'public_key', 'address', 'enabled')} for r in vpn_rows(m)]

def register(m):
    def admin(fn):
        @wraps(fn)
        def wrapped(*args, **kwargs):
            u = m.current_user()
            if not u or not u.active:
                return redirect(url_for('login', next=request.path))
            if not u.role or u.role.code != 'SUPER_ADMIN':
                abort(403)
            return fn(*args, **kwargs)
        return wrapped

    def actor_ip():
        return client_ip(request, m.app.config.get('SECURITY_TRUSTED_PROXIES') or os.environ.get('SECURITY_TRUSTED_PROXIES', ''))

    def mutation():
        token = session.get('security_csrf', '')
        if not token or not secrets.compare_digest(token, request.form.get('csrf_token', '')):
            abort(403)
        reason = request.form.get('reason', '').strip()
        if not 5 <= len(reason) <= 300:
            abort(400, 'A reason of 5–300 characters is required.')
        if not check_password_hash(m.current_user().password_hash, request.form.get('password', '')):
            abort(403, 'Administrator password verification failed.')
        return reason

    def save_audit(action, entity_id, data):
        u = m.current_user()
        row = m.AuditLog(user_id=u.id, username=u.username, action=action, entity='server_security', entity_id=str(entity_id), details=json.dumps(data, separators=(',', ':')), ip=str(actor_ip() or ''))
        m.db.session.add(row)
        return row

    @m.app.before_request
    def country_gate():
        policy = current_policy(m)
        if policy['mode'] == 'disabled':
            return None
        ip = actor_ip()
        internal = m.app.config.get('SECURITY_INTERNAL_CLIENTS') or os.environ.get('SECURITY_INTERNAL_CLIENTS', '')
        if ip and any(ip in ipaddress.ip_network(net.strip()) for net in internal.split(',') if net.strip()):
            return None
        snap = snapshot(m)
        allowed, why = policy_decision(policy, ip, country(m, ip), geo_status(m)['ready'], bool(snap['fresh'] and snap.get('vpn', {}).get('ready')))
        if not allowed:
            return Response('Access is restricted by the site country policy. Contact your administrator for authorized VPN access.', status=403, content_type='text/plain; charset=utf-8', headers={'Cache-Control': 'no-store', 'X-RadBridge-Security-Decision': why})

    @m.app.route('/security/country-gate')
    def security_country_gate():
        return Response(status=204, headers={'Cache-Control': 'no-store'})

    @m.app.route('/admin/security')
    @admin
    def admin_security():
        session.setdefault('security_csrf', secrets.token_urlsafe(32))
        session['security_vpn_nonce'] = secrets.token_urlsafe(24)
        channel = request.args.get('channel', 'ALL').upper()
        outcome = request.args.get('outcome', 'ALL').upper()
        code = request.args.get('country', '').upper()
        ip_filter = request.args.get('ip', '').strip()
        if channel not in ('ALL', 'SSH', 'WEB', 'HTTP', 'SUDO', 'FIREWALL') or outcome not in ('ALL', 'SUCCESS', 'FAILED', 'REJECTED'):
            abort(400)
        if code and not re.fullmatch(r'[A-Z]{2}|UNKNOWN|PRIVATE', code):
            abort(400)
        if ip_filter and valid_ip(ip_filter) is None:
            abort(400)
        try:
            days = int(request.args.get('days', '7'))
            page = int(request.args.get('page', '1'))
            if days not in (1, 7, 30) or not 1 <= page <= 10000:
                raise ValueError
        except ValueError:
            abort(400)
        since = datetime.utcnow() - timedelta(days=days)
        events, groups, host_total = [], [], 0
        errors = []
        try:
            with ro_db(root(m) / 'events.sqlite') as c:
                where, args = ['timestamp>=?'], [since.isoformat(timespec='seconds')]
                for name, value in [('channel', channel), ('outcome', outcome), ('country', code), ('ip', ip_filter)]:
                    if value and value != 'ALL':
                        where.append(name + '=?'); args.append(value)
                clause = ' AND '.join(where)
                host_total = c.execute('SELECT count(*) FROM events WHERE ' + clause, args).fetchone()[0]
                events = [dict(x) for x in c.execute('SELECT timestamp,channel,outcome,ip,country,account,detail FROM events WHERE ' + clause + ' ORDER BY timestamp DESC,id DESC LIMIT 100 OFFSET ?', args + [(page-1)*100])]
                groups = [dict(x) for x in c.execute('SELECT country,count(*) total,sum(outcome="FAILED") failed,sum(outcome="SUCCESS") success FROM events WHERE timestamp>=? GROUP BY country ORDER BY total DESC LIMIT 250', [since.isoformat(timespec='seconds')])]
        except (OSError, sqlite3.Error):
            errors.append('Host event collector is unavailable; this does not mean zero attempts.')
        return render_template('server_security.html', status=snapshot(m), policy=current_policy(m), geo=geo_status(m), events=events, country_groups=groups, host_total=host_total, errors=errors, filters={'channel': channel, 'outcome': outcome, 'country': code, 'ip': ip_filter, 'days': days, 'page': page}, csrf_token=session['security_csrf'], vpn_nonce=session['security_vpn_nonce'], vpn_peers=vpn_rows(m), users=m.User.query.filter_by(active=True).order_by(m.User.username).limit(1000).all(), admin_ip=str(actor_ip() or ''))

    @m.app.route('/admin/security/country-policy', methods=['POST'])
    @admin
    def security_save_country_policy():
        reason = mutation()
        mode = request.form.get('mode', '')
        codes = sorted(set(re.split(r'[\s,;]+', request.form.get('countries', '').strip().upper())) - {''})
        unknown = request.form.get('unknown', 'allow')
        if mode not in ('disabled', 'allow', 'deny') or unknown not in ('allow', 'deny') or any(not re.fullmatch(r'[A-Z]{2}', x) for x in codes):
            abort(400)
        if mode != 'disabled' and (not codes or not geo_status(m)['ready']):
            abort(400, 'Select countries and load a current geolocation database before activation.')
        if codes and mode != 'disabled':
            with ro_db(root(m) / 'countries.sqlite') as c:
                known={row[0] for row in c.execute('SELECT DISTINCT country FROM ranges')}
            if any(code not in known for code in codes):
                abort(400, 'A country code is not present in the loaded dataset.')
        if m.db.engine.dialect.name == 'postgresql':
            m.db.session.execute(m.text("SELECT pg_advisory_xact_lock(hashtext('SECURITY_COUNTRY_POLICY'))"))
        try:
            if int(request.form.get('version', '-1')) != current_policy(m)['id']:
                abort(409)
        except ValueError:
            abort(400)
        ip = actor_ip()
        if ip is None:
            abort(400, 'A trusted administrative client address is required.')
        data = {'mode': mode, 'countries': codes, 'unknown': unknown, 'rescue_ip': str(ip), 'reason': reason, 'updated_at': datetime.utcnow().isoformat(timespec='seconds'), 'scope': 'ALL_SITE_HTTP', 'vpn_network': str(VPN_NETWORK)}
        save_audit(POLICY_ACTION, 'site', data)
        m.db.session.commit()
        return redirect(url_for('admin_security'))

    @m.app.route('/admin/security/vpn/create', methods=['POST'])
    @admin
    def security_create_vpn():
        reason = mutation()
        nonce=request.form.get('creation_nonce','')
        if not nonce or not secrets.compare_digest(nonce,session.get('security_vpn_nonce','')):
            abort(403)
        snap = snapshot(m)
        if not snap.get('fresh') or not snap.get('vpn', {}).get('ready'):
            abort(503, 'WireGuard controller is not ready.')
        try:
            uid = int(request.form.get('user_id', '0'))
        except ValueError:
            abort(400)
        user = m.db.session.get(m.User, uid)
        label = request.form.get('label', '').strip()
        if not user or not user.active or not 2 <= len(label) <= 80:
            abort(400)
        if m.db.engine.dialect.name == 'postgresql':
            m.db.session.execute(m.text("SELECT pg_advisory_xact_lock(hashtext('SECURITY_VPN_ALLOCATION'))"))
        if m.AuditLog.query.filter(m.AuditLog.action=='SECURITY_VPN_CREATE',m.AuditLog.details.contains('"request_id":"'+nonce+'"')).first():
            abort(409, 'This creation request was already used; the private key cannot be retrieved again.')
        peers = vpn_rows(m)
        if sum(p['enabled'] and p['user_id'] == uid for p in peers) >= 5:
            abort(400, 'Maximum five active devices per user.')
        used = {p['address'] for p in peers}
        address = next((str(ip) for ip in VPN_NETWORK.hosts() if str(ip) != '10.77.240.1' and str(ip) not in used), None)
        if not address:
            abort(409, 'VPN address allocation is full; no address is silently reused.')
        from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey
        from cryptography.hazmat.primitives import serialization
        key = X25519PrivateKey.generate()
        private = base64.b64encode(key.private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw, serialization.NoEncryption())).decode()
        public = base64.b64encode(key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)).decode()
        row = save_audit('SECURITY_VPN_CREATE', uid, {'user_id': uid, 'label': label, 'public_key': public, 'address': address, 'reason': reason, 'request_id':nonce})
        m.db.session.commit()
        config = f'[Interface]\nPrivateKey = {private}\nAddress = {address}/32\nDNS = 10.77.240.1\n\n[Peer]\nPublicKey = {snap["vpn"]["public_key"]}\nEndpoint = {snap["vpn"]["endpoint"]}\nAllowedIPs = 10.77.240.1/32\nPersistentKeepalive = 25\n'
        image = io.BytesIO()
        m.qrcode.make(config).save(image, format='PNG')
        # The client private key exists only in this one-time response, never DB/log/session.
        return Response(render_template('security_vpn_once.html', config=config, qr=base64.b64encode(image.getvalue()).decode(), peer_id=row.id, label=label), headers={'Cache-Control': 'no-store', 'Pragma': 'no-cache', 'Referrer-Policy': 'no-referrer'})

    @m.app.route('/admin/security/vpn/<int:peer_id>/revoke', methods=['POST'])
    @admin
    def security_revoke_vpn(peer_id):
        reason = mutation()
        peer = next((p for p in vpn_rows(m) if p['id'] == peer_id), None)
        if peer is None:
            abort(404)
        if peer['enabled']:
            save_audit('SECURITY_VPN_REVOKE', peer_id, {'reason': reason, 'public_key': peer['public_key']})
            m.db.session.commit()
        return redirect(url_for('admin_security'))

    @m.app.after_request
    def security_no_store(resp):
        if request.path.startswith('/admin/security'):
            resp.headers['Cache-Control'] = 'no-store'
            resp.headers['Referrer-Policy'] = 'no-referrer'
        return resp

    @m.app.context_processor
    def security_navigation_context():
        u=m.current_user()
        return {'can_manage_server_security': bool(u and u.active and u.role and u.role.code=='SUPER_ADMIN')}
