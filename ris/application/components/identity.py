"""Runtime-bound application.components.identity; dependencies are supplied at composition.

Legacy behavior is preserved; new policies belong in the independent domain layer.
"""

def install_0108(_rb):
    def current_user():
        uid = _rb.session.get('uid')
        return _rb.User.query.get(uid) if uid else None
    return current_user


def install_0109(_rb):
    def has_perm(perm):
        u = _rb.current_user()
        if not u or not u.active:
            return False

        if u.role and u.role.code == 'SUPER_ADMIN':
            return True

        from user_access_policy import NO_REPORT_EDIT
        if u.role and u.role.code in NO_REPORT_EDIT and perm=='reports.edit':return False
        perms = u.role.permissions() if u.role else []
        if u.role and u.role.code == 'RECEPTION' and perm in ('payments.create','cashier.workstation'):
            from collection_policy import reception_collection_allowed
            return ('*' in perms or 'payments.create' in perms) and reception_collection_allowed(u)
        return '*' in perms or perm in perms
    return has_perm


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


def install_0244(_rb):
    def get_user_profile(user=None):
        user=user or _rb.current_user()
        if not user:return None
        row=_rb.UserProfile.query.filter_by(user_id=user.id).first()
        if not row:
            row=_rb.UserProfile(user_id=user.id,department=(user.role.name if user.role else ''))
            _rb.db.session.add(row);_rb.db.session.flush()
        return row
    return get_user_profile


def install_0245(_rb):
    def user_profile_settings(profile):
        try:
            data=_rb.json.loads(profile.settings_json or '{}')
            return data if isinstance(data,dict) else {}
        except Exception:
            return {}
    return user_profile_settings


def install_0272(_rb):
    def verify_current_user_password(password):
        u=_rb.current_user()
        return bool(u and u.active and password and _rb.check_password_hash(u.password_hash,password))
    return verify_current_user_password


def install_0606(_rb):
    def correction_execution_user_has_perm(
        user,
        permission='correction.execute',
    ):
        if not user or not getattr(user,'role',None):
            return False

        try:
            permissions=set(user.role.permissions())
        except Exception:
            return False

        return (
            '*' in permissions
            or permission in permissions
        )
    return correction_execution_user_has_perm
