from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
from dataclasses import dataclass

from sqlalchemy import text


DEFAULT_LEASE_SECONDS = 120
EDITABLE_ROLES = {"RADIOLOGIST", "TYPIST", "SUPER_ADMIN"}
VERIFY_ROLES = {"RADIOLOGIST", "SUPER_ADMIN"}
FINALIZE_ROLES = {"RADIOLOGIST", "SUPER_ADMIN"}
READ_ONLY_CLINICAL_ROLES = {"CASE_COORDINATOR"}


class ReportEditControlError(RuntimeError):
    code = "REPORT_EDIT_CONTROL_ERROR"


class FinalReportLocked(ReportEditControlError):
    code = "FINAL_REPORT_LOCKED"


class ReportRoleDenied(ReportEditControlError):
    code = "REPORT_ROLE_DENIED"


class ReportEditLocked(ReportEditControlError):
    code = "REPORT_EDIT_LOCKED"


class ReportLeaseTokenInvalid(ReportEditControlError):
    code = "REPORT_LEASE_TOKEN_INVALID"


@dataclass(frozen=True)
class LeaseState:
    order_id: int
    user_id: int
    editor_type: str
    lease_token_hash: str
    expires_at: datetime


def _utcnow():
    return datetime.now(timezone.utc)



def _token_hash(value):
    raw=str(value or "").encode("utf-8")
    return hashlib.sha256(raw).hexdigest()

def _role_code(user):
    role = getattr(user, "role", None)
    return str(getattr(role, "code", "") or "").strip().upper()


def assert_role_allowed(user, action):
    role = _role_code(user)
    action = str(action or "").strip().upper()

    if action == "VERIFIED":
        action = "VERIFY"
    elif action == "FINAL":
        action = "FINALIZE"

    if action == "DRAFT":
        allowed = EDITABLE_ROLES
    elif action == "VERIFY":
        allowed = VERIFY_ROLES
    elif action == "FINALIZE":
        allowed = FINALIZE_ROLES
    else:
        raise ReportRoleDenied("REPORT_ROLE_DENIED")

    if role not in allowed:
        raise ReportRoleDenied("REPORT_ROLE_DENIED")

    return role


def assert_not_final(report):
    if str(getattr(report, "status", "") or "").upper() == "FINAL":
        raise FinalReportLocked("FINAL_REPORT_LOCKED")


def get_active_lease(db, order_id):
    row = db.session.execute(
        text("""
            SELECT
                order_id,
                user_id,
                editor_type,
                lease_token_hash,
                expires_at
            FROM report_edit_lease
            WHERE order_id = :order_id
        """),
        {"order_id": int(order_id)},
    ).mappings().first()

    if not row:
        return None

    expires_at = row["expires_at"]

    if expires_at is not None:
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)

        if expires_at <= _utcnow():
            return None

    return LeaseState(
        order_id=int(row["order_id"]),
        user_id=int(row["user_id"]),
        editor_type=str(row["editor_type"] or ""),
        lease_token_hash=str(row["lease_token_hash"] or ""),
        expires_at=expires_at,
    )



def assert_no_foreign_active_lease(*, db, order_id, user):
    lease=get_active_lease(
        db,
        order_id,
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
    db,
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

    now = _utcnow()
    expires = now + timedelta(seconds=int(lease_seconds))

    db.session.execute(
        text("""
            SELECT id
            FROM report
            WHERE id = :report_id
            FOR UPDATE
        """),
        {"report_id": int(report.id)},
    )

    current = db.session.execute(
        text("""
            SELECT
                user_id,
                lease_token_hash,
                expires_at
            FROM report_edit_lease
            WHERE order_id = :order_id
            FOR UPDATE
        """),
        {"order_id": int(order.id)},
    ).mappings().first()

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

    db.session.execute(
        text("""
            INSERT INTO report_edit_lease (
                order_id,
                report_id,
                user_id,
                editor_type,
                lease_token_hash,
                acquired_at,
                renewed_at,
                expires_at
            )
            VALUES (
                :order_id,
                :report_id,
                :user_id,
                :editor_type,
                :lease_token_hash,
                :now,
                :now,
                :expires
            )
            ON CONFLICT (order_id)
            DO UPDATE SET
                report_id = EXCLUDED.report_id,
                user_id = EXCLUDED.user_id,
                editor_type = EXCLUDED.editor_type,
                lease_token_hash = EXCLUDED.lease_token_hash,
                renewed_at = EXCLUDED.renewed_at,
                expires_at = EXCLUDED.expires_at
        """),
        {
            "order_id": int(order.id),
            "report_id": int(report.id),
            "user_id": int(user.id),
            "editor_type": editor_type,
            "lease_token_hash": lease_token_hash,
            "now": now,
            "expires": expires,
        },
    )

    return LeaseState(
        order_id=int(order.id),
        user_id=int(user.id),
        editor_type=editor_type,
        lease_token_hash=lease_token_hash,
        expires_at=expires,
    )


def assert_lease_owner(*, db, order, report, user, lease_token):
    assert_not_final(report)
    assert_role_allowed(user, "DRAFT")

    lease = get_active_lease(db, order.id)

    if lease is None:
        raise ReportEditLocked("REPORT_EDIT_LOCKED")

    if (
        int(lease.user_id) != int(user.id)
        or str(lease.lease_token_hash) != _token_hash(lease_token)
    ):
        raise ReportEditLocked("REPORT_EDIT_LOCKED")

    return lease


def release_lease(*, db, order_id, user_id=None, lease_token=None):
    sql = """
        DELETE FROM report_edit_lease
        WHERE order_id = :order_id
    """
    params = {"order_id": int(order_id)}

    if user_id is not None:
        sql += " AND user_id = :user_id"
        params["user_id"] = int(user_id)

    if lease_token is not None:
        sql += " AND lease_token_hash = :lease_token_hash"
        params["lease_token_hash"] = _token_hash(lease_token)

    result = db.session.execute(text(sql), params)
    return int(result.rowcount or 0)


def clear_expired_leases(*, db):
    result = db.session.execute(
        text("""
            DELETE FROM report_edit_lease
            WHERE expires_at <= :now
        """),
        {"now": _utcnow()},
    )
    return int(result.rowcount or 0)
