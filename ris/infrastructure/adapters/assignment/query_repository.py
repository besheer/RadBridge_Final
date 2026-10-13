"""Read-only SQLAlchemy adapter; session and models are supplied by composition."""
from sqlalchemy import func


class SqlAlchemyAssignmentQueryRepository:
    def __init__(self, *, session, Policy, Profile, Assignment, Order, Report):
        self.session = session
        self.Policy = Policy
        self.Profile = Profile
        self.Assignment = Assignment
        self.Order = Order
        self.Report = Report

    def policy_record(self):
        return self.session.query(self.Policy).filter_by(id=1).first()

    def profile_capacity(self, doctor_id):
        row = self.session.query(self.Profile).filter_by(user_id=doctor_id).first()
        return row.max_active_cases if row is not None else None

    def active_case_count(self, doctor_id):
        a, o, r = self.Assignment, self.Order, self.Report
        return (self.session.query(a)
                .join(o, o.id == a.order_id)
                .outerjoin(r, r.order_id == o.id)
                .filter(a.doctor_user_id == doctor_id,
                        a.active.is_(True),
                        func.upper(o.status).notin_(['FINAL', 'CANCELLED']),
                        func.upper(func.coalesce(r.status, '')).notin_(['VERIFIED', 'FINAL']))
                .count())
