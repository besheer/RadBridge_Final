"""SQLAlchemy search predicate for the coordinator's bulk-assignment queue."""
from sqlalchemy import or_


class SqlAlchemyCoordinatorCaseSearch:
    def __init__(self, *, Patient, Order):
        self.Patient = Patient
        self.Order = Order

    def apply(self, query, search):
        search = (search or '').strip()
        if not search:
            return query
        like = '%' + search + '%'
        return query.filter(
            or_(
                self.Patient.name.ilike(like),
                self.Patient.patient_id.ilike(like),
                self.Order.accession.ilike(like),
            )
        )
