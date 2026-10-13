"""Compatibility composition for the legacy report writer signature."""
from application.services.reporting.commit_errors import (
    TransactionalReportCommitError, ReportCommitConflict, ReportCommitDuplicate,
)
from application.services.reporting.report_commit_service import commit_report_version as _commit
from infrastructure.adapters.reporting.commit_repository import SqlAlchemyReportCommitRepository
from infrastructure.adapters.reporting.artifact_store import LocalReportArtifactStore
from infrastructure.adapters.reporting.report_commit_core import sha256_file

def commit_report_version(
    *,
    db,
    Report,
    ReportVersion,
    report_root,
    order,
    patient,
    user,
    editor_type,
    requested_status,
    source_file,
    base_version_no,
    commit_id,
    findings="",
    impression="",
    radiologist="",
    change_summary="",
):
    return _commit(
        repository=SqlAlchemyReportCommitRepository(db.session, Report, ReportVersion),
        artifacts=LocalReportArtifactStore(report_root, sha256_file),
        order=order, patient=patient, user=user, editor_type=editor_type,
        requested_status=requested_status, source_file=source_file,
        base_version_no=base_version_no, commit_id=commit_id, findings=findings,
        impression=impression, radiologist=radiologist, change_summary=change_summary,
    )
