"""Insurance decision authority and the shared outbound Worklist gate."""
from flask import abort


def require_actor(order):
    from application.legacy_runtime import resolve_runtime as _rb_runtime; m = _rb_runtime()
    user = m.current_user()
    if not user or not user.active:
        abort(403)
    if not (m.has_perm('orders.create') or m.has_perm('contracts.manage')):
        abort(403)
    role = user.role
    if role and (role.code == 'SUPER_ADMIN' or '*' in role.permissions()):
        return
    if not user.branch_id or user.branch_id != order.branch_id:
        abort(403)


def approval_blocker(order):
    from application.legacy_runtime import resolve_runtime as _rb_runtime; m = _rb_runtime()
    required = bool(getattr(getattr(order, 'contract', None), 'approval_required', False))
    row = m.InsuranceApprovalRequest.query.filter_by(order_id=order.id).order_by(
        m.InsuranceApprovalRequest.id.desc()).first()
    if row is None:
        if not required:
            return ''
    elif row.status == 'APPROVED' and (row.approval_no or '').strip():
        return ''
    elif row.status == 'NOT_REQUIRED' and not required:
        return ''
    return ('Insurance approval is incomplete. An approved decision with an approval '
            'reference is required before sending Worklist. / موافقة التأمين غير مكتملة؛ '
            'يلزم تسجيل موافقة مع رقمها قبل التحويل إلى أمر شغل وإرسال Worklist.')


def assert_approval_ready(order):
    blocker = approval_blocker(order)
    if blocker:
        raise ValueError(blocker)
