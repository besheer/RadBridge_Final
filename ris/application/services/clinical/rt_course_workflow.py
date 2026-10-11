"""Manual RT course creation/PET links over explicit persistence and scope policies.

Caller owns commit/rollback. No order identity or clinical report is modified.
"""
from domain.clinical.rt_validation import text
from domain.clinical.rt_course_policy import RTWorkflowError,require_version,require_pet_link


def create_course(*, repository, authorize_order, actor_id, audit, accession, reference):
    order=repository.find_order(text(accession,1,100))
    if order is None: raise RTWorkflowError('ORDER_NOT_FOUND')
    authorize_order(order)
    if order.status=='CANCELLED': raise RTWorkflowError('ORDER_CANCELLED')
    row=repository.create_course(primary_order_id=order.id,patient_id=order.patient_id,
        branch_id=order.branch_id,reference=text(reference,1,100),created_by=actor_id())
    repository.add(row);repository.flush()
    audit('COURSE_CREATED','rt_course',row,dict(primary_order_id=order.id,source='MANUAL'))
    return row


def link_pet(*, repository, authorize_course, authorize_order, actor_id, audit,
             course_id, expected_version, accession, purpose, reason):
    course=repository.lock_course(course_id)
    if course is None: raise RTWorkflowError('COURSE_NOT_FOUND')
    authorize_course(course)
    require_version(course,expected_version)
    if course.status in ('COMPLETED','CANCELLED'): raise RTWorkflowError('COURSE_TERMINAL')
    order=repository.find_order(text(accession,1,100))
    if order is None: raise RTWorkflowError('ORDER_NOT_FOUND')
    authorize_order(order)
    require_pet_link(course,order)
    if purpose not in ('BASELINE','PLANNING_REFERENCE','FOLLOW_UP','OTHER'): raise RTWorkflowError('INVALID_PET_PURPOSE')
    row=repository.create_pet_link(course_id=course.id,order_id=order.id,purpose=purpose,
        reason=text(reason,5,1000),linked_by=actor_id())
    repository.add(row);repository.flush();course.version+=1
    audit('PET_LINKED','rt_pet_link',row,dict(course_id=course.id,order_id=order.id,purpose=purpose,reason=row.reason))
    return course,row
