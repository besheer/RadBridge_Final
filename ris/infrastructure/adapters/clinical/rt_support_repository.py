"""SQL ownership for RT support records and course-state evidence."""
from infrastructure.adapters.clinical.rt_session_repository import SqlAlchemyRTSessionRepository


class SqlAlchemyRTSupportRepository(SqlAlchemyRTSessionRepository):
    def __init__(self, session, Course, Plan, Fraction, Device, Note, Consumable):
        super().__init__(session,Course,Plan,Fraction,Device)
        self.Note,self.Consumable=Note,Consumable

    def started_fraction(self, course_id):
        return self.session.query(self.Fraction).filter_by(course_id=course_id,status='STARTED').first()

    def completed_count(self, course_id):
        return self.session.query(self.Fraction).filter_by(course_id=course_id,status='COMPLETED').count()

    def create_note(self, **values): return self.Note(**values)
    def create_consumable(self, **values): return self.Consumable(**values)
