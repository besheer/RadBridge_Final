"""Report edit leases over explicit clock, persistence and assignment evidence."""
from datetime import timedelta, timezone
from domain.reporting.edit_policy import (
    DEFAULT_LEASE_SECONDS, LeaseState, ReportEditLocked, ReportRoleDenied,
    ReportLeaseTokenInvalid, assert_not_final, assert_role_allowed, _token_hash, _role_code,
)

def get_active_lease(repository, order_id, clock):
    row = repository.read_lease(order_id)

    if not row:
        return None

    expires_at = row["expires_at"]

    if expires_at is not None:
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)

        if expires_at <= clock():
            return None

    return LeaseState(
        order_id=int(row["order_id"]),
        user_id=int(row["user_id"]),
        editor_type=str(row["editor_type"] or ""),
        lease_token_hash=str(row["lease_token_hash"] or ""),
        expires_at=expires_at,
    )


def assert_no_foreign_active_lease(*, repository, order_id, user, clock):
    lease=get_active_lease(
        repository,
        order_id, clock,
    )

    if lease is None:
        return None

    if int(lease.user_id) != int(user.id):
        raise ReportEditLocked(
            "REPORT_EDIT_LOCKED"
        )

    return lease


def acquire_or_renew_lease(
    *,
    repository,
    clock,
    group_members,
    mark_reading_started,
    order,
    report,
    user,
    editor_type,
    lease_token,
    lease_seconds=DEFAULT_LEASE_SECONDS,
):
    assert_not_final(report)
    assert_role_allowed(user, "DRAFT")

    editor_type = str(editor_type or "").strip().upper()
    lease_token = str(lease_token or "").strip()

    if not lease_token:
        raise ReportLeaseTokenInvalid("REPORT_LEASE_TOKEN_INVALID")

    lease_token_hash = _token_hash(lease_token)

    now = clock()
    expires = now + timedelta(seconds=int(lease_seconds))
    group_members(order, lock=True)
    owner = repository.lock_order_owner(order.id)
    if _role_code(user) in ('RADIOLOGIST', 'DOCTOR') and owner != int(user.id):
        raise ReportRoleDenied('REPORT_CASE_NOT_ASSIGNED')

    repository.lock_report(report.id)
    current = repository.read_locked_lease(order.id)

    if current:
        current_expiry = current["expires_at"]

        if current_expiry is not None and current_expiry.tzinfo is None:
            current_expiry = current_expiry.replace(tzinfo=timezone.utc)

        active = (
            current_expiry is not None
            and current_expiry > now
        )

        same_owner = (
            int(current["user_id"]) == int(user.id)
            and str(current["lease_token_hash"] or "") == lease_token_hash
        )

        if active and not same_owner:
            raise ReportEditLocked("REPORT_EDIT_LOCKED")

    repository.upsert(dict(
        order_id=int(order.id), report_id=int(report.id), user_id=int(user.id),
        editor_type=editor_type, lease_token_hash=lease_token_hash, now=now, expires=expires,
    ))

    mark_reading_started(order.id, user.id)

    return LeaseState(
        order_id=int(order.id),
        user_id=int(user.id),
        editor_type=editor_type,
        lease_token_hash=lease_token_hash,
        expires_at=expires,
    )


def assert_lease_owner(*, repository, clock, order, report, user, lease_token):
    assert_not_final(report)
    assert_role_allowed(user, "DRAFT")

    lease = get_active_lease(repository, order.id, clock)

    if lease is None:
        raise ReportEditLocked("REPORT_EDIT_LOCKED")

    if (
        int(lease.user_id) != int(user.id)
        or str(lease.lease_token_hash) != _token_hash(lease_token)
    ):
        raise ReportEditLocked("REPORT_EDIT_LOCKED")

    return lease


def release_lease(*, repository, order_id, user_id=None, lease_token=None):
    return repository.release(order_id, user_id, _token_hash(lease_token) if lease_token is not None else None)


def clear_expired_leases(*, repository, clock):
    return repository.clear_expired(clock())
