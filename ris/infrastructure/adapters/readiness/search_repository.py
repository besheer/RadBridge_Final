"""Scoped SQL candidate retrieval; no mutations or identity corrections."""
from sqlalchemy import or_


class SqlAlchemyReadinessSearchRepository:
    def __init__(self, session, Order, Patient):
        self.session, self.Order, self.Patient = session, Order, Patient

    def candidates(self, query, limit):
        Order, Patient = self.Order, self.Patient
        like = f'%{query}%'
        filters = [Order.accession.ilike(like), Order.procedure.ilike(like),
                   Order.study_instance_uid.ilike(like), Patient.name.ilike(like),
                   Patient.patient_id.ilike(like), Patient.phone.ilike(like),
                   Patient.national_id.ilike(like)]
        if query.isdigit():
            filters.append(Order.id == int(query))
        return (self.session.query(Order).join(Patient).filter(or_(*filters))
                .order_by(Order.id.desc()).limit(limit).all())
