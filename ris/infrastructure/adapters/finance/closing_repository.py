"""Read-only receipt/refund evidence by branch and accounting timestamp."""


class SqlAlchemyClosingRepository:
    def __init__(self, session, Order, Payment, PaymentRefund):
        self.session,self.Order,self.Payment,self.Refund = session,Order,Payment,PaymentRefund

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
