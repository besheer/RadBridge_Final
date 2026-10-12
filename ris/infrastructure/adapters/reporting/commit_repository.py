"""SQLAlchemy report row/version operations; never commits a caller's transaction."""
from sqlalchemy.exc import IntegrityError


class SqlAlchemyReportCommitRepository:
    integrity_error = IntegrityError

    def __init__(self, session, Report, ReportVersion):
        self.session, self.Report, self.ReportVersion = session, Report, ReportVersion

    def lock_report(self, report_id):
        return self.session.query(self.Report).filter(self.Report.id == report_id).with_for_update().one()

    def find_commit(self, report_id, commit_id):
        return self.session.query(self.ReportVersion).filter_by(report_id=report_id, commit_id=commit_id).first()

    def latest_version(self, report_id):
        return self.session.query(self.ReportVersion).filter_by(report_id=report_id).order_by(self.ReportVersion.version_no.desc()).first()

    def version_hashes(self, report_id):
        return [str(x.sha256 or '') for x in self.session.query(self.ReportVersion).filter_by(report_id=report_id).all()]

    def create_version(self, **values):
        return self.ReportVersion(**values)

    def add(self, version):
        self.session.add(version)

    def flush(self):
        self.session.flush()

    def rollback(self):
        self.session.rollback()
