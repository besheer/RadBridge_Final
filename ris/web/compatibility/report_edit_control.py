"""Compatibility composition for report edit leases and role policy."""
from datetime import datetime, timezone
from domain.reporting.edit_policy import (
    DEFAULT_LEASE_SECONDS, EDITABLE_ROLES, VERIFY_ROLES, FINALIZE_ROLES,
    READ_ONLY_CLINICAL_ROLES, ReportEditControlError, FinalReportLocked,
    ReportRoleDenied, ReportEditLocked, ReportLeaseTokenInvalid, LeaseState,
    _token_hash, _role_code, assert_role_allowed, assert_not_final,
)
from application.services.reporting import edit_lease_service as _service
from infrastructure.adapters.reporting.edit_lease_repository import SqlAlchemyEditLeaseRepository


def _utcnow():
    return datetime.now(timezone.utc)


def get_active_lease(db, order_id):
    return _service.get_active_lease(SqlAlchemyEditLeaseRepository(db.session), order_id, _utcnow)


def assert_no_foreign_active_lease(*, db, order_id, user):
    return _service.assert_no_foreign_active_lease(repository=SqlAlchemyEditLeaseRepository(db.session),
                                                clock=_utcnow, order_id=order_id, user=user)


def acquire_or_renew_lease(*, db, order, report, user, editor_type, lease_token,
                          lease_seconds=DEFAULT_LEASE_SECONDS):
    from assignment_visit_grouping import group_members
    from assignment_distribution import mark_reading_started
    return _service.acquire_or_renew_lease(
        repository=SqlAlchemyEditLeaseRepository(db.session), clock=_utcnow,
        group_members=group_members, mark_reading_started=mark_reading_started,
        order=order, report=report, user=user, editor_type=editor_type,
        lease_token=lease_token, lease_seconds=lease_seconds,
    )


def assert_lease_owner(*, db, order, report, user, lease_token):
    return _service.assert_lease_owner(repository=SqlAlchemyEditLeaseRepository(db.session),
                                     clock=_utcnow, order=order, report=report, user=user, lease_token=lease_token)


def release_lease(*, db, order_id, user_id=None, lease_token=None):
    return _service.release_lease(repository=SqlAlchemyEditLeaseRepository(db.session),
                                order_id=order_id, user_id=user_id, lease_token=lease_token)


def clear_expired_leases(*, db):
    return _service.clear_expired_leases(repository=SqlAlchemyEditLeaseRepository(db.session), clock=_utcnow)
