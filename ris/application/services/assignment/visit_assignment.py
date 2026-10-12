"""Grouped-visit assignment over explicit evidence and transaction ports."""
import uuid
from dataclasses import dataclass
from typing import Callable
from application.services.assignment.assignment_transaction import (
    CaseAssignmentServiceError, assert_assignable_order, assert_assignable_lifecycle,
)


@dataclass(frozen=True)
class VisitPolicies:
    case_return_is_open: Callable
    readiness_decision: Callable
    active_case_count: Callable
    case_capacity: Callable
    validate_special_doctor: Callable
    assign_case_atomically: Callable
    automatic_types: frozenset


class VisitAssignmentService:
    def __init__(self, repository, policies):
        self.repository, self.policies = repository, policies

    def create_visit(self, patient_id, branch_id, scheduled):
        return self.repository.new_visit(str(uuid.uuid4()), patient_id, branch_id, scheduled.date())

    def group_members(self, order, lock=False):
        if not getattr(order,'assignment_visit_id',None):
            return [order]
        visit=self.repository.find_visit(order.assignment_visit_id)
        if not visit or visit.patient_id!=order.patient_id or visit.branch_id!=order.branch_id:
            raise ValueError('VISIT_PATIENT_BRANCH_MISMATCH')
        if lock: self.repository.lock_visit(visit)
        rows=self.repository.visit_orders(visit.id, lock)
        if any(o.patient_id!=visit.patient_id or o.branch_id!=visit.branch_id for o in rows):
            raise ValueError('VISIT_PATIENT_BRANCH_MISMATCH')
        sources=set()
        for member in rows:
            sources.add(self.repository.source_of(member.id))
        if len(sources)>1: raise ValueError('VISIT_SOURCE_CENTER_MISMATCH')
        return rows

    def visit_ready_for_offer(self, order):
        members=self.group_members(order,lock=True)
        visit=self.repository.find_visit(order.assignment_visit_id) if order.assignment_visit_id else None
        if visit:
            if visit.assignment_mode=='MANUAL': return members[0],'VISIT_MANUAL_RESERVATION'
            if visit.registration_open: return members[0],'VISIT_REGISTRATION_OPEN'
            if self.repository.open_booking(visit.id):
                return members[0],'VISIT_BOOKINGS_NOT_CHECKED_IN'
        if len(members)==1: return members[0],None
        if any(o.assigned_doctor_id for o in members):
            return members[0],'VISIT_ALREADY_ASSIGNED'
        for o in members:
            if self.policies.case_return_is_open(o.id): return members[0],'VISIT_RETURNED_FOR_CORRECTION'
            if str(o.exam_status).upper()!='EXAM_COMPLETED' or str(o.pacs_status).upper()!='IMAGES_COMPLETE':
                return members[0],'VISIT_EXAMS_NOT_COMPLETE'
            if str(o.status).upper() in ('FINAL','CANCELLED') or (o.report and str(o.report.status).upper() in ('VERIFIED','FINAL')):
                return members[0],'VISIT_LIFECYCLE_LOCKED'
            if not self.policies.readiness_decision(o)['allowed']: return members[0],'VISIT_NOT_READY'
        return members[0],None

    def prefer_visit_doctor(self, order,candidates):
        if not order.assignment_visit_id or not candidates: return candidates
        visit=self.repository.find_visit(order.assignment_visit_id)
        if not visit or visit.patient_id!=order.patient_id or visit.branch_id!=order.branch_id:
            return []  # Never cross a mismatched patient/branch boundary.
        siblings=self.group_members(order)
        preferred=[]
        if visit.preferred_doctor_id: preferred.append(visit.preferred_doctor_id)
        for sibling in siblings:
            if sibling.assigned_doctor_id: preferred.append(sibling.assigned_doctor_id)
            pending=self.repository.latest_pending_offer(sibling.id)
            if pending: preferred.append(pending.doctor_user_id)
        modalities={str(s.modality).upper() for s in siblings}
        def covers_visit(user):
            profile=self.repository.doctor_profile(user.id)
            allowed={x.strip().upper() for x in (profile.modalities or '').split(',') if x.strip()} if profile else set()
            return not allowed or modalities.issubset(allowed)
        preferred=list(dict.fromkeys(preferred))
        candidates=[u for u in candidates if covers_visit(u) and self.policies.active_case_count(u.id)+len(siblings)<=self.policies.case_capacity(u.id)]
        positions={u.id:i for i,u in enumerate(candidates)}
        return sorted(candidates,key=lambda u:(0 if u.id in preferred else 1,
            preferred.index(u.id) if u.id in preferred else 0,
            0 if covers_visit(u) else 1,positions[u.id]))

    def assign_visit_atomically(self, **kwargs):
        order=self.repository.get_order(kwargs['order_id'])
        if not order: raise CaseAssignmentServiceError('ORDER_NOT_FOUND')
        members=self.group_members(order,lock=True)
        if len(members)==1: return self.policies.assign_case_atomically(**kwargs)
        doctor=self.repository.lock_doctor(kwargs['doctor_user_id'])
        if not doctor: raise CaseAssignmentServiceError('ASSIGNMENT_DOCTOR_NOT_FOUND')
        profile=self.repository.doctor_profile(doctor.id)
        modalities={x.strip().upper() for x in (profile.modalities or '').split(',') if x.strip()} if profile else set()
        branches={x.strip() for x in (profile.branches or '').split(',') if x.strip()} if profile else set()
        if any((modalities and o.modality.upper() not in modalities) or (branches and str(o.branch_id) not in branches) for o in members):
            raise CaseAssignmentServiceError('VISIT_DOCTOR_NOT_QUALIFIED_FOR_ALL_EXAMS')
        for o in members:
            assert_assignable_order(o)
            assert_assignable_lifecycle(o, self.repository.lock_report(o))
            self.policies.validate_special_doctor(o,doctor)
        new_count=sum(o.assigned_doctor_id!=doctor.id for o in members)
        if self.policies.active_case_count(doctor.id)+new_count>self.policies.case_capacity(doctor.id):
            raise CaseAssignmentServiceError('VISIT_DOCTOR_CAPACITY_REACHED')
        if kwargs.get('assignment_type') in self.policies.automatic_types:
            _,reason=self.visit_ready_for_offer(order)
            if reason: raise CaseAssignmentServiceError(reason)
        results=[]
        for o in members:
            args=dict(kwargs,order_id=o.id)
            results.append(self.policies.assign_case_atomically(**args))
        # A visit has one start deadline: use the longest member deadline.
        deadlines=[r.assignment.start_deadline_at for r in results if r.assignment.start_deadline_at]
        if deadlines:
            deadline=max(deadlines)
            for r in results:
                r.assignment.start_deadline_at=deadline
                r.assignment.start_timeout_seconds=int((deadline-r.assignment.assigned_at).total_seconds())
        self.repository.flush()
        return next(r for r in results if r.order.id==order.id)
