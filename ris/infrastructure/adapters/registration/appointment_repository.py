"""Appointment evidence/add/flush only; transaction ownership is outside."""


class SqlAlchemyAppointmentRepository:
    def __init__(self, session, *, Branch, Procedure, Patient, Device, Appointment):
        self.session=session
        self.Branch,self.Procedure,self.Patient=Branch,Procedure,Patient
        self.Device,self.Appointment=Device,Appointment

    def active_branch(self, id):return self.session.query(self.Branch).filter_by(id=id,active=True).first()
    def active_procedure(self, id):return self.session.query(self.Procedure).filter_by(id=id,active=True).first()
    def patient(self, id):return self.session.get(self.Patient,id)
    def device(self, id):return self.session.get(self.Device,id)
    def add(self, **values):
        row=self.Appointment(**values)
        self.session.add(row);self.session.flush()
        return row
