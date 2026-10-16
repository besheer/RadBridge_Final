"""Manual RT session commands over supplied repositories and scope policies.

Caller owns commit/rollback. Accepted completion records external/manual input;
no command controls a device or changes an RIS report or source order.
"""
from dataclasses import dataclass
from typing import Callable
from domain.clinical.rt_validation import amount,text,local_time
from domain.clinical.rt_course_policy import RTWorkflowError,require_version
from domain.clinical.rt_completion import fingerprint
from application.services.clinical import rt_scope_context


@dataclass(frozen=True)
class SessionPolicies:
    authorize_actor: Callable
    authorize_course: Callable
    authorize_device: Callable
    actor_id: Callable
    audit: Callable
    clock: Callable


def _course(repository, policies, course_id):
    return rt_scope_context.course(repository,policies.authorize_course,course_id)


def _fraction(repository, policies, fraction_id):
    return rt_scope_context.fraction(repository,policies.authorize_course,policies.authorize_device,fraction_id)


def _usable(repository, course, row, device, completing=False):
    plan=repository.current_plan(course.id)
    states=('ACTIVE','PAUSED') if completing else ('ACTIVE',)
    if course.status not in states or not plan or plan.id!=row.plan_id or row.number>plan.fractions:
        raise RTWorkflowError('SESSION_STATE_CONFLICT')
    if str(device.operational_status or '').upper() not in ('ACTIVE',''):
        raise RTWorkflowError('SESSION_STATE_CONFLICT')
    return plan


def schedule(*, repository, policies, course_id, expected_version, values, device_id):
    course=_course(repository,policies,course_id)
    require_version(course,expected_version)
    plan=repository.current_plan(course.id)
    if course.status!='ACTIVE' or not plan: raise RTWorkflowError('SESSION_STATE_CONFLICT')
    try:number=int(values.get('number',''))
    except ValueError:raise ValueError('Invalid session number / رقم جلسة غير صحيح') from None
    if not 1<=number<=plan.fractions: raise RTWorkflowError('SESSION_STATE_CONFLICT')
    device=repository.device(device_id)
    if device is None: raise RTWorkflowError('DEVICE_NOT_FOUND')
    if device.branch_id!=course.branch_id: raise RTWorkflowError('DEVICE_BRANCH_DENIED')
    policies.authorize_device(device)
    if amount(values.get('planned_gy'))!=plan.fraction_gy: raise RTWorkflowError('SESSION_STATE_CONFLICT')
    previous=repository.previous_attempt(course.id,number)
    if previous and previous.status not in ('CANCELLED','NOT_GIVEN'):
        raise RTWorkflowError('SESSION_STATE_CONFLICT')
    retry_reason=text(values.get('reason'),5,1000) if previous else ''
    row=repository.create_fraction(course_id=course.id,plan_id=plan.id,number=number,
        attempt=previous.attempt+1 if previous else 1,device_id=device.id,
        planned_gy=plan.fraction_gy,scheduled_at=local_time(values.get('scheduled_at')))
    repository.add(row);repository.flush();course.version+=1
    policies.audit('FRACTION_SCHEDULED','rt_fraction',row,dict(course_id=course.id,plan_id=plan.id,
        number=number,attempt=row.attempt,previous_attempt_id=previous.id if previous else None,
        retry_reason=retry_reason,planned_gy=row.planned_gy,device_id=device.id))
    return course,row


def reschedule(*, repository, policies, fraction_id, expected_version, values):
    course,row,device=_fraction(repository,policies,fraction_id)
    require_version(row,expected_version)
    plan=repository.current_plan(course.id)
    if course.status!='ACTIVE' or not plan or row.status!='SCHEDULED' or row.number>plan.fractions:
        raise RTWorkflowError('SESSION_STATE_CONFLICT')
    old=dict(plan_id=row.plan_id,planned_gy=row.planned_gy,scheduled_at=row.scheduled_at)
    reason=text(values.get('reason'),5,1000)
    if amount(values.get('planned_gy'))!=plan.fraction_gy: raise RTWorkflowError('SESSION_STATE_CONFLICT')
    row.plan_id=plan.id;row.planned_gy=plan.fraction_gy
    row.scheduled_at=local_time(values.get('scheduled_at'));row.version+=1
    policies.audit('FRACTION_RESCHEDULED','rt_fraction',row,
        dict(before=old,after=dict(plan_id=plan.id,planned_gy=row.planned_gy,scheduled_at=row.scheduled_at),reason=reason))
    return course,row


def start(*, repository, policies, fraction_id, expected_version):
    policies.authorize_actor()
    course,row,device=_fraction(repository,policies,fraction_id)
    require_version(row,expected_version)
    _usable(repository,course,row,device)
    if row.status!='SCHEDULED': raise RTWorkflowError('SESSION_STATE_CONFLICT')
    row.status='STARTED';row.started_at=policies.clock();row.operator_id=policies.actor_id();row.version+=1
    policies.audit('FRACTION_STARTED','rt_fraction',row,dict(course_id=course.id,plan_id=row.plan_id,source='MANUAL'))
    return course,row


def complete(*, repository, policies, fraction_id, expected_version, values):
    policies.authorize_actor()
    course,row,device=_fraction(repository,policies,fraction_id)
    actual=amount(values.get('actual_gy'))
    reference=str(values.get('delivery_reference') or '').strip()
    if len(reference)>150: raise RTWorkflowError('INVALID_COMPLETION_INPUT')
    key=text(values.get('idempotency_key'),16,80)
    variance_reason=str(values.get('dose_variance_reason') or '').strip()
    if len(variance_reason)>1000: raise RTWorkflowError('INVALID_COMPLETION_INPUT')
    payload=fingerprint(actual,reference,variance_reason)
    if row.status=='COMPLETED':
        if row.completion_key==key and row.completion_hash==payload:
            return course,row,False
        raise RTWorkflowError('COMPLETION_REPLAY_CONFLICT')
    require_version(row,expected_version)
    _usable(repository,course,row,device,completing=True)
    if row.status!='STARTED': raise RTWorkflowError('SESSION_STATE_CONFLICT')
    if actual!=row.planned_gy: variance_reason=text(variance_reason,5,1000)
    row.reason=variance_reason;row.actual_gy=actual;row.ended_at=policies.clock();row.status='COMPLETED'
    row.operator_id=policies.actor_id();row.delivery_reference=reference
    row.completion_key=key;row.completion_hash=payload;row.version+=1
    policies.audit('FRACTION_COMPLETED','rt_fraction',row,dict(course_id=course.id,plan_id=row.plan_id,
        planned_gy=row.planned_gy,actual_gy=actual,dose_variance_reason=variance_reason,
        source='MANUAL',delivery_reference=reference))
    return course,row,True


def cancel(*, repository, policies, fraction_id, expected_version, status, reason):
    course,row,device=_fraction(repository,policies,fraction_id)
    require_version(row,expected_version)
    if row.status!='SCHEDULED': raise RTWorkflowError('SESSION_STATE_CONFLICT')
    if status not in ('CANCELLED','NOT_GIVEN'): raise RTWorkflowError('INVALID_SESSION_STATUS')
    row.reason=text(reason,5,1000);row.status=status;row.version+=1
    policies.audit('FRACTION_NOT_DELIVERED','rt_fraction',row,dict(status=status,reason=row.reason))
    return course,row
