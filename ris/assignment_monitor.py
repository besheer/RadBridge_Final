"""Read-only assignment monitoring; never creates presence or policy rows."""
from datetime import datetime, timedelta


def snapshot(now=None):
    import app as m
    from assignment_distribution import policy_snapshot, case_capacity, AUTO_TYPES
    now = now or datetime.utcnow()
    policy = policy_snapshot()
    doctors = m.assignable_doctors()
    profiles = {p.user_id: p for p in m.DoctorAssignmentProfile.query.all()}
    presence = {p.user_id: p for p in m.DoctorAvailabilityState.query.all()}
    assignments = {a.order_id: a for a in m.CaseAssignment.query.filter_by(active=True).all()}
    orders = m.Order.query.filter(m.Order.status.notin_(['FINAL', 'CANCELLED'])).order_by(m.Order.scheduled).all()
    ids = [o.id for o in orders]
    reports = {r.order_id: r for r in m.Report.query.filter(m.Report.order_id.in_(ids)).all()} if ids else {}
    orders = [o for o in orders if not reports.get(o.id) or reports[o.id].status not in ('VERIFIED', 'FINAL')]
    by_id = {o.id: o for o in orders}
    offers = m.AssignmentOffer.query.filter_by(status='PENDING').order_by(m.AssignmentOffer.offered_at).all()
    offers = [f for f in offers if f.order_id in by_id]
    visit_counts = {}
    for o in orders:
        key = o.assignment_visit_id or ('order', o.id)
        visit_counts[key] = visit_counts.get(key, 0) + 1
    cases = []
    for o in orders:
        a = assignments.get(o.id)
        owned = bool(a and a.doctor_user_id == o.assigned_doctor_id)
        started = a.reading_started_at if owned else None
        manual = bool(owned and a.assignment_type not in AUTO_TYPES)
        deadline = a.start_deadline_at if owned and not manual and not started else None
        remaining = int((deadline - now).total_seconds()) if deadline else None
        cases.append(dict(order=o, assignment=a if owned else None, started=started,
                          manual=manual, deadline=deadline, remaining=remaining,
                          overdue=bool(deadline and deadline <= now and policy['reclaim_enabled']),
                          linked=visit_counts[o.assignment_visit_id or ('order', o.id)] > 1,
                          visit_count=visit_counts[o.assignment_visit_id or ('order', o.id)]))
    rows = []
    for doctor in doctors:
        state = presence.get(doctor.id)
        p = profiles.get(doctor.id)
        owned_cases = [c for c in cases if c['order'].assigned_doctor_id == doctor.id]
        pending = [f for f in offers if f.doctor_user_id == doctor.id]
        reserved = sum(visit_counts[by_id[f.order_id].assignment_visit_id or ('order', f.order_id)] for f in pending)
        rows.append(dict(doctor=doctor, profile=p, state=state.state if state else 'UNKNOWN',
                         online=bool(state and state.last_seen_at and state.last_seen_at >= now-timedelta(minutes=5) and state.state != 'OFFLINE'),
                         last_seen=state.last_seen_at if state else None,
                         available=bool(not p or p.available), cap=case_capacity(doctor.id, policy),
                         cases=owned_cases, active=len(owned_cases), reserved=reserved,
                         visits=len({c['order'].assignment_visit_id or ('order', c['order'].id) for c in owned_cases})))
    return dict(doctors=rows, cases=cases, offers=offers, now=now, policy=policy,
                waiting=[c for c in cases if not c['order'].assigned_doctor_id],
                overdue=[c for c in cases if c['overdue']])
