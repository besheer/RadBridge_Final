"""Original monitoring SQL scopes; no presence/profile/policy writes."""


class SqlAlchemyMonitorRepository:
    def __init__(self, session, *, Profile, Presence, Assignment, Order, Report, Offer):
        self.session=session
        self.Profile,self.Presence,self.Assignment=Profile,Presence,Assignment
        self.Order,self.Report,self.Offer=Order,Report,Offer

    def profiles(self):return self.session.query(self.Profile).all()
    def presence(self):return self.session.query(self.Presence).all()
    def active_assignments(self):return self.session.query(self.Assignment).filter_by(active=True).all()
    def open_orders(self):
        return self.session.query(self.Order).filter(self.Order.status.notin_(['FINAL','CANCELLED'])).order_by(self.Order.scheduled).all()
    def reports(self, order_ids):
        return self.session.query(self.Report).filter(self.Report.order_id.in_(order_ids)).all()
    def pending_offers(self):
        return self.session.query(self.Offer).filter_by(status='PENDING').order_by(self.Offer.offered_at).all()
