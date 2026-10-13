"""Worklist insurance readiness from the latest authoritative decision."""

def approval_blocker(required, row):
    if row is None:
        if not required:
            return ''
    elif row.status == 'APPROVED' and (row.approval_no or '').strip():
        return ''
    elif row.status == 'NOT_REQUIRED' and not required:
        return ''
    return ('Insurance approval is incomplete. An approved decision with an approval '
            'reference is required before sending Worklist. / موافقة التأمين غير مكتملة؛ '
            'يلزم تسجيل موافقة مع رقمها قبل التحويل إلى أمر شغل وإرسال Worklist.')
