"""Branch-scoped reception collection; no automatic role grants."""
def reception_collection_allowed(user):
    from application.legacy_runtime import resolve_runtime as _rb_runtime; m = _rb_runtime()
    if not user or not user.active or not user.branch_id:return False
    branch=m.db.session.get(m.Branch,user.branch_id)
    return bool(branch and branch.active and branch.reception_collection_enabled)

def require_collection_branch(branch_id):
    from application.legacy_runtime import resolve_runtime as _rb_runtime; m = _rb_runtime()
    user=m.current_user()
    if not user or not user.active:m.abort(403)
    code=user.role.code if user.role else ''
    if code in ('RECEPTION','CASHIER'):
        if not user.branch_id or user.branch_id!=branch_id:m.abort(403)
        if code=='RECEPTION' and not reception_collection_allowed(user):m.abort(403)
