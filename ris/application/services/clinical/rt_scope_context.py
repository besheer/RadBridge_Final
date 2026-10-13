"""Shared locked RT context over supplied repositories and scope callbacks."""
from domain.clinical.rt_course_policy import RTWorkflowError


def course(repository, authorize_course, course_id):
    row=repository.lock_course(course_id)
    if row is None: raise RTWorkflowError('COURSE_NOT_FOUND')
    authorize_course(row)
    return row


def fraction(repository, authorize_course, authorize_device, fraction_id):
    preview=repository.fraction(fraction_id)
    if preview is None: raise RTWorkflowError('FRACTION_NOT_FOUND')
    parent=course(repository,authorize_course,preview.course_id)
    row=repository.lock_fraction(fraction_id)
    if row is None: raise RTWorkflowError('FRACTION_NOT_FOUND')
    device=repository.device(row.device_id)
    if not device or device.branch_id!=parent.branch_id:
        raise RTWorkflowError('FRACTION_DEVICE_MISMATCH')
    authorize_device(device)
    return parent,row,device
