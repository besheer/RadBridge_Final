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

    def orders(self, limit):
        return self.session.query(self.Order).order_by(self.Order.id.desc()).limit(limit).all()

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

    def leases(self):
        statement=text('''SELECT id, order_id, user_id, editor_type,
            acquired_at, renewed_at, expires_at FROM report_edit_lease
            ORDER BY expires_at DESC, id DESC''').columns(
                acquired_at=DateTime(timezone=True),renewed_at=DateTime(timezone=True),expires_at=DateTime(timezone=True))
        return self.session.execute(statement).mappings().all()

    def inbox(self, state, limit):
        M=self.Inbox
        return self.session.query(M).filter(M.state==state).order_by(M.first_seen_at.desc()).limit(limit).all()

    def active_links(self, limit):
        M=self.Link
        return self.session.query(M).filter(M.active.is_(True)).order_by(M.created_at.desc()).limit(limit).all()

    def strategies(self):
        M=self.Strategy
        return self.session.query(M).filter(M.enabled.is_(True)).order_by(M.priority,M.id).all()

    def recent_escalations(self):
        M=self.Escalation
        return self.session.query(M).order_by(M.created_at.desc()).limit(20).all()

    def recent_pacs_events(self):
        M=self.Event
        return self.session.query(M).order_by(M.created_at.desc()).limit(20).all()
