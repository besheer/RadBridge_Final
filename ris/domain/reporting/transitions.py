"""
RadBridge Clinical Report State Transition Core.

CONTENT SAVE:
    creates new DRAFT version.

VERIFY:
    changes the newest DRAFT version to VERIFIED.
    DOES NOT create another content version.

FINALIZE:
    locks the newest VERIFIED version.
    DOES NOT create another content version.
    Version remains VERIFIED.

Clinical authority:
    newest VERIFIED version only.
"""

from datetime import datetime


class ReportStateError(Exception):
    code = "REPORT_STATE_ERROR"


class VerifyConflict(ReportStateError):
    code = "REPORT_VERIFY_CONFLICT"


class FinalizeConflict(ReportStateError):
    code = "REPORT_FINALIZE_CONFLICT"


class FinalReportLocked(ReportStateError):
    code = "FINAL_REPORT_LOCKED"


def normalize_status(value):
    return str(value or "").strip().upper()


def authoritative_verified(versions):
    """
    Return newest VERIFIED version.

    A newer DRAFT does not replace a previously
    VERIFIED authoritative report.
    """

    verified = [
        row
        for row in (versions or [])
        if normalize_status(
            getattr(row, "status", None)
            if not isinstance(row, dict)
            else row.get("status")
        ) == "VERIFIED"
    ]

    if not verified:
        return None

    def version_no(row):
        if isinstance(row, dict):
            return int(row.get("version_no") or 0)

        return int(
            getattr(row, "version_no", 0) or 0
        )

    return max(
        verified,
        key=version_no,
    )


def assert_latest_version(
    *,
    target_version_no,
    latest_version_no,
):
    if int(target_version_no) != int(
        latest_version_no
    ):
        raise VerifyConflict(
            "ONLY_LATEST_VERSION_CAN_BE_VERIFIED"
        )

    return True


def assert_verify_allowed(
    *,
    version_status,
    finalized_at=None,
):
    status = normalize_status(
        version_status
    )

    if finalized_at is not None:
        raise FinalReportLocked(
            "FINALIZED_VERSION_IS_LOCKED"
        )

    if status == "VERIFIED":
        raise VerifyConflict(
            "VERSION_ALREADY_VERIFIED"
        )

    if status != "DRAFT":
        raise VerifyConflict(
            "ONLY_DRAFT_CAN_BE_VERIFIED"
        )

    return True


def verify_version(
    *,
    version,
    latest_version_no,
    user_id,
    verified_at=None,
):
    assert_latest_version(
        target_version_no=version.version_no,
        latest_version_no=latest_version_no,
    )

    assert_verify_allowed(
        version_status=version.status,
        finalized_at=getattr(
            version,
            "finalized_at",
            None,
        ),
    )

    when = verified_at or datetime.utcnow()

    version.status = "VERIFIED"
    version.verified_by_user_id = user_id
    version.verified_at = when

    return version


def assert_finalize_allowed(
    *,
    version_status,
    finalized_at=None,
):
    status = normalize_status(
        version_status
    )

    if finalized_at is not None:
        raise FinalizeConflict(
            "VERSION_ALREADY_FINALIZED"
        )

    if status != "VERIFIED":
        raise FinalizeConflict(
            "LATEST_VERSION_NOT_VERIFIED"
        )

    return True


def finalize_version(
    *,
    version,
    latest_version_no,
    user_id,
    finalized_at=None,
):
    if int(version.version_no) != int(
        latest_version_no
    ):
        raise FinalizeConflict(
            "ONLY_LATEST_VERSION_CAN_BE_FINALIZED"
        )

    assert_finalize_allowed(
        version_status=version.status,
        finalized_at=getattr(
            version,
            "finalized_at",
            None,
        ),
    )

    when = finalized_at or datetime.utcnow()

    # IMPORTANT:
    # status remains VERIFIED.
    version.finalized_by_user_id = user_id
    version.finalized_at = when

    return version


def assert_content_edit_allowed(
    *,
    latest_version,
):
    """
    After finalized_at is set, that clinical lifecycle
    is locked.

    Any further correction must use a future
    Amendment/Addendum workflow.
    """

    if latest_version is None:
        return True

    if getattr(
        latest_version,
        "finalized_at",
        None,
    ) is not None:
        raise FinalReportLocked(
            "FINAL_REPORT_REQUIRES_ADDENDUM"
        )

    return True
