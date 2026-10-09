"""Shared registration validation and explicit visit assignment choices."""
from datetime import datetime, date
from sqlalchemy import text


FIELDS = ('name', 'phone', 'national_id', 'address', 'email', 'nationality', 'dob', 'sex')


def validate_patient_fields(values):
    import app as m
    rules = m.registration_rule_map()
    for key in FIELDS:
        ok, message = m.validate_registration_value(rules.get('patient.'+key), values.get(key, ''))
        if not ok:
            raise ValueError(message)

    dob = (values.get('dob') or '').strip()
    if dob:
        try:
            parsed = datetime.strptime(dob, '%Y%m%d').date()
            if len(dob) != 8 or parsed > date.today():
                raise ValueError()
        except ValueError:
            raise ValueError('Enter a valid date of birth that is not in the future.')
    if (values.get('sex') or '').strip() not in ('', 'M', 'F', 'O'):
        raise ValueError('Choose a valid patient sex.')


def validate_patient(patient):
    import app as m
    extra = m.PatientDemographicsExtra.query.filter_by(patient_id=patient.id).first()
    values = {key: getattr(patient, key, '') for key in FIELDS}
    values['nationality'] = extra.nationality if extra else ''
    validate_patient_fields(values)


def field_rules_for_ui():
    import app as m
    return {key.split('.', 1)[1]: dict(required=bool(row.required), visible=bool(row.visible),
            data_type=row.data_type, min_length=row.min_length, max_length=row.max_length,
            exact_length=row.exact_length, regex_pattern=row.regex_pattern, label=row.label_en or key)
            for key, row in m.registration_rule_map().items() if key.startswith('patient.')}


def select_visit(patient, branch, scheduled, procedures, form):
    import app as m
    from assignment_visit_grouping import create_visit
    from assignment_distribution import case_capacity, active_case_count
    raw = (form.get('assignment_visit_id') or '').strip()
    if raw:
        visit = m.AssignmentVisit.query.filter_by(id=raw).first()
        if not visit or (visit.patient_id, visit.branch_id, visit.visit_date) != (patient.id, branch.id, scheduled.date()):
            raise ValueError('Choose a visit for the same patient, branch and date.')
        if m.db.engine.dialect.name == 'postgresql':
            m.db.session.execute(text('SELECT pg_advisory_xact_lock(20261003, :id)'), {'id': visit.sequence_id})
        m.db.session.refresh(visit)
    else:
        visit = m.AssignmentVisit.query.filter_by(id=create_visit(patient.id, branch.id, scheduled)).first()
    members = m.Order.query.filter_by(assignment_visit_id=visit.id).order_by(m.Order.id).with_for_update().all()
    for order in members:
        assignment = m.CaseAssignment.query.filter_by(order_id=order.id, active=True).first()
        report = order.report
        if order.status in ('FINAL', 'CANCELLED') or (report and (report.status in ('VERIFIED', 'FINAL') or report.findings or report.impression or m.ReportVersion.query.filter_by(report_id=report.id).first())):
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
        if not raw and not m.has_perm('assignment.manage'): m.abort(403)
        if raw and visit.assignment_mode != 'MANUAL' and not m.has_perm('assignment.manage'): m.abort(403)
        doctor = m.User.query.filter_by(id=doctor_id, active=True).with_for_update().first()
        if not doctor or not doctor.role or doctor.role.code not in ('RADIOLOGIST','DOCTOR'):
            raise ValueError('Choose an active reporting doctor.')
        profile = m.DoctorAssignmentProfile.query.filter_by(user_id=doctor_id).first()
        modalities = {p.modality.upper() for p in procedures} | {o.modality.upper() for o in members}
        appointments = m.Appointment.query.filter_by(assignment_visit_id=visit.id).filter(m.Appointment.status.notin_(['CANCELLED','NO_SHOW'])).all()
        modalities |= {a.procedure.modality.upper() for a in appointments}
        allowed = {x.strip().upper() for x in (profile.modalities or '').split(',') if x.strip()} if profile else set()
        branches = {x.strip() for x in (profile.branches or '').split(',') if x.strip()} if profile else set()
        if (allowed and not modalities.issubset(allowed)) or (branches and str(branch.id) not in branches):
            raise ValueError('Selected doctor must qualify for every examination in this visit.')
        if any(o.assigned_doctor_id and o.assigned_doctor_id != doctor_id for o in members):
            raise ValueError('Visit examinations already belong to another doctor.')
        new_count = len(procedures) + sum(o.assigned_doctor_id != doctor_id for o in members)
        if active_case_count(doctor_id) + new_count > case_capacity(doctor_id):
            raise ValueError('Selected doctor does not have capacity for the whole visit.')
        visit.preferred_doctor_id = doctor_id
    elif any(o.assigned_doctor_id for o in members):
        raise ValueError('Keep the existing manual assignment for this visit.')
    visit.assignment_mode = mode
    visit.registration_open = form.get('visit_registration_open') == '1'
    # Membership changes invalidate old offers; never silently accept a stale group.
    if members:
        m.AssignmentOffer.query.filter(m.AssignmentOffer.order_id.in_([o.id for o in members]),m.AssignmentOffer.status=='PENDING').update(
            dict(status='CANCELLED',responded_at=datetime.utcnow(),response_note='Visit examinations updated during registration'),synchronize_session='fetch')
    m.audit('REGISTRATION_VISIT_CHOICE','assignment_visit',visit.id,
            f'mode={mode};doctor={visit.preferred_doctor_id};open={visit.registration_open}')
    m.db.session.flush()
    return visit.id


