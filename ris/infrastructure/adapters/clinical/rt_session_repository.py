"""SQL ownership for scoped manual RT session records."""


class SqlAlchemyRTSessionRepository:
    def __init__(self, session, Course, Plan, Fraction, Device):
        self.session,self.Course,self.Plan,self.Fraction,self.Device=session,Course,Plan,Fraction,Device

    def lock_course(self, course_id):
        return self.session.query(self.Course).filter_by(id=course_id).populate_existing().with_for_update().first()

    def fraction(self, fraction_id): return self.session.get(self.Fraction,fraction_id)

    def lock_fraction(self, fraction_id):
        return self.session.query(self.Fraction).filter_by(id=fraction_id).populate_existing().with_for_update().first()

    def device(self, device_id): return self.session.get(self.Device,device_id)

    def current_plan(self, course_id):
        return self.session.query(self.Plan).filter_by(course_id=course_id,status='ACTIVE').first()

    def previous_attempt(self, course_id, number):
        M=self.Fraction
        return self.session.query(M).filter_by(course_id=course_id,number=number).order_by(M.attempt.desc()).first()

    def create_fraction(self, **values): return self.Fraction(**values)
    def add(self, row): self.session.add(row)
    def flush(self): self.session.flush()
