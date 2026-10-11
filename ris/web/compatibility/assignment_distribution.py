"""Fair assignment and start deadlines. All mutations share the order row lock."""
import json
from datetime import datetime, timedelta
from sqlalchemy import func
from domain.assignment.distribution import start_timeout_seconds, CandidateFacts, rank_candidate_facts

AUTO_TYPES = frozenset({'AUTO', 'AUTO_DIRECT', 'AUTO_OFFER'})
SELECTION_MODES = frozenset({'LEAST_ACTIVE', 'ROUND_ROBIN', 'LONGEST_WAITING'})
DEFAULT_RULES = [
    {'modality': '*', 'priority': '*', 'min_images': 0, 'minutes': 10},
    {'modality': 'CR', 'priority': '*', 'min_images': 0, 'minutes': 5},
    {'modality': 'DX', 'priority': '*', 'min_images': 0, 'minutes': 5},
    {'modality': 'CT', 'priority': '*', 'min_images': 0, 'minutes': 10},
    {'modality': 'CT', 'priority': '*', 'min_images': 500, 'minutes': 15},
    {'modality': 'MR', 'priority': '*', 'min_images': 0, 'minutes': 20},
]


def policy_snapshot():
    return _queries().policy_snapshot()




def active_case_count(doctor_id):
    return _queries().active_case_count(doctor_id)


def case_capacity(doctor_id, policy=None):
    return _queries().case_capacity(doctor_id, policy)


def special_doctor_pool(order,policy=None):
    """Match operator tags, emergency priority or procedure names, then intersect pools."""
    policy=policy or policy_snapshot()
    code=str(getattr(order,'assignment_special_code','') or '').upper()
    matched=[]
    for rule in policy.get('special_rules',[]):
        if not rule['enabled']: continue
        patterns=[p.strip().upper() for p in rule['procedure_pattern'].split(',') if p.strip()]
        tagged=bool(code and code==rule['code'])
        automatic=(rule['priority'] in ('*',str(order.priority or 'ROUTINE').upper())
                   and (not patterns or any(p in str(order.procedure or '').upper() for p in patterns)))
        if tagged or automatic: matched.append(set(rule['doctor_ids']))
    if code and not any(r['enabled'] and r['code']==code for r in policy.get('special_rules',[])):
        return set()
    return set.intersection(*matched) if matched else None


def validate_special_doctor(order,doctor):
    from application.legacy_runtime import resolve_runtime as _rb_runtime; m = _rb_runtime()
    from clinical_scope import allowed
    if not allowed(m,doctor,order):
        from case_assignment_service import CaseAssignmentServiceError
        raise CaseAssignmentServiceError('DOCTOR_CLINICAL_SCOPE_DENIED')
    pool=special_doctor_pool(order)
    if pool is not None and doctor.id not in pool:
        from case_assignment_service import CaseAssignmentServiceError
        raise CaseAssignmentServiceError('SPECIAL_CASE_DOCTOR_NOT_QUALIFIED')


def rank_candidates(candidates, policy=None,order=None):
    """Use offered/assigned history as a cursor; pending offers reserve capacity."""
    from application.legacy_runtime import resolve_runtime as _rb_runtime; m = _rb_runtime()
    policy = policy or policy_snapshot()
    ranked = []
    now = datetime.utcnow()
    users = {}
    for index, (user, online, _old_count, weight) in enumerate(candidates):
        if order is not None:
            from assignment_visit_grouping import group_members
            from clinical_scope import allowed
            if any(not allowed(m,user,o) for o in group_members(order)):continue
            pools=[special_doctor_pool(o,policy) for o in group_members(order)]
            if any(pool is not None and user.id not in pool for pool in pools): continue
        active = active_case_count(user.id)
        offers=m.AssignmentOffer.query.filter_by(doctor_user_id=user.id,status='PENDING').filter(m.AssignmentOffer.expires_at>now).all()
        from assignment_visit_grouping import group_members
        pending=sum(len(group_members(offer.order)) for offer in offers)
        capacity = case_capacity(user.id, policy)
        if active + pending >= capacity:
            continue
        assigned = m.db.session.query(func.max(m.CaseAssignment.assigned_at)).filter_by(doctor_user_id=user.id).scalar()
        offered = m.db.session.query(func.max(m.AssignmentOffer.offered_at)).filter_by(doctor_user_id=user.id).scalar()
        last_turn = max(assigned or datetime.min, offered or datetime.min)
        users[index] = user
        ranked.append(CandidateFacts(index, user.id, online, active, pending, capacity, last_turn, weight))
    return [users[index] for index in rank_candidate_facts(ranked, policy['selection_mode'])]



def prepare_auto_assignment(order, doctor, assignment_type, now):
    """Called after order/doctor locks, before replacing any assignment."""
    if assignment_type not in AUTO_TYPES:
        return {}
    from case_assignment_service import CaseAssignmentServiceError
    policy = policy_snapshot()
    if active_case_count(doctor.id) >= case_capacity(doctor.id, policy):
        raise CaseAssignmentServiceError('ASSIGNMENT_DOCTOR_CAPACITY_REACHED')
    timeout = start_timeout_seconds(policy, order.modality, order.priority, order.pacs_image_count)
    return {'start_deadline_at': now + timedelta(seconds=timeout) if policy['reclaim_enabled'] else None,
            'start_timeout_seconds': timeout,
            'distribution_snapshot_json': json.dumps(policy, sort_keys=True)}


def mark_reading_started(order_id, user_id, now=None):
    from application.legacy_runtime import resolve_runtime as _rb_runtime; m = _rb_runtime()
    now = now or datetime.utcnow()
    order = m.db.session.get(m.Order,order_id)
    if not order or order.assigned_doctor_id != user_id:
        return False
    from assignment_visit_grouping import group_members
    for member in group_members(order,lock=True):
        if member.assigned_doctor_id!=user_id: return False
    for member in group_members(order):
        assignment = m.CaseAssignment.query.filter_by(order_id=member.id, active=True, doctor_user_id=user_id).populate_existing().with_for_update().first()
        if not assignment: return False
        if assignment.reading_started_at is None:
            assignment.reading_started_at=now
            m.db.session.add(m.AssignmentEscalationEvent(order_id=member.id,event_type='READING_STARTED',details=f'assignment={assignment.id};doctor={user_id}',created_by=user_id))
    return True


def expire_unstarted_assignments(now=None,limit=100):
    from assignment_deadline_worker import expire_unstarted_assignments as run
    return run(now=now,limit=limit)


def _queries():
    # Only this compatibility edge resolves the current clinical runtime.
    from application.legacy_runtime import resolve_runtime
    from application.services.assignment.assignment_queries import AssignmentQueries
    from infrastructure.adapters.assignment.query_repository import SqlAlchemyAssignmentQueryRepository
    m = resolve_runtime()
    repository = SqlAlchemyAssignmentQueryRepository(
        session=m.db.session, Policy=m.AssignmentDistributionPolicy,
        Profile=m.DoctorAssignmentProfile, Assignment=m.CaseAssignment,
        Order=m.Order, Report=m.Report)
    return AssignmentQueries(repository, DEFAULT_RULES)
