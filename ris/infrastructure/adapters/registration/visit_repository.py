"""Visit registration evidence and SQL locks; transaction remains caller-owned."""
from sqlalchemy import text


class SqlAlchemyRegistrationVisitRepository:
    def __init__(self, session, Visit, Order, Assignment, ReportVersion, User, Profile, Appointment, Offer):
        self.session,self.Visit,self.Order,self.Assignment=session,Visit,Order,Assignment
        self.ReportVersion,self.User,self.Profile,self.Appointment,self.Offer=ReportVersion,User,Profile,Appointment,Offer
    def find_visit(self, visit_id): return self.session.query(self.Visit).filter_by(id=visit_id).first()
    def lock_and_refresh_visit(self, visit):
        if self.session.get_bind().dialect.name == 'postgresql':
            self.session.execute(text('SELECT pg_advisory_xact_lock(20261003, :id)'),{'id':visit.sequence_id})
        self.session.refresh(visit)
    def locked_members(self, visit_id):
        return self.session.query(self.Order).filter_by(assignment_visit_id=visit_id).order_by(self.Order.id).with_for_update().all()
    def active_assignment(self, order_id):
        return self.session.query(self.Assignment).filter_by(order_id=order_id,active=True).first()
    def report_version(self, report_id):
        return self.session.query(self.ReportVersion).filter_by(report_id=report_id).first()
    def lock_active_doctor(self, doctor_id):
        return self.session.query(self.User).filter_by(id=doctor_id,active=True).with_for_update().first()
    def doctor_profile(self, doctor_id):
        return self.session.query(self.Profile).filter_by(user_id=doctor_id).first()
    def open_appointments(self, visit_id):
        return self.session.query(self.Appointment).filter_by(assignment_visit_id=visit_id).filter(self.Appointment.status.notin_(['CANCELLED','NO_SHOW'])).all()
    def cancel_pending_offers(self, order_ids, now):
        self.session.query(self.Offer).filter(self.Offer.order_id.in_(order_ids),self.Offer.status=='PENDING').update(dict(status='CANCELLED',responded_at=now,response_note='Visit examinations updated during registration'),synchronize_session='fetch')
    def planned_order(self, **values): return self.Order(**values)
    def flush(self): self.session.flush()
