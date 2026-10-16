"""Correction request/review workflows with explicit evidence and persistence."""
from dataclasses import dataclass
from typing import Callable
from domain.reporting.revision_policy import RevisionError


@dataclass(frozen=True)
class RevisionPolicies:
    reference: Callable
    check_reference: Callable
    eligible: Callable
    audit: Callable
    notify: Callable
    clock: Callable


def request_revision(repository, policies, order, user, reason, kind):
    reason=(reason or '').strip();kind=(kind or '').upper()
    if not 10<=len(reason)<=2000 or kind not in ('ADDENDUM','REPLACEMENT'):raise RevisionError('REASON')
    repository.lock_order(order.id)
    report,v,path,sha,base,base_sha=policies.reference(order)
    if repository.active_revision(order.id):raise RevisionError('ACTIVE')
    count=repository.latest_revision(order.id)
    row=repository.create_revision(order_id=order.id,original_report_id=report.id,original_version_id=v.id,
        original_sha256=sha,base_revision_id=base,base_sha256=base_sha,revision_no=(count.revision_no+1 if count else 1),
        status='REQUESTED',kind=kind,reason=reason,requested_by=user.id,active_order_id=order.id)
    repository.add(row);repository.flush()
    policies.audit(user,'REPORT_REVISION_REQUESTED',row,{}, {'status':'REQUESTED'})
    policies.notify(order,'REPORT_REVISION_REQUESTED','طلب تصحيح تقرير / Report correction request',reason,'CASE_COORDINATOR')
    return row


def review(repository, policies, row, user, action, reason, doctor_id=None):
    # Order then revision is the lock order used throughout this workflow.
    order=repository.lock_order(row.order_id)
    row=repository.lock_revision(row.id)
    reason=(reason or '').strip()
    if row.status!='REQUESTED':raise RevisionError('STATE')
    if not 10<=len(reason)<=2000:raise RevisionError('REASON')
    if action not in ('APPROVE','REJECT'):raise RevisionError('STATE')
    before={'status':row.status,'doctor_id':row.doctor_id}
    if action=='APPROVE':
        policies.check_reference(order,row)
        user_doctor=repository.get_doctor(doctor_id)
        if not policies.eligible(order,user_doctor):raise RevisionError('DOCTOR')
        row.doctor_id=user_doctor.id;row.status='DRAFT'
    else:row.status='REJECTED';row.active_order_id=None
    row.reviewed_by=user.id;row.reviewed_at=policies.clock();row.review_reason=reason
    policies.audit(user,'REPORT_REVISION_'+action,row,before,{'status':row.status,'doctor_id':row.doctor_id,'review_reason':reason})
    policies.notify(order,'REPORT_REVISION_'+action,'مراجعة تصحيح التقرير / Report correction review',reason,'RADIOLOGIST',row.requested_by)
    if row.doctor_id and row.doctor_id!=row.requested_by:
        policies.notify(order,'REPORT_REVISION_ASSIGNED','تصحيح تقرير مسند إليك / Assigned report correction',row.reason,'RADIOLOGIST',row.doctor_id)
    return row
