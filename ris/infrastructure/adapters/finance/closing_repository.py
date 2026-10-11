"""Read-only receipt/refund evidence by branch and accounting timestamp."""


class SqlAlchemyClosingRepository:
    def __init__(self, session, Order, Payment, PaymentRefund, Branch=None, DailyClosing=None):
        self.session,self.Order,self.Payment,self.Refund = session,Order,Payment,PaymentRefund
        self.Branch,self.Closing=Branch,DailyClosing

    def lock_branch(self, branch_id):
        return self.session.query(self.Branch).filter_by(id=branch_id,active=True).with_for_update().one()

    def lock_closing(self, branch_id, closing_date):
        M=self.Closing
        return (self.session.query(M).filter_by(branch_id=branch_id,closing_date=closing_date)
                .populate_existing().with_for_update().order_by(M.id.desc()).first())

    def create_closing(self, **values): return self.Closing(**values)
    def add(self, row): self.session.add(row)
    def flush(self): self.session.flush()

    def receipts(self, branch_id, start, end):
        P,O=self.Payment,self.Order
        query=self.session.query(P).join(O).filter(P.created_at>=start,P.created_at<end)
        if branch_id: query=query.filter(O.branch_id==branch_id)
        return query.all()

    def refunds(self, branch_id, start, end):
        R,O=self.Refund,self.Order
        query=self.session.query(R).join(O,R.order_id==O.id).filter(R.created_at>=start,R.created_at<end)
        if branch_id: query=query.filter(O.branch_id==branch_id)
        return query.all()
