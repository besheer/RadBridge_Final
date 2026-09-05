"""
RadBridge ONLYOFFICE Unified Reporting Adapter.

ONLYOFFICE is an editor/transport only.

Rules:
- autosave -> working copy only
- explicit Save Draft -> commit_report_version()
- Verify -> latest DRAFT becomes VERIFIED
- Finalize -> same latest VERIFIED is locked
- no independent ONLYOFFICE report identity
"""

from report_transaction_writer import (
    commit_report_version,
)

from report_state_transition import (
    verify_version,
    finalize_version,
    assert_content_edit_allowed,
)


class OnlyOfficeReportBridgeError(Exception):
    code = "ONLYOFFICE_REPORT_BRIDGE_ERROR"


def latest_report_version(
    *,
    ReportVersion,
    report_id,
):
    return (
        ReportVersion.query
        .filter_by(report_id=report_id)
        .order_by(
            ReportVersion.version_no.desc()
        )
        .first()
    )


def onlyoffice_save_draft(
    *,
    db,
    Report,
    ReportVersion,
    report_root,
    order,
    patient,
    user,
    source_file,
    base_version_no,
    commit_id,
    findings="",
    impression="",
    radiologist="",
):
    """
    Explicit Save Draft.

    Autosave callbacks MUST NOT call this.
    """

    report = order.report

    if report is None:
        raise OnlyOfficeReportBridgeError(
            "REPORT_NOT_FOUND"
        )

    latest = latest_report_version(
        ReportVersion=ReportVersion,
        report_id=report.id,
    )

    assert_content_edit_allowed(
        latest_version=latest
    )

    return commit_report_version(
        db=db,
        Report=Report,
        ReportVersion=ReportVersion,
        report_root=report_root,
        order=order,
        patient=patient,
        user=user,
        editor_type="ONLYOFFICE",
        requested_status="DRAFT",
        source_file=source_file,
        base_version_no=base_version_no,
        commit_id=commit_id,
        findings=findings,
        impression=impression,
        radiologist=radiologist,
        change_summary=(
            "Saved from ONLYOFFICE "
            "through unified report writer"
        ),
    )


def verify_latest_report_version(
    *,
    db,
    Report,
    ReportVersion,
    order,
    user,
):
    """
    Verify latest DRAFT.

    No ReportVersion INSERT.
    """

    report = (
        db.session.query(Report)
        .filter(Report.id == order.report.id)
        .with_for_update()
        .one()
    )

    latest = latest_report_version(
        ReportVersion=ReportVersion,
        report_id=report.id,
    )

    if latest is None:
        raise OnlyOfficeReportBridgeError(
            "NO_REPORT_VERSION"
        )

    verify_version(
        version=latest,
        latest_version_no=latest.version_no,
        user_id=getattr(user, "id", None),
    )

    username = (
        getattr(user, "full_name", None)
        or getattr(user, "username", None)
        or "Unknown"
    )

    report.status = "VERIFIED"
    report.verified_by = username
    report.verified_at = latest.verified_at

    db.session.flush()

    return latest


def finalize_latest_report_version(
    *,
    db,
    Report,
    ReportVersion,
    order,
    user,
):
    """
    Finalize latest VERIFIED.

    No ReportVersion INSERT.
    Version status remains VERIFIED.
    """

    report = (
        db.session.query(Report)
        .filter(Report.id == order.report.id)
        .with_for_update()
        .one()
    )

    latest = latest_report_version(
        ReportVersion=ReportVersion,
        report_id=report.id,
    )

    if latest is None:
        raise OnlyOfficeReportBridgeError(
            "NO_REPORT_VERSION"
        )

    finalize_version(
        version=latest,
        latest_version_no=latest.version_no,
        user_id=getattr(user, "id", None),
    )

    username = (
        getattr(user, "full_name", None)
        or getattr(user, "username", None)
        or "Unknown"
    )

    report.status = "FINAL"
    report.finalized_by = username
    report.finalized_at = latest.finalized_at

    order.status = "FINAL"

    db.session.flush()

    return latest


# Backward-compatible aliases.
# Editor channels must use the generic names for new integrations.
onlyoffice_verify_latest = verify_latest_report_version
onlyoffice_finalize_latest = finalize_latest_report_version
