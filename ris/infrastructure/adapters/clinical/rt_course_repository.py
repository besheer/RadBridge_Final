"""Explicit SQL ownership for manual RT course/PET-link records."""


class SqlAlchemyRTCourseRepository:
    def __init__(self, session, Order, Course, PetLink):
        self.session,self.Order,self.Course,self.PetLink=session,Order,Course,PetLink

    def find_order(self, accession):
        return self.session.query(self.Order).filter_by(accession=accession).first()

    def lock_course(self, course_id):
        return self.session.query(self.Course).filter_by(id=course_id).populate_existing().with_for_update().first()

    def create_course(self, **values): return self.Course(**values)
    def create_pet_link(self, **values): return self.PetLink(**values)
    def add(self, row): self.session.add(row)
    def flush(self): self.session.flush()
