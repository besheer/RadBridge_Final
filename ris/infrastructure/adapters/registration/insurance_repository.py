"""Latest insurance decision query without runtime resolution."""


class SqlAlchemyInsuranceRepository:
    def __init__(self, session, ApprovalRequest):
        self.session,self.ApprovalRequest=session,ApprovalRequest

    def latest(self, order_id):
        M=self.ApprovalRequest
        return self.session.query(M).filter_by(order_id=order_id).order_by(M.id.desc()).first()
