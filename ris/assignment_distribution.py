"""Fair assignment and start deadlines. All mutations share the order row lock."""
import json
from datetime import datetime, timedelta
from sqlalchemy import func

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
    import app as m
    row = m.AssignmentDistributionPolicy.query.filter_by(id=1).first()
    if row is None:
        return dict(selection_mode='LEAST_ACTIVE', max_active_cases=20,
                    reclaim_enabled=True, urgent_percent=50, stat_percent=25,
                    rules=DEFAULT_RULES, special_rules=[], version_no=0)
    return dict(selection_mode=row.selection_mode, max_active_cases=row.max_active_cases,
                reclaim_enabled=row.reclaim_enabled, urgent_percent=row.urgent_percent,
                stat_percent=row.stat_percent, rules=json.loads(row.rules_json),
                special_rules=json.loads(row.special_rules_json or '[]'), version_no=row.version_no)


def start_timeout_seconds(policy, modality, priority, images):
    modality = str(modality or '').upper()
    priority = str(priority or 'ROUTINE').upper()
    matched = [r for r in policy['rules']
               if r['modality'] in ('*', modality)
               and r['priority'] in ('*', priority)
               and int(r['min_images']) <= int(images or 0)]
    if not matched:
        raise ValueError('START_DEADLINE_RULE_MISSING')
    rule = max(matched, key=lambda r: (r['priority'] != '*', r['modality'] != '*', r['min_images']))
    percent = 100
    if rule['priority'] == '*':
        percent = policy['stat_percent'] if priority == 'STAT' else policy['urgent_percent'] if priority == 'URGENT' else 100
    return max(60, int(rule['minutes']) * 60 * int(percent) // 100)


def active_case_count(doctor_id):
    import app as m
    return (m.db.session.query(m.CaseAssignment)
            .join(m.Order, m.Order.id == m.CaseAssignment.order_id)
            .outerjoin(m.Report, m.Report.order_id == m.Order.id)
            .filter(m.CaseAssignment.doctor_user_id == doctor_id,
                    m.CaseAssignment.active.is_(True),
                    func.upper(m.Order.status).notin_(['FINAL', 'CANCELLED']),
                    func.upper(func.coalesce(m.Report.status, '')).notin_(['VERIFIED', 'FINAL']))
            .count())


def case_capacity(doctor_id, policy=None):
    import app as m
    policy = policy or policy_snapshot()
    prof = m.DoctorAssignmentProfile.query.filter_by(user_id=doctor_id).first()
    return min(int(policy['max_active_cases']), int(prof.max_active_cases or 20) if prof else 20)


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
    pool=special_doctor_pool(order)
    if pool is not None and doctor.id not in pool:
        from case_assignment_service import CaseAssignmentServiceError
        raise CaseAssignmentServiceError('SPECIAL_CASE_DOCTOR_NOT_QUALIFIED')


def rank_candidates(candidates, policy=None,order=None):
    """Use offered/assigned history as a cursor; pending offers reserve capacity."""
    import app as m
    policy = policy or policy_snapshot()
    ranked = []
    now = datetime.utcnow()
    for user, online, _old_count, weight in candidates:
        if order is not None:
            from assignment_visit_grouping import group_members
            pools=[special_doctor_pool(o,policy) for o in group_members(order)]
            if any(pool is not None and user.id not in pool for pool in pools): continue
        active = active_case_count(user.id)
        offers=m.AssignmentOffer.query.filter_by(doctor_user_id=user.id,status='PENDING').filter(m.AssignmentOffer.expires_at>now).all()
        from assignment_visit_grouping import group_members
        pending=sum(len(group_members(offer.order)) for offer in offers)
        if active + pending >= case_capacity(user.id, policy):
            continue
        assigned = m.db.session.query(func.max(m.CaseAssignment.assigned_at)).filter_by(doctor_user_id=user.id).scalar()
        offered = m.db.session.query(func.max(m.AssignmentOffer.offered_at)).filter_by(doctor_user_id=user.id).scalar()
        last_turn = max(assigned or datetime.min, offered or datetime.min)
        if policy['selection_mode'] == 'ROUND_ROBIN':
            key = (last_turn, user.id)
        elif policy['selection_mode'] == 'LONGEST_WAITING':
            key = (0 if online else 1, last_turn, user.id)
        else:
            key = (0 if online else 1, active + pending, last_turn, -weight, user.id)
        ranked.append((key, user))
    return [user for _, user in sorted(ranked, key=lambda item: item[0])]


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
    import app as m
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
