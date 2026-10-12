"""Revision queries and row locks with caller-owned transactions."""


class SqlAlchemyRevisionRepository:
    def __init__(self, session, Order, Revision, User):
        self.session, self.Order, self.Revision, self.User = session, Order, Revision, User

    def lock_order(self, order_id):
        return self.session.query(self.Order).filter_by(id=order_id).with_for_update().populate_existing().one()

    def lock_revision(self, revision_id):
        return self.session.query(self.Revision).filter_by(id=revision_id).with_for_update().populate_existing().one()

    def active_revision(self, order_id):
        return self.session.query(self.Revision).filter_by(active_order_id=order_id).first()

    def latest_revision(self, order_id):
        return self.session.query(self.Revision).filter_by(order_id=order_id).order_by(self.Revision.revision_no.desc()).first()

    def get_doctor(self, doctor_id):
        return self.session.get(self.User, doctor_id)

    def create_revision(self, **values):
        return self.Revision(**values)

    def add(self, row):
        self.session.add(row)

    def flush(self):
        self.session.flush()
