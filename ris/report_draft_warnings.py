"""Read-only draft notices. Never reject, refresh PACS, or mutate report state."""
from datetime import datetime
from flask import request


MESSAGES = {
    'EXAM_NOT_COMPLETED': ('الفحص لم يُنهَ بعد.', 'The examination is not completed yet.'),
    'READINESS_NOT_CHECKED': ('لم تُفحص جاهزية الحالة بعد.', 'Case readiness has not been checked.'),
    'READINESS_STALE': ('فحص الجاهزية قديم؛ أعد التحقق من الحالة.', 'Readiness is outdated; recheck the case.'),
    'MISSING_HISTORY': ('التاريخ المرضي المطلوب غير مكتمل.', 'Required clinical history is incomplete.'),
    'MISSING_ATTACHMENTS': ('المرفقات المطلوبة غير مكتملة.', 'Required attachments are incomplete.'),
    'MISSING_PACS': ('آخر تحقق لم يؤكد توفر صور PACS.', 'The last check did not confirm PACS images.'),
    'INCOMPLETE_IMAGES': ('عدد الصور أقل من المطلوب في آخر تحقق.', 'The last checked image count is below the required minimum.'),
    'MISSING_SERIES': ('السلاسل المطلوبة غير مكتملة في آخر تحقق.', 'Required series were incomplete at the last check.'),
    'READINESS_BLOCKED': ('آخر فحص جاهزية يحتاج مراجعة؛ راجع تفاصيل الحالة.', 'The last readiness check requires review; see case details.'),
    'READINESS_UNAVAILABLE': ('تعذر قراءة الجاهزية؛ هذا التنبيه لا يمنع حفظ المسودة.', 'Readiness could not be read; this notice does not block draft saving.'),
}


def notice(code):
    ar,en=MESSAGES[code]
    return {'code':code,'message_ar':ar,'message_en':en,'blocking':False}


def build_warnings(order,row,now=None):
    codes=[]
    if (getattr(order,'exam_status','') or '').upper() not in ('EXAM_COMPLETED','REPORTING'):
        codes.append('EXAM_NOT_COMPLETED')
    if row is None:
        codes.append('READINESS_NOT_CHECKED')
    else:
        now=now or datetime.utcnow()
        checked=getattr(row,'checked_at',None)
        if not checked or (now-checked).total_seconds()>300:
            codes.append('READINESS_STALE')
        for field,code in [('missing_history','MISSING_HISTORY'),('missing_attachments','MISSING_ATTACHMENTS'),
                           ('missing_pacs','MISSING_PACS'),('incomplete_images','INCOMPLETE_IMAGES'),
                           ('missing_series','MISSING_SERIES')]:
            if getattr(row,field,False):codes.append(code)
        if (getattr(row,'status','') or '').upper()!='READY' and not any(
                code in codes for code in ('MISSING_HISTORY','MISSING_ATTACHMENTS','MISSING_PACS','INCOMPLETE_IMAGES','MISSING_SERIES')):
            codes.append('READINESS_BLOCKED')
    return [notice(code) for code in codes]


def snapshot(m,order):
    try:
        row=m.CaseReadiness.query.filter_by(order_id=order.id).first()
        return build_warnings(order,row)
    except Exception:
        return [notice('READINESS_UNAVAILABLE')]


def register(m):
    post_endpoints={'api_ohif_report_draft','api_ohif_report_word_draft',
                    'api_ohif_onlyoffice_commit_draft','api_reporting_draft'}

    @m.app.after_request
    def enrich_draft_response(response):
        if request.method!='POST' or request.endpoint not in post_endpoints:
            return response
        if not response.is_json or not 200<=response.status_code<300:
            return response
        payload=response.get_json(silent=True)
        if not isinstance(payload,dict) or payload.get('ok') is not True:
            return response
        try:
            args=request.view_args or {}
            order=(m.db.session.get(m.Order,args['order_id']) if 'order_id' in args else
                   m.Order.query.filter_by(accession=args.get('accession')).first())
            warnings=snapshot(m,order) if order else [notice('READINESS_UNAVAILABLE')]
        except Exception:
            warnings=[notice('READINESS_UNAVAILABLE')]
        payload['draft_warnings']=warnings
        response.set_data(m.app.json.dumps(payload))
        response.headers['Cache-Control']='no-store'
        response.headers.pop('ETag',None)
        return response

    @m.app.context_processor
    def editor_warnings():
        if request.endpoint!='report_editor':return {}
        try:
            order=m.db.session.get(m.Order,(request.view_args or {}).get('order_id'))
            return {'draft_warnings':snapshot(m,order)} if order else {}
        except Exception:
            return {'draft_warnings':[notice('READINESS_UNAVAILABLE')]}
    return enrich_draft_response
