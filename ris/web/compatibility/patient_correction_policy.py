"""Legacy callable surface; HTTP and runtime composition stay at the web edge."""
from datetime import date
from domain.registration.demographic_correction import FIELDS, IDENTITY_FIELDS
from application.services.registration.demographic_corrections import DemographicCorrections, ReviewDenied
from infrastructure.adapters.registration.demographic_repository import SqlAlchemyDemographicRepository


def _service(runtime):
    m=runtime
    repository=SqlAlchemyDemographicRepository(m.db.session,Patient=m.Patient,
        Extra=m.PatientDemographicsExtra,Order=m.Order,ReportVersion=m.ReportVersion,
        Appointment=m.Appointment,AssignmentVisit=m.AssignmentVisit,
        Request=m.CorrectionRequest,Detail=m.PatientDemographicsCorrection,
        open_statuses=m.CORRECTION_OPEN_STATUSES)
    return DemographicCorrections(repository,registration_rules=m.registration_rule_map,
        validate_registration=m.validate_registration_value,actor_id=lambda:m.current_user().id,
        branch_allowed=m.correction_branch_allowed,audit=m.audit,today=date.today)


def current_value(patient,field,*,runtime):return _service(runtime).current_value(patient,field)
def patient_orders(patient,*,runtime):return _service(runtime).patient_orders(patient)
def snapshot(patient,*,runtime):return _service(runtime).snapshot(patient)
def impact(patient,field,*,runtime):return _service(runtime).impact(patient,field)
def normalize(field,value,*,runtime):return _service(runtime).normalize(field,value)
def submit(order,field,value,reason,expected_snapshot,*,runtime):
    return _service(runtime).submit(order,field,value,reason,expected_snapshot)
def assert_approvable(row,*,runtime):
    m=runtime
    try:return _service(m).assert_approvable(row)
    except ReviewDenied as error:m.abort(error.status,str(error))
