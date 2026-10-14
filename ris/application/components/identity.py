"""Runtime-bound application.components.identity; dependencies are supplied at composition.

Legacy behavior is preserved; new policies belong in the independent domain layer.
"""

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
            return ('*' in perms or 'payments.create' in perms) and reception_collection_allowed(u,runtime=_rb)
        return '*' in perms or perm in perms
    return has_perm


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
