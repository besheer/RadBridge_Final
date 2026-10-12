"""Insurance authorization and compatibility composition for outbound gates."""
from flask import abort
from application.services.registration.insurance_readiness import InsuranceReadiness
from infrastructure.adapters.registration.insurance_repository import SqlAlchemyInsuranceRepository

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


def _readiness():
    from application.legacy_runtime import resolve_runtime
    m=resolve_runtime()
    return InsuranceReadiness(SqlAlchemyInsuranceRepository(m.db.session,m.InsuranceApprovalRequest))

def approval_blocker(order):
    return _readiness().blocker(order)

def assert_approval_ready(order):
    blocker=approval_blocker(order)
    if blocker:raise ValueError(blocker)
