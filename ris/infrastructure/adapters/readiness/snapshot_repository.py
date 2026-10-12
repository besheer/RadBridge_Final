"""Read-only SQL evidence for the existing operations dashboard."""
from sqlalchemy import text, DateTime


class SqlAlchemyOperationsSnapshotRepository:
    def __init__(self, session, Order, Report, CaseAssignment, AssignmentOffer,
                 AssignmentStrategy, AssignmentEscalationEvent, CaseReadiness,
                 PacsStudyInbox, PacsExamLink, PacsResolutionEvent):
        self.session=session
        self.Order,self.Report,self.Assignment,self.Offer=Order,Report,CaseAssignment,AssignmentOffer
        self.Strategy,self.Escalation,self.Readiness=AssignmentStrategy,AssignmentEscalationEvent,CaseReadiness
        self.Inbox,self.Link,self.Event=PacsStudyInbox,PacsExamLink,PacsResolutionEvent

    def _orders_in_scope(self, branch_ids):
        if branch_ids is None:
            return self.session.query(self.Order)
        if not branch_ids:
            return None
        return self.session.query(self.Order).filter(self.Order.branch_id.in_(branch_ids))

    def orders(self, limit, branch_ids=None):
        query=self._orders_in_scope(branch_ids)
        return query.order_by(self.Order.id.desc()).limit(limit).all() if query is not None else []

    def reports(self, ids):
        return self.session.query(self.Report).filter(self.Report.order_id.in_(ids)).all() if ids else []

    def readiness(self, ids):
        return self.session.query(self.Readiness).filter(self.Readiness.order_id.in_(ids)).all() if ids else []

    def assignments(self, ids):
        M=self.Assignment
        return self.session.query(M).filter(M.order_id.in_(ids),M.active.is_(True)).all() if ids else []

    def pending_offers(self, ids):
        M=self.Offer
        return self.session.query(M).filter(M.order_id.in_(ids),M.status=='PENDING').all() if ids else []

    def leases(self, order_ids=None):
        if order_ids is not None and not order_ids:
            return []
        sql='''SELECT id, order_id, user_id, editor_type,
            acquired_at, renewed_at, expires_at FROM report_edit_lease'''
        if order_ids is not None:
            sql+=' WHERE order_id IN :order_ids'
        sql+=' ORDER BY expires_at DESC, id DESC'
        statement=text(sql).columns(
                acquired_at=DateTime(timezone=True),renewed_at=DateTime(timezone=True),expires_at=DateTime(timezone=True))
        if order_ids is None:
            return self.session.execute(statement).mappings().all()
        from sqlalchemy import bindparam
        statement=statement.bindparams(bindparam('order_ids', expanding=True))
        return self.session.execute(statement,{'order_ids':order_ids}).mappings().all()

    def inbox(self, state, limit, order_ids=None, branch_ids=None):
        M=self.Inbox
        if order_ids is not None and not order_ids:return []
        query=self.session.query(M).filter(M.state==state)
        if order_ids is not None:query=query.filter(M.order_id.in_(order_ids))
        elif branch_ids is not None:
            if not branch_ids:return []
            query=query.join(self.Order,M.order_id==self.Order.id).filter(self.Order.branch_id.in_(branch_ids))
        return query.order_by(M.first_seen_at.desc()).limit(limit).all()

    def active_links(self, limit, order_ids=None, branch_ids=None):
        M=self.Link
        if order_ids is not None and not order_ids:return []
        query=self.session.query(M).filter(M.active.is_(True))
        if order_ids is not None:query=query.filter(M.order_id.in_(order_ids))
        elif branch_ids is not None:
            if not branch_ids:return []
            query=query.join(self.Order,M.order_id==self.Order.id).filter(self.Order.branch_id.in_(branch_ids))
        return query.order_by(M.created_at.desc()).limit(limit).all()

    def strategies(self, branch_ids=None):
        M=self.Strategy
        query=self.session.query(M).filter(M.enabled.is_(True))
        if branch_ids is not None:
            if not branch_ids:return []
            query=query.filter((M.branch_id.is_(None)) | M.branch_id.in_(branch_ids))
        return query.order_by(M.priority,M.id).all()

    def recent_escalations(self, order_ids=None, branch_ids=None):
        M=self.Escalation
        if order_ids is not None and not order_ids:return []
        query=self.session.query(M)
        if order_ids is not None:query=query.filter(M.order_id.in_(order_ids))
        elif branch_ids is not None:
            if not branch_ids:return []
            query=query.join(self.Order,M.order_id==self.Order.id).filter(self.Order.branch_id.in_(branch_ids))
        return query.order_by(M.created_at.desc()).limit(20).all()

    def recent_pacs_events(self, order_ids=None, branch_ids=None):
        M=self.Event
        if order_ids is not None and not order_ids:return []
        query=self.session.query(M)
        if order_ids is not None:query=query.filter(M.order_id.in_(order_ids))
        elif branch_ids is not None:
            if not branch_ids:return []
            query=query.join(self.Order,M.order_id==self.Order.id).filter(self.Order.branch_id.in_(branch_ids))
        return query.order_by(M.created_at.desc()).limit(20).all()
