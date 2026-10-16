"""Stable report commit errors shared by services and adapters."""
class TransactionalReportCommitError(Exception):
    code = "REPORT_COMMIT_ERROR"


class ReportCommitConflict(TransactionalReportCommitError):
    code = "REPORT_VERSION_CONFLICT"


class ReportCommitDuplicate(TransactionalReportCommitError):
    code = "REPORT_VERSION_DUPLICATE"
