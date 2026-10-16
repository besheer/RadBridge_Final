"""Shared registration validation and explicit visit assignment choices."""
from datetime import datetime, date
from sqlalchemy import text


from domain.registration.patient_validation import FIELDS, validate_patient_fields as _validate, allowed_registration_branches as _branches
from application.services.registration import visit_registration as _visits
from infrastructure.adapters.registration.visit_repository import SqlAlchemyRegistrationVisitRepository

def validate_patient_fields(values):
    from application.legacy_runtime import resolve_runtime
    m=resolve_runtime()
    return _validate(values,m.registration_rule_map(),m.validate_registration_value,date.today())

def validate_patient(patient):
    from application.legacy_runtime import resolve_runtime as _rb_runtime; m = _rb_runtime()
    extra = m.PatientDemographicsExtra.query.filter_by(patient_id=patient.id).first()
    values = {key: getattr(patient, key, '') for key in FIELDS}
    values['nationality'] = extra.nationality if extra else ''
    validate_patient_fields(values)


def field_rules_for_ui():
    from application.legacy_runtime import resolve_runtime as _rb_runtime; m = _rb_runtime()
    return {key.split('.', 1)[1]: dict(required=bool(row.required), visible=bool(row.visible),
            data_type=row.data_type, min_length=row.min_length, max_length=row.max_length,
            exact_length=row.exact_length, regex_pattern=row.regex_pattern, label=row.label_en or key)
            for key, row in m.registration_rule_map().items() if key.startswith('patient.')}


def _visit_dependencies(m):
    from assignment_visit_grouping import create_visit,group_members,assign_visit_atomically
    from assignment_distribution import case_capacity,active_case_count,validate_special_doctor
    repository=SqlAlchemyRegistrationVisitRepository(m.db.session,m.AssignmentVisit,m.Order,
        m.CaseAssignment,m.ReportVersion,m.User,m.DoctorAssignmentProfile,m.Appointment,m.AssignmentOffer)
    def assign(order,doctor_id):
        return assign_visit_atomically(db=m.db,Order=m.Order,User=m.User,CaseAssignment=m.CaseAssignment,
            Report=m.Report,AssignmentOffer=m.AssignmentOffer,order_id=order.id,doctor_user_id=doctor_id,
            assignment_type='MANUAL',assigned_by=m.current_user().id,
            notes='Doctor selected during registration; excluded from automatic assignment and withdrawal')
    policies=_visits.RegistrationPolicies(create_visit,m.has_perm,m.abort,active_case_count,case_capacity,
        m.audit,datetime.utcnow,group_members,validate_special_doctor,assign)
    return repository,policies

def select_visit(patient,branch,scheduled,procedures,form):
    from application.legacy_runtime import resolve_runtime
    repository,policies=_visit_dependencies(resolve_runtime())
    return _visits.select_visit(repository,policies,patient,branch,scheduled,procedures,form)

def assign_reserved_visit(order):
    from application.legacy_runtime import resolve_runtime
    repository,policies=_visit_dependencies(resolve_runtime())
    return _visits.assign_reserved_visit(repository,policies,order)

def allowed_registration_branches():
    from application.legacy_runtime import resolve_runtime
    return _branches(resolve_runtime().current_user())

def require_registration_branch(branch_id):
    from application.legacy_runtime import resolve_runtime as _rb_runtime; m = _rb_runtime()
    allowed=allowed_registration_branches()
    if allowed is not None and branch_id not in allowed:m.abort(403)
