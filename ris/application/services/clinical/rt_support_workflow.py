"""RT course state, notes and consumable records over explicit dependencies."""
from domain.clinical.rt_validation import text,amount
from domain.clinical.rt_course_policy import RTWorkflowError,require_version
from application.services.clinical import rt_scope_context


def change_state(*, repository, policies, course_id, expected_version, target, reason):
    course=rt_scope_context.course(repository,policies.authorize_course,course_id)
    require_version(course,expected_version)
    reason=text(reason,5,1000)
    allowed={'DRAFT':{'CANCELLED'},'ACTIVE':{'PAUSED','COMPLETED','CANCELLED'},'PAUSED':{'ACTIVE','CANCELLED'}}
    if target not in allowed.get(course.status,set()): raise RTWorkflowError('COURSE_STATE_CONFLICT')
    if target in ('CANCELLED','COMPLETED') and repository.started_fraction(course.id):
        raise RTWorkflowError('COURSE_STATE_CONFLICT')
    if target=='COMPLETED':
        plan=repository.current_plan(course.id)
        completed=repository.completed_count(course.id)
        if not plan or completed!=plan.fractions: raise RTWorkflowError('COURSE_STATE_CONFLICT')
    previous=course.status;course.status=target;course.version+=1
    policies.audit('COURSE_STATE','rt_course',course,dict(**{'from':previous},to=target,reason=reason))
    return course


def add_note(*, repository, policies, course_id, kind, body, fraction_id=None):
    course=rt_scope_context.course(repository,policies.authorize_course,course_id)
    if course.status in ('COMPLETED','CANCELLED'): raise RTWorkflowError('COURSE_TERMINAL')
    if kind not in ('PREPARATION','NURSING','TECHNICAL','CLINICAL'): raise RTWorkflowError('INVALID_NOTE_KIND')
    if fraction_id:
        row=repository.fraction(fraction_id)
        if row is None: raise RTWorkflowError('FRACTION_NOT_FOUND')
        if row.course_id!=course.id: raise RTWorkflowError('NOTE_FRACTION_MISMATCH')
        rt_scope_context.fraction(repository,policies.authorize_course,policies.authorize_device,fraction_id)
    note=repository.create_note(course_id=course.id,fraction_id=fraction_id,kind=kind,
        body=text(body,1,10000),recorded_by=policies.actor_id())
    repository.add(note);repository.flush()
    policies.audit('NOTE_ADDED','rt_note',note,dict(course_id=course.id,fraction_id=fraction_id,kind=kind))
    return course,note


def add_consumable(*, repository, policies, fraction_id, name, quantity, unit):
    course,row,device=rt_scope_context.fraction(repository,policies.authorize_course,policies.authorize_device,fraction_id)
    if course.status in ('COMPLETED','CANCELLED') or row.status in ('CANCELLED','NOT_GIVEN'):
        raise RTWorkflowError('CONSUMABLE_STATE_CONFLICT')
    item=repository.create_consumable(fraction_id=row.id,name=text(name,1,150),
        quantity=amount(quantity),unit=text(unit,1,40),recorded_by=policies.actor_id())
    repository.add(item);repository.flush()
    policies.audit('CONSUMABLE_RECORDED','rt_consumable',item,dict(course_id=course.id,
        fraction_id=row.id,name=item.name,quantity=item.quantity,unit=item.unit,stock_posted=False))
    return course,item
