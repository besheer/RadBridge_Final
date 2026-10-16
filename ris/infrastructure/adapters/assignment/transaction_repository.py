"""Assignment row-lock adapter; caller owns transaction commit and rollback."""
from application.services.assignment.assignment_transaction import CaseAssignmentServiceError


class SqlAlchemyAssignmentRepository:
    def __init__(self, *, session, Order, User, Assignment, Report=None, Offer=None):
        self.session, self.Order, self.User = session, Order, User
        self.Assignment, self.Report, self.Offer = Assignment, Report, Offer

    def lock_order(self, order_id):
        row = (self.session.query(self.Order).filter(self.Order.id == int(order_id))
               .populate_existing().with_for_update().one_or_none())
        if row is None:
            raise CaseAssignmentServiceError('ORDER_NOT_FOUND')
        return row

    def lock_report(self, order):
        if self.Report is None:
            return getattr(order, 'report', None)
        return (self.session.query(self.Report).filter(self.Report.order_id == int(order.id))
                .populate_existing().with_for_update().one_or_none())

    def lock_doctor(self, doctor_id):
        return (self.session.query(self.User).filter(self.User.id == int(doctor_id))
                .populate_existing().with_for_update().one_or_none())

    def active_assignments(self, order_id):
        a = self.Assignment
        return (self.session.query(a).filter(a.order_id == int(order_id), a.active.is_(True))
                .order_by(a.id).populate_existing().with_for_update().all())

    def pending_offers(self, order_id):
        if self.Offer is None:
            return []
        return (self.session.query(self.Offer)
                .filter(self.Offer.order_id == int(order_id), self.Offer.status == 'PENDING')
                .populate_existing().with_for_update().all())

    def new_assignment(self, **values):
        assignment = self.Assignment(**values)
        self.session.add(assignment)
        return assignment

    def offer_probe(self, offer_id):
        return self.session.query(self.Offer).filter(self.Offer.id == int(offer_id)).one_or_none()

    def order_for_offer(self, offer):
        return self.session.query(self.Order).filter(self.Order.id == offer.order_id).one()

    def lock_offer(self, offer_id):
        return (self.session.query(self.Offer).filter(self.Offer.id == int(offer_id))
                .populate_existing().with_for_update().one_or_none())

    def flush(self):
        self.session.flush()
