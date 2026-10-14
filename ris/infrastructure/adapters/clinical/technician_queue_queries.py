"""SQLAlchemy query predicates used by the technician worklist."""
from sqlalchemy import and_, exists, func, or_, select
from sqlalchemy.orm import aliased


class SqlAlchemyTechnicianQueueQueries:
    def __init__(self, *, Order, Patient, CaseWorkflowEvent):
        self.Order = Order
        self.Patient = Patient
        self.CaseWorkflowEvent = CaseWorkflowEvent

    def open_technician_return(self):
        """Return the latest unresolved technician return as a SQL predicate."""
        returned = aliased(self.CaseWorkflowEvent)
        newer = aliased(self.CaseWorkflowEvent)
        resolved = aliased(self.CaseWorkflowEvent)

        def later(row):
            return or_(
                row.created_at > returned.created_at,
                and_(row.created_at == returned.created_at, row.id > returned.id),
            )

        newer_return = exists(
            select(newer.id)
            .where(
                newer.order_id == returned.order_id,
                newer.event_type == 'RETURNED',
                later(newer),
            )
            .correlate(returned)
        )
        resolution = exists(
            select(resolved.id)
            .where(
                resolved.order_id == returned.order_id,
                resolved.event_type.in_(('RESOLVED', 'READY_FOR_REREVIEW')),
                later(resolved),
            )
            .correlate(returned)
        )
        return exists(
            select(returned.id)
            .where(
                returned.order_id == self.Order.id,
                returned.event_type == 'RETURNED',
                returned.owner_role == 'TECHNICIAN',
                ~newer_return,
                ~resolution,
            )
            .correlate(self.Order)
        )

    def queue_filters(self, returned):
        status = func.upper(func.coalesce(self.Order.exam_status, 'ORDERED'))
        work_order = self.Order.status.in_(
            ('SCHEDULED', 'ARRIVED', 'IN_PROGRESS', 'COMPLETED', 'IMAGES_RECEIVED', 'REPORTING', 'MWL_ERROR')
        )
        return {
            'waiting': and_(status.in_(('BOOKED', 'ORDERED')), ~returned, work_order),
            'in_progress': and_(status == 'IN_PROGRESS', ~returned, work_order),
            'returned': and_(returned, self.Order.status != 'FINAL'),
        }

    def apply_search(self, query, search):
        if not search:
            return query
        like = '%' + search + '%'
        return query.join(self.Patient).filter(
            or_(
                self.Patient.name.ilike(like),
                self.Patient.patient_id.ilike(like),
                self.Patient.phone.ilike(like),
                self.Patient.national_id.ilike(like),
                self.Order.accession.ilike(like),
                self.Order.procedure.ilike(like),
                self.Order.modality.ilike(like),
            )
        )
