"""Explicit patient visit identity; never infer a visit from patient ID alone."""
import uuid
from sqlalchemy import text


def create_visit(patient_id, branch_id, scheduled):
    from application.legacy_runtime import resolve_runtime as _rb_runtime; m = _rb_runtime()
    row=m.AssignmentVisit(id=str(uuid.uuid4()),patient_id=patient_id,branch_id=branch_id,visit_date=scheduled.date())
    m.db.session.add(row);m.db.session.flush();return row.id


def group_members(order, lock=False):
    from application.legacy_runtime import resolve_runtime as _rb_runtime; m = _rb_runtime()
    if not getattr(order,'assignment_visit_id',None):
        return [order]
    visit=m.AssignmentVisit.query.filter_by(id=order.assignment_visit_id).first()
    if not visit or visit.patient_id!=order.patient_id or visit.branch_id!=order.branch_id:
        raise ValueError('VISIT_PATIENT_BRANCH_MISMATCH')
    if lock and m.db.engine.dialect.name=='postgresql':
        m.db.session.execute(text('SELECT pg_advisory_xact_lock(20261003, :id)'),{'id':visit.sequence_id})
    q=m.Order.query.filter_by(assignment_visit_id=visit.id).order_by(m.Order.id).populate_existing()
    if lock: q=q.with_for_update()
    rows=q.all()
    if any(o.patient_id!=visit.patient_id or o.branch_id!=visit.branch_id for o in rows):
        raise ValueError('VISIT_PATIENT_BRANCH_MISMATCH')
    sources=set()
    for member in rows:
        external=m.ExternalIntakeCase.query.filter_by(order_id=member.id).first()
        sources.add(('EXTERNAL',external.center_id) if external else ('INTERNAL',None))
    if len(sources)>1: raise ValueError('VISIT_SOURCE_CENTER_MISMATCH')
    return rows


def visit_ready_for_offer(order):
    from application.legacy_runtime import resolve_runtime as _rb_runtime; m = _rb_runtime()
    members=group_members(order,lock=True)
    visit=m.AssignmentVisit.query.filter_by(id=order.assignment_visit_id).first() if order.assignment_visit_id else None
    if visit:
        if visit.assignment_mode=='MANUAL': return members[0],'VISIT_MANUAL_RESERVATION'
        if visit.registration_open: return members[0],'VISIT_REGISTRATION_OPEN'
        if m.Appointment.query.filter_by(assignment_visit_id=visit.id).filter(m.Appointment.order_id.is_(None),m.Appointment.status.notin_(['CANCELLED','NO_SHOW'])).first():
            return members[0],'VISIT_BOOKINGS_NOT_CHECKED_IN'
    if len(members)==1: return members[0],None
    if any(o.assigned_doctor_id for o in members):
        return members[0],'VISIT_ALREADY_ASSIGNED'
    for o in members:
        if m.case_return_is_open(o.id): return members[0],'VISIT_RETURNED_FOR_CORRECTION'
        if str(o.exam_status).upper()!='EXAM_COMPLETED' or str(o.pacs_status).upper()!='IMAGES_COMPLETE':
            return members[0],'VISIT_EXAMS_NOT_COMPLETE'
        if str(o.status).upper() in ('FINAL','CANCELLED') or (o.report and str(o.report.status).upper() in ('VERIFIED','FINAL')):
            return members[0],'VISIT_LIFECYCLE_LOCKED'
        if not m.assignment_readiness_decision(o)['allowed']: return members[0],'VISIT_NOT_READY'
    return members[0],None


