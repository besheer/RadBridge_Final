"""Manual RT plan SQL locks, evidence and persisted versions."""
from sqlalchemy import func


class SqlAlchemyRTPlanRepository:
    def __init__(self, session, Course, Plan, Fraction, Attachment):
        self.session,self.Course,self.Plan,self.Fraction,self.Attachment=session,Course,Plan,Fraction,Attachment

    def lock_course(self, course_id):
        return self.session.query(self.Course).filter_by(id=course_id).populate_existing().with_for_update().first()

    def started_fraction(self, course_id):
        return self.session.query(self.Fraction).filter_by(course_id=course_id,status='STARTED').first()

    def latest_delivered_fraction(self, course_id):
        M=self.Fraction
        return self.session.query(M).filter_by(course_id=course_id).filter(M.status.in_(['STARTED','COMPLETED'])).order_by(M.number.desc()).first()

    def attachment(self, attachment_id): return self.session.get(self.Attachment,attachment_id)

    def current_plan(self, course_id):
        return self.session.query(self.Plan).filter_by(course_id=course_id,status='ACTIVE').first()

    def maximum_revision(self, course_id):
        return self.session.query(func.max(self.Plan.revision)).filter_by(course_id=course_id).scalar()

    def create_plan(self, **values): return self.Plan(**values)
    def add(self, row): self.session.add(row)
    def flush(self): self.session.flush()
