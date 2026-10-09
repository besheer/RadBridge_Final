"""Withdraw an entire unstarted automatic visit, under one shared visit lock."""
from datetime import datetime


def expire_unstarted_assignments(now=None,limit=100):
    import app as m
    from assignment_distribution import policy_snapshot, AUTO_TYPES
    from assignment_visit_grouping import group_members
    from report_edit_control import get_active_lease
    now=now or datetime.utcnow()
    result={'withdrawn':0,'protected':0}
    if not policy_snapshot()['reclaim_enabled']: return result
    ids=[r[0] for r in m.db.session.query(m.CaseAssignment.order_id).filter(
        m.CaseAssignment.active.is_(True),m.CaseAssignment.assignment_type.in_(AUTO_TYPES),
        m.CaseAssignment.start_deadline_at<=now,m.CaseAssignment.reading_started_at.is_(None))
        .order_by(m.CaseAssignment.start_deadline_at).limit(limit).all()]
    seen=set()
    for oid in ids:
        probe=m.db.session.get(m.Order,oid)
        if not probe: continue
        key=probe.assignment_visit_id or f'order:{oid}'
        if key in seen: continue
        seen.add(key)
        members=group_members(probe,lock=True)
        # Ungrouped cases still acquire the same order-first lock.
        if len(members)==1:
            members=[m.Order.query.filter_by(id=oid).populate_existing().with_for_update().first()]
        assignments=[];protected=False
        for order in members:
            report=m.Report.query.filter_by(order_id=order.id).populate_existing().with_for_update().first()
            assignment=m.CaseAssignment.query.filter_by(order_id=order.id,active=True).populate_existing().with_for_update().first()
            if not assignment or assignment.assignment_type not in AUTO_TYPES or not assignment.start_deadline_at or assignment.start_deadline_at>now or assignment.reading_started_at or order.assigned_doctor_id!=assignment.doctor_user_id:
                protected=True
            if str(order.status).upper() in ('FINAL','CANCELLED') or (report and str(report.status).upper() in ('VERIFIED','FINAL')):
                protected=True
            if report and (str(report.findings or '').strip() or str(report.impression or '').strip() or m.ReportVersion.query.filter_by(report_id=report.id).first()):
                protected=True
            if get_active_lease(m.db,order.id) or m.case_return_is_open(order.id): protected=True
            assignments.append(assignment)
        owners={a.doctor_user_id for a in assignments if a}
        if len(owners)!=1: protected=True
        if protected:
            for a in assignments:
                if a and a.assignment_type in AUTO_TYPES: a.reading_started_at=a.reading_started_at or now
            result['protected']+=1
            continue
        for order,assignment in zip(members,assignments):
            doctor_id=assignment.doctor_user_id
            assignment.active=False;assignment.unassigned_at=now
            order.assigned_doctor_id=None;order.assigned_at=None
            m.db.session.add(m.AssignmentOffer(order_id=order.id,doctor_user_id=doctor_id,status='START_TIMEOUT',attempt_no=0,
                offered_at=assignment.assigned_at,expires_at=assignment.start_deadline_at,responded_at=now,
                response_note='Automatic visit withdrawn before reading started'))
            m.db.session.add(m.AssignmentEscalationEvent(order_id=order.id,event_type='START_TIMEOUT',details=f'assignment={assignment.id};doctor={doctor_id};visit={order.assignment_visit_id or "single"}'))
            m.db.session.add(m.AuditLog(username='SYSTEM',action='CASE_START_TIMEOUT',entity='order',entity_id=str(order.id),details=f'assignment={assignment.id};doctor={doctor_id};no report changes',ip=''))
        anchor=members[0];doctor_id=next(iter(owners))
        for role,user_id,title in [('COORDINATOR',None,'Unstarted visit returned for distribution'),('',doctor_id,'Automatic assignment expired')]:
            m.db.session.add(m.RISNotification(order_id=anchor.id,branch_id=anchor.branch_id,event_type='CASE_START_TIMEOUT',title=title,
                body='The entire automatic visit was withdrawn because reading had not started before its deadline.',severity='WARNING',role_code=role,user_id=user_id,status='NEW'))
        m.db.session.flush()
        m.offer_next_doctor(anchor)
        result['withdrawn']+=1
    m.db.session.commit()
    return result
