"""Read-only distribution projections with explicit evidence/policy/clock ports."""
from datetime import timedelta


class AssignmentMonitoring:
    def __init__(self, repository, *, doctors, policy, capacity, auto_types, clock):
        self.repository,self.doctors,self.policy=repository,doctors,policy
        self.capacity,self.auto_types,self.clock=capacity,auto_types,clock

    def snapshot(self, now=None):
        now=now or self.clock()
        policy=self.policy()
        doctors=self.doctors()
        profiles={p.user_id:p for p in self.repository.profiles()}
        presence={p.user_id:p for p in self.repository.presence()}
        assignments={a.order_id:a for a in self.repository.active_assignments()}
        orders=self.repository.open_orders()
        ids=[o.id for o in orders]
        reports={r.order_id:r for r in self.repository.reports(ids)} if ids else {}
        orders=[o for o in orders if not reports.get(o.id) or reports[o.id].status not in ('VERIFIED','FINAL')]
        by_id={o.id:o for o in orders}
        offers=[offer for offer in self.repository.pending_offers() if offer.order_id in by_id]
        visit_counts={}
        for order in orders:
            key=order.assignment_visit_id or ('order',order.id)
            visit_counts[key]=visit_counts.get(key,0)+1
        cases=[]
        for order in orders:
            assignment=assignments.get(order.id)
            owned=bool(assignment and assignment.doctor_user_id==order.assigned_doctor_id)
            started=assignment.reading_started_at if owned else None
            manual=bool(owned and assignment.assignment_type not in self.auto_types)
            deadline=assignment.start_deadline_at if owned and not manual and not started else None
            remaining=int((deadline-now).total_seconds()) if deadline else None
            size=visit_counts[order.assignment_visit_id or ('order',order.id)]
            cases.append(dict(order=order,assignment=assignment if owned else None,started=started,
                manual=manual,deadline=deadline,remaining=remaining,
                overdue=bool(deadline and deadline<=now and policy['reclaim_enabled']),
                linked=size>1,visit_count=size))
        rows=[]
        for doctor in doctors:
            state=presence.get(doctor.id)
            profile=profiles.get(doctor.id)
            owned_cases=[case for case in cases if case['order'].assigned_doctor_id==doctor.id]
            pending=[offer for offer in offers if offer.doctor_user_id==doctor.id]
            reserved=sum(visit_counts[by_id[offer.order_id].assignment_visit_id or ('order',offer.order_id)] for offer in pending)
            rows.append(dict(doctor=doctor,profile=profile,state=state.state if state else 'UNKNOWN',
                online=bool(state and state.last_seen_at and state.last_seen_at>=now-timedelta(minutes=5) and state.state!='OFFLINE'),
                last_seen=state.last_seen_at if state else None,
                available=bool(not profile or profile.available),cap=self.capacity(doctor.id,policy),
                cases=owned_cases,active=len(owned_cases),reserved=reserved,
                visits=len({case['order'].assignment_visit_id or ('order',case['order'].id) for case in owned_cases})))
        return dict(doctors=rows,cases=cases,offers=offers,now=now,policy=policy,
                    waiting=[case for case in cases if not case['order'].assigned_doctor_id],
                    overdue=[case for case in cases if case['overdue']])
