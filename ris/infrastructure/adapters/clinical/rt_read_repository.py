"""Scoped read-only RT SQL projections with explicit model ownership."""
from sqlalchemy import false,literal,or_,select
from infrastructure.adapters.identity.scope_repository import scope_predicate


class SqlAlchemyRTReadRepository:
    def __init__(self, session, Course, Plan, Fraction, PetLink, Note, Consumable, Order, Patient, Device, Branch):
        self.session=session
        self.Course,self.Plan,self.Fraction,self.PetLink,self.Note,self.Consumable=Course,Plan,Fraction,PetLink,Note,Consumable
        self.Order,self.Patient,self.Device,self.Branch=Order,Patient,Device,Branch

    def _predicate(self, scope, model):
        return scope_predicate(scope,model=model,Device=self.Device,Branch=self.Branch)

    def worklist(self, global_access, branch_id, scope, search):
        C,P,O=self.Course,self.Patient,self.Order
        query=self.session.query(C)
        if not global_access:
            query=query.filter(C.branch_id==branch_id) if branch_id else query.filter(false())
        if scope:
            query=query.filter(C.primary_order_id.in_(self.session.query(O.id).filter(self._predicate(scope,O))))
        if search:
            query=query.join(P,C.patient_id==P.id).filter(or_(C.reference.ilike('%'+search+'%'),P.patient_id==search))
        return query.order_by(C.created_at.desc()).limit(100).all()

    def course(self, course_id):
        return self.session.query(self.Course).filter_by(id=course_id).first()

    def current_plan(self, course_id):
        return self.session.query(self.Plan).filter_by(course_id=course_id,status='ACTIVE').first()

    def devices(self, branch_id):
        return self.session.query(self.Device).filter_by(branch_id=branch_id).order_by(self.Device.name).all()

    def device_matches(self, scope, device):
        cols=select(literal(device.modality).label('modality'),literal(device.id).label('device_id')).subquery().c
        return self.session.execute(select(cols.device_id).where(self._predicate(scope,cols))).first() is not None

    def plans(self, course_id):
        M=self.Plan
        return self.session.query(M).filter_by(course_id=course_id).order_by(M.revision.desc()).all()

    def fractions(self, course_id, device_ids):
        M=self.Fraction
        return self.session.query(M).filter_by(course_id=course_id).filter(M.device_id.in_(device_ids)).order_by(M.number).all()

    def pet_links(self, course_id):
        return self.session.query(self.PetLink).filter_by(course_id=course_id).all()

    def notes(self, course_id, device_ids):
        M,F=self.Note,self.Fraction
        return (self.session.query(M).filter_by(course_id=course_id)
                .filter(or_(M.fraction_id.is_(None),M.fraction_id.in_(self.session.query(F.id).filter(F.device_id.in_(device_ids)))))
                .order_by(M.recorded_at.desc()).all())

    def consumables(self, course_id, device_ids):
        C,F=self.Consumable,self.Fraction
        return self.session.query(C).join(F).filter(F.course_id==course_id,F.device_id.in_(device_ids)).all()