def prefer_visit_doctor(order,candidates):
    from application.legacy_runtime import resolve_runtime as _rb_runtime; m = _rb_runtime()
    if not order.assignment_visit_id or not candidates: return candidates
    visit=m.AssignmentVisit.query.filter_by(id=order.assignment_visit_id).first()
    if not visit or visit.patient_id!=order.patient_id or visit.branch_id!=order.branch_id:
        return []  # Never cross a mismatched patient/branch boundary.
    siblings=group_members(order)
    preferred=[]
    if visit.preferred_doctor_id: preferred.append(visit.preferred_doctor_id)
    for sibling in siblings:
        if sibling.assigned_doctor_id: preferred.append(sibling.assigned_doctor_id)
        pending=m.AssignmentOffer.query.filter_by(order_id=sibling.id,status='PENDING').order_by(m.AssignmentOffer.id.desc()).first()
        if pending: preferred.append(pending.doctor_user_id)
    modalities={str(s.modality).upper() for s in siblings}
    def covers_visit(user):
        profile=m.DoctorAssignmentProfile.query.filter_by(user_id=user.id).first()
        allowed={x.strip().upper() for x in (profile.modalities or '').split(',') if x.strip()} if profile else set()
        return not allowed or modalities.issubset(allowed)
    preferred=list(dict.fromkeys(preferred))
    from assignment_distribution import active_case_count, case_capacity
    candidates=[u for u in candidates if covers_visit(u) and active_case_count(u.id)+len(siblings)<=case_capacity(u.id)]
    positions={u.id:i for i,u in enumerate(candidates)}
    return sorted(candidates,key=lambda u:(0 if u.id in preferred else 1,
        preferred.index(u.id) if u.id in preferred else 0,
        0 if covers_visit(u) else 1,positions[u.id]))


def assign_visit_atomically(**kwargs):
    from application.legacy_runtime import resolve_runtime as _rb_runtime; m = _rb_runtime()
    from case_assignment_service import assign_case_atomically, CaseAssignmentServiceError, _assert_assignable_lifecycle
    from assignment_distribution import AUTO_TYPES, policy_snapshot, case_capacity, active_case_count, start_timeout_seconds
    order=m.db.session.get(m.Order,kwargs['order_id'])
    if not order: raise CaseAssignmentServiceError('ORDER_NOT_FOUND')
    members=group_members(order,lock=True)
    if len(members)==1: return assign_case_atomically(**kwargs)
    doctor=m.User.query.filter_by(id=kwargs['doctor_user_id']).populate_existing().with_for_update().first()
    if not doctor: raise CaseAssignmentServiceError('ASSIGNMENT_DOCTOR_NOT_FOUND')
    profile=m.DoctorAssignmentProfile.query.filter_by(user_id=doctor.id).first()
    modalities={x.strip().upper() for x in (profile.modalities or '').split(',') if x.strip()} if profile else set()
    branches={x.strip() for x in (profile.branches or '').split(',') if x.strip()} if profile else set()
    if any((modalities and o.modality.upper() not in modalities) or (branches and str(o.branch_id) not in branches) for o in members):
        raise CaseAssignmentServiceError('VISIT_DOCTOR_NOT_QUALIFIED_FOR_ALL_EXAMS')
    from assignment_distribution import validate_special_doctor
    for o in members:
        _assert_assignable_lifecycle(m.db.session,m.Report,o)
        validate_special_doctor(o,doctor)
    new_count=sum(o.assigned_doctor_id!=doctor.id for o in members)
    if active_case_count(doctor.id)+new_count>case_capacity(doctor.id):
        raise CaseAssignmentServiceError('VISIT_DOCTOR_CAPACITY_REACHED')
    if kwargs.get('assignment_type') in AUTO_TYPES:
        _,reason=visit_ready_for_offer(order)
        if reason: raise CaseAssignmentServiceError(reason)
    results=[]
    for o in members:
        args=dict(kwargs,order_id=o.id)
        results.append(assign_case_atomically(**args))
    # A visit has one start deadline: use the longest member deadline.
    deadlines=[r.assignment.start_deadline_at for r in results if r.assignment.start_deadline_at]
    if deadlines:
        deadline=max(deadlines)
        for r in results:
            r.assignment.start_deadline_at=deadline
            r.assignment.start_timeout_seconds=int((deadline-r.assignment.assigned_at).total_seconds())
    m.db.session.flush()
    return next(r for r in results if r.order.id==order.id)
