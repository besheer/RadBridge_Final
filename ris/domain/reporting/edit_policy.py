"""Pure report editing role, FINAL and lease token policy."""
from datetime import datetime
import hashlib
from dataclasses import dataclass

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
