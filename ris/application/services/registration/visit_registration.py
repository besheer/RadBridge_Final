"""Visit selection/reservation over explicit query, qualification and mutation ports."""
from dataclasses import dataclass
from typing import Callable
from application.services.assignment.assignment_transaction import CaseAssignmentServiceError


@dataclass(frozen=True)
class RegistrationPolicies:
    create_visit: Callable
    has_perm: Callable
    deny: Callable
    active_case_count: Callable
    case_capacity: Callable
    audit: Callable
    clock: Callable
    group_members: Callable
    validate_special_doctor: Callable
    assign_visit: Callable


def select_visit(repository, policies, patient, branch, scheduled, procedures, form):
    raw = (form.get('assignment_visit_id') or '').strip()
    if raw:
        visit = repository.find_visit(raw)
        if not visit or (visit.patient_id, visit.branch_id, visit.visit_date) != (patient.id, branch.id, scheduled.date()):
            raise ValueError('Choose a visit for the same patient, branch and date.')
        repository.lock_and_refresh_visit(visit)
    else:
        visit = repository.find_visit(policies.create_visit(patient.id, branch.id, scheduled))
    members = repository.locked_members(visit.id)
    for order in members:
        assignment = repository.active_assignment(order.id)
        report = order.report
        if order.status in ('FINAL', 'CANCELLED') or (report and (report.status in ('VERIFIED', 'FINAL') or report.findings or report.impression or repository.report_version(report.id))):
            raise ValueError('This visit has completed or saved reporting work. Register a separate visit.')
        if assignment and (assignment.reading_started_at or assignment.assignment_type != 'MANUAL'):
            raise ValueError('This visit is already in reading or automatic assignment. Register a separate visit.')
    mode = (form.get('assignment_mode') or 'AUTO').upper()
    if mode not in ('AUTO', 'MANUAL'): raise ValueError('Invalid assignment mode.')
    doctor_id = form.get('selected_doctor_id', type=int)
    if raw and visit.assignment_mode == 'MANUAL':
        # Existing manual reservation is carried across device registrations.
        mode = 'MANUAL'; doctor_id = visit.preferred_doctor_id
    if mode == 'MANUAL':
        if not raw and not policies.has_perm('assignment.manage'): policies.deny(403)
        if raw and visit.assignment_mode != 'MANUAL' and not policies.has_perm('assignment.manage'): policies.deny(403)
        doctor = repository.lock_active_doctor(doctor_id)
        if not doctor or not doctor.role or doctor.role.code not in ('RADIOLOGIST','DOCTOR'):
            raise ValueError('Choose an active reporting doctor.')
        profile = repository.doctor_profile(doctor_id)
        modalities = {p.modality.upper() for p in procedures} | {o.modality.upper() for o in members}
        appointments = repository.open_appointments(visit.id)
        modalities |= {a.procedure.modality.upper() for a in appointments}
        allowed = {x.strip().upper() for x in (profile.modalities or '').split(',') if x.strip()} if profile else set()
        branches = {x.strip() for x in (profile.branches or '').split(',') if x.strip()} if profile else set()
        if (allowed and not modalities.issubset(allowed)) or (branches and str(branch.id) not in branches):
            raise ValueError('Selected doctor must qualify for every examination in this visit.')
        if any(o.assigned_doctor_id and o.assigned_doctor_id != doctor_id for o in members):
            raise ValueError('Visit examinations already belong to another doctor.')
        new_count = len(procedures) + sum(o.assigned_doctor_id != doctor_id for o in members)
        if policies.active_case_count(doctor_id) + new_count > policies.case_capacity(doctor_id):
            raise ValueError('Selected doctor does not have capacity for the whole visit.')
        visit.preferred_doctor_id = doctor_id
    elif any(o.assigned_doctor_id for o in members):
        raise ValueError('Keep the existing manual assignment for this visit.')
    visit.assignment_mode = mode
    visit.registration_open = form.get('visit_registration_open') == '1'
    # Membership changes invalidate old offers; never silently accept a stale group.
    if members:
        repository.cancel_pending_offers([o.id for o in members], policies.clock())
    policies.audit('REGISTRATION_VISIT_CHOICE','assignment_visit',visit.id,
            f'mode={mode};doctor={visit.preferred_doctor_id};open={visit.registration_open}')
    repository.flush()
    return visit.id


def assign_reserved_visit(repository, policies, order):
    visit = repository.find_visit(order.assignment_visit_id) if order.assignment_visit_id else None
    if not visit or visit.assignment_mode != 'MANUAL': return
    try:
        members=policies.group_members(order,lock=True)
        doctor=repository.lock_active_doctor(visit.preferred_doctor_id)
        if not doctor or not doctor.role or doctor.role.code not in ('RADIOLOGIST','DOCTOR'):
            raise ValueError('The reserved reporting doctor is no longer active.')
        profile=repository.doctor_profile(doctor.id)
        allowed={x.strip().upper() for x in (profile.modalities or '').split(',') if x.strip()} if profile else set()
        branches={x.strip() for x in (profile.branches or '').split(',') if x.strip()} if profile else set()
        appointments=repository.open_appointments(visit.id)
        modalities={o.modality.upper() for o in members}|{a.procedure.modality.upper() for a in appointments}
        if (allowed and not modalities.issubset(allowed)) or (branches and str(visit.branch_id) not in branches):
            raise ValueError('Reserved doctor must still qualify for every examination in this visit.')
        for a in appointments:
            planned=repository.planned_order(modality=a.procedure.modality,procedure=a.procedure.name,priority=a.priority,assignment_special_code=a.assignment_special_code)
            policies.validate_special_doctor(planned,doctor)
        policies.assign_visit(order, visit.preferred_doctor_id)
    except CaseAssignmentServiceError as exc: raise ValueError(str(exc)) from exc

