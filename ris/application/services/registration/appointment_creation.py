"""Existing-patient appointment creation through narrow evidence/policy ports.

The caller authorizes the branch and owns savepoint/commit/rollback handling.
"""
from domain.registration.booking_validation import local_appointment_time


class AppointmentCreation:
    def __init__(self, repository, *, procedure_available, route_device, lock_slot,
                 restriction_reason, actor_id, audit):
        self.repository=repository
        self.procedure_available,self.route_device=procedure_available,route_device
        self.lock_slot,self.restriction_reason=lock_slot,restriction_reason
        self.actor_id,self.audit=actor_id,audit

    def create(self, values):
        branch=self.repository.active_branch(values.get('branch_id'))
        procedure=self.repository.active_procedure(values.get('procedure_id'))
        patient=self.repository.patient(values.get('patient_id'))
        if not branch or not procedure or not patient:
            raise ValueError('Choose an active branch, examination and existing patient.')
        if not self.procedure_available(procedure.id,branch.id):
            raise ValueError('Examination is not available in this branch.')
        scheduled=local_appointment_time(values.get('scheduled',''))
        device_id=values.get('device_id')
        device=self.repository.device(device_id) if device_id else self.route_device(branch.id,procedure.modality)
        if not device or device.branch_id!=branch.id or device.modality.upper()!=procedure.modality.upper():
            raise ValueError('Choose a matching device in this branch.')
        duration=procedure.duration_min or 20
        self.lock_slot(device.id,scheduled)
        reason=self.restriction_reason(branch,procedure,device,scheduled,duration)
        if reason:raise ValueError(reason)
        row=self.repository.add(patient_id=patient.id,branch_id=branch.id,procedure_id=procedure.id,
            device_id=device.id,scheduled=scheduled,duration_min=duration,status='BOOKED',
            source=values.get('source','CALL_CENTER'),notes=values.get('notes',''),created_by=self.actor_id())
        self.audit('APPOINTMENT_CREATE','appointment',row.id,str(row.scheduled))
        return row