def assign_reserved_visit(order):
    import app as m
    from assignment_visit_grouping import assign_visit_atomically, group_members
    from case_assignment_service import CaseAssignmentServiceError
    visit = m.AssignmentVisit.query.filter_by(id=order.assignment_visit_id).first() if order.assignment_visit_id else None
    if not visit or visit.assignment_mode != 'MANUAL': return
    try:
        members=group_members(order,lock=True)
        doctor=m.User.query.filter_by(id=visit.preferred_doctor_id,active=True).with_for_update().first()
        if not doctor or not doctor.role or doctor.role.code not in ('RADIOLOGIST','DOCTOR'):
            raise ValueError('The reserved reporting doctor is no longer active.')
        profile=m.DoctorAssignmentProfile.query.filter_by(user_id=doctor.id).first()
        allowed={x.strip().upper() for x in (profile.modalities or '').split(',') if x.strip()} if profile else set()
        branches={x.strip() for x in (profile.branches or '').split(',') if x.strip()} if profile else set()
        appointments=m.Appointment.query.filter_by(assignment_visit_id=visit.id).filter(m.Appointment.status.notin_(['CANCELLED','NO_SHOW'])).all()
        modalities={o.modality.upper() for o in members}|{a.procedure.modality.upper() for a in appointments}
        if (allowed and not modalities.issubset(allowed)) or (branches and str(visit.branch_id) not in branches):
            raise ValueError('Reserved doctor must still qualify for every examination in this visit.')
        from assignment_distribution import validate_special_doctor
        for a in appointments:
            planned=m.Order(modality=a.procedure.modality,procedure=a.procedure.name,priority=a.priority,assignment_special_code=a.assignment_special_code)
            validate_special_doctor(planned,doctor)
        assign_visit_atomically(db=m.db,Order=m.Order,User=m.User,CaseAssignment=m.CaseAssignment,
            Report=m.Report,AssignmentOffer=m.AssignmentOffer,order_id=order.id,
            doctor_user_id=visit.preferred_doctor_id,assignment_type='MANUAL',assigned_by=m.current_user().id,
            notes='Doctor selected during registration; excluded from automatic assignment and withdrawal')
    except CaseAssignmentServiceError as exc: raise ValueError(str(exc)) from exc


def allowed_registration_branches():
    """None means all active branches; ordinary staff use their assigned branch."""
    import app as m
    user=m.current_user()
    if user and user.role and user.role.code in ('SUPER_ADMIN','CALL_CENTER'):
        return None
    return [user.branch_id] if user and getattr(user,'branch_id',None) else []

def require_registration_branch(branch_id):
    import app as m
    allowed=allowed_registration_branches()
    if allowed is not None and branch_id not in allowed:m.abort(403)
