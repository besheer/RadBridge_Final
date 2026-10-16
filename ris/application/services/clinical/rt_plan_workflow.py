"""Record externally approved manual RT plan versions over explicit dependencies."""
from datetime import date
from domain.clinical.rt_validation import amount,text
from domain.clinical.rt_course_policy import RTWorkflowError,require_version


def record_plan(*, repository, authorize_actor, authorize_course, actor_id, audit,
                today, course_id, expected_version, values, attachment_id=None):
    authorize_actor()
    course=repository.lock_course(course_id)
    if course is None: raise RTWorkflowError('COURSE_NOT_FOUND')
    authorize_course(course)
    require_version(course,expected_version)
    if course.status in ('COMPLETED','CANCELLED') or repository.started_fraction(course.id):
        raise RTWorkflowError('PLAN_EDIT_BLOCKED')
    try:
        count=int(values.get('fractions',''))
        approved=date.fromisoformat(values.get('approved_on',''))
    except ValueError:
        raise ValueError('Invalid approval date or session count / تاريخ اعتماد أو عدد جلسات غير صحيح') from None
    if approved>today():
        raise ValueError('Approval date cannot be in the future / تاريخ الاعتماد لا يكون في المستقبل')
    if not 1<=count<=1000:
        raise ValueError('Invalid session count / عدد جلسات غير صحيح')
    last=repository.latest_delivered_fraction(course.id)
    if last and count<last.number: raise RTWorkflowError('PLAN_EDIT_BLOCKED')
    if attachment_id:
        attachment=repository.attachment(attachment_id)
        if attachment is None: raise RTWorkflowError('ATTACHMENT_NOT_FOUND')
        if attachment.patient_id!=course.patient_id or attachment.order_id!=course.primary_order_id:
            raise RTWorkflowError('PLAN_ATTACHMENT_MISMATCH')
    prior=repository.current_plan(course.id)
    revision=(repository.maximum_revision(course.id) or 0)+1
    plan=repository.create_plan(course_id=course.id,revision=revision,
        external_reference=text(values.get('external_reference'),1,150),
        approved_by=text(values.get('approved_by'),1,150),approved_on=approved,
        attachment_id=attachment_id,target=text(values.get('target'),1,1000),
        total_gy=amount(values.get('total_gy')),fraction_gy=amount(values.get('fraction_gy')),
        fractions=count,reason=text(values.get('reason'),5,1000),recorded_by=actor_id())
    if prior: prior.status='SUPERSEDED'
    repository.add(plan);repository.flush();course.version+=1
    if course.status=='DRAFT': course.status='ACTIVE'
    audit('EXTERNAL_PLAN_RECORDED','rt_plan',plan,dict(source='MANUAL',course_id=course.id,
        prior_plan_id=prior.id if prior else None,reference=plan.external_reference,
        approved_by=plan.approved_by,approved_on=plan.approved_on,total_gy=plan.total_gy,
        fraction_gy=plan.fraction_gy,fractions=plan.fractions,reason=plan.reason))
    return course,plan
