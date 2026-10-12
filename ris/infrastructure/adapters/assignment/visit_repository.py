"""Visit evidence and advisory locking with explicit sessions and models."""
from sqlalchemy import text
from infrastructure.adapters.assignment.transaction_repository import SqlAlchemyAssignmentRepository


class SqlAlchemyVisitRepository(SqlAlchemyAssignmentRepository):
    def __init__(self, *, Visit, External, Appointment, Profile, **models):
        super().__init__(**models)
        self.Visit, self.External, self.Appointment, self.Profile = Visit, External, Appointment, Profile

    def new_visit(self, visit_id, patient_id, branch_id, visit_date):
        row = self.Visit(id=visit_id, patient_id=patient_id, branch_id=branch_id, visit_date=visit_date)
        self.session.add(row)
        self.session.flush()
        return row.id

    def find_visit(self, visit_id):
        return self.session.query(self.Visit).filter_by(id=visit_id).first()

    def lock_visit(self, visit):
        if self.session.get_bind().dialect.name == 'postgresql':
            self.session.execute(text('SELECT pg_advisory_xact_lock(20261003, :id)'), {'id': visit.sequence_id})

    def visit_orders(self, visit_id, lock=False):
        query = self.session.query(self.Order).filter_by(assignment_visit_id=visit_id).order_by(self.Order.id).populate_existing()
        if lock:
            query = query.with_for_update()
        return query.all()

    def source_of(self, order_id):
        row = self.session.query(self.External).filter_by(order_id=order_id).first()
        return ('EXTERNAL', row.center_id) if row else ('INTERNAL', None)

    def open_booking(self, visit_id):
        return (self.session.query(self.Appointment).filter_by(assignment_visit_id=visit_id)
                .filter(self.Appointment.order_id.is_(None), self.Appointment.status.notin_(['CANCELLED', 'NO_SHOW'])).first())

    def latest_pending_offer(self, order_id):
        return (self.session.query(self.Offer).filter_by(order_id=order_id, status='PENDING')
                .order_by(self.Offer.id.desc()).first())

    def doctor_profile(self, user_id):
        return self.session.query(self.Profile).filter_by(user_id=user_id).first()

    def get_order(self, order_id):
        return self.session.get(self.Order, order_id)
