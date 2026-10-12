"""Manual course linking barriers; never infer identity from a patient name."""


class RTWorkflowError(Exception):
    def __init__(self, code):
        self.code=code
        super().__init__(code)


def require_version(course, expected):
    try: value=int(expected)
    except (ValueError,TypeError): raise RTWorkflowError('INVALID_COURSE_VERSION') from None
    if value!=course.version: raise RTWorkflowError('STALE_COURSE_VERSION')


def require_pet_link(course, order):
    if (order.patient_id!=course.patient_id or order.branch_id!=course.branch_id
            or str(order.modality or '').upper()!='PT' or order.status=='CANCELLED'):
        raise RTWorkflowError('PET_LINK_IDENTITY_MISMATCH')
