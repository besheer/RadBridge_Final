"""Runtime-bound web.components.identity; dependencies are supplied at composition.

Legacy behavior is preserved; new policies belong in the independent domain layer.
"""

def install_0108(_rb):
    def current_user():
        uid = _rb.session.get('uid')
        return _rb.User.query.get(uid) if uid else None
    return current_user


def install_0110(_rb):
    def login_required(fn):
        @_rb.wraps(fn)
        def w(*a, **kw):
            u=_rb.current_user()
            if not u or not u.active: return _rb.redirect(_rb.url_for('login', next=_rb.request.path))
            return fn(*a, **kw)
        return w
    return login_required


def install_0112(_rb):
    def _security_audit_ip():
        from security_dashboard import client_ip
        ip=client_ip(_rb.request, _rb.app.config.get('SECURITY_TRUSTED_PROXIES') or _rb.os.environ.get('SECURITY_TRUSTED_PROXIES',''))
        return str(ip or '')
    return _security_audit_ip


def install_0146(_rb):
    def _safe_login_next(value):
        # A login link may return to a local page, never to another site.
        target = str(value or '').strip()
        if (target.startswith('/') and not target.startswith('//')
                and '\\' not in target
                and not any(ord(ch) < 32 or ord(ch) == 127 for ch in target)):
            return target
        return _rb.url_for('dashboard')
    return _safe_login_next

