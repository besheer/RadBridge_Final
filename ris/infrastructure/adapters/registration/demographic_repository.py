"""SQLAlchemy evidence and request writes; no demographic identity update."""


class SqlAlchemyDemographicRepository:
    def __init__(self, session, *, Patient, Extra, Order, ReportVersion, Appointment,
                 AssignmentVisit, Request, Detail, open_statuses):
        self.session=session
        self.Patient,self.Extra,self.Order=Patient,Extra,Order
        self.ReportVersion,self.Appointment,self.AssignmentVisit=ReportVersion,Appointment,AssignmentVisit
        self.Request,self.Detail,self.open_statuses=Request,Detail,open_statuses

    def nationality(self, patient_id):
        extra=self.session.query(self.Extra).filter_by(patient_id=patient_id).first()
        return str(extra.nationality or '') if extra else ''

    def orders(self, patient_id):
        return self.session.query(self.Order).filter_by(patient_id=patient_id).order_by(self.Order.id).all()

    def report_version_count(self, report_id):
        return self.session.query(self.ReportVersion).filter_by(report_id=report_id).count()

    def bookings(self, patient_id):
        return self.session.query(self.Appointment).filter_by(patient_id=patient_id).order_by(self.Appointment.id).all()

    def visit_count(self, patient_id):
        return self.session.query(self.AssignmentVisit).filter_by(patient_id=patient_id).count()

    def booking_count(self, patient_id):
        return self.session.query(self.Appointment).filter_by(patient_id=patient_id).count()

    def open_request(self, order_id):
        return self.session.query(self.Request).filter(self.Request.order_id==order_id,
            self.Request.request_type=='WRONG_DEMOGRAPHICS',self.Request.status.in_(self.open_statuses)).first()

    def add_request(self, order, reason, actor_id):
        row=self.Request(order_id=order.id,branch_id=order.branch_id,request_type='WRONG_DEMOGRAPHICS',
                         status='NEW',reason=reason,requested_by=actor_id)
        self.session.add(row);self.session.flush()
        return row

    def add_detail(self, row, patient, field, old, proposed, snapshot, impact):
        detail=self.Detail(correction_request_id=row.id,patient_id=patient.id,field_name=field,
                           old_value=old,proposed_value=proposed,snapshot_hash=snapshot,impact_json=impact)
        self.session.add(detail)

    def lock_patient(self, patient_id):
        return self.session.query(self.Patient).filter_by(id=patient_id).with_for_update().first()
