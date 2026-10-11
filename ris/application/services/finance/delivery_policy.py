"""Fail-closed evidence checks for recording physical/manual delivery."""
from pathlib import Path
from urllib.parse import quote

METHODS={'REPORT':{'IN_PERSON','EMAIL','PORTAL','WHATSAPP'},'IMAGES':{'CD','FILM','PORTAL','LINK'}}

def report_readiness(order):
    from application.legacy_runtime import resolve_runtime as _rb_runtime; m = _rb_runtime()
    report=order.report
    if not report or report.status!='FINAL':return False,'A FINAL report is required. / يجب اعتماد التقرير نهائيًا أولًا.'
    root=Path(m.REPORT_DIR).resolve()
    for raw in (report.pdf_path,report.docx_path,report.source_path):
        if not raw:continue
        try:
            path=Path(raw).resolve();path.relative_to(root)
            if not path.is_file() or path.stat().st_size==0 or path.suffix.lower() not in ('.pdf','.docx'):continue
            result=m.validate_report_patient_file(order,str(path),path.suffix)
            if result.get('result')=='MATCH':return True,''
        except Exception:
            continue
    return False,'The final report file is missing, invalid, or does not match this case. / ملف التقرير النهائي غير متاح أو غير مطابق للحالة.'

def images_readiness(order,live=False):
    from application.legacy_runtime import resolve_runtime as _rb_runtime; m = _rb_runtime()
    sid=(order.pacs_study_id or '').strip()
    if not sid:return False,'No PACS study is linked to this examination. / لا توجد دراسة صور مرتبطة بالفحص.'
    match=m.PacsStudyMatch.query.filter_by(order_id=order.id,orthanc_study_id=sid,is_current=True).first()
    if not match:return False,'The image-to-case link is not verified. / ربط الصور بالحالة غير مؤكد.'
    safe,reason=m.pacs_demographic_gate(order)
    if not safe:return False,'Image identity needs review. / هوية الصور تحتاج مراجعة.'
    if not live:
        if (order.pacs_image_count or 0)<=0 or order.pacs_status in ('PACS_OFFLINE','WAITING','ERROR'):
            return False,'No confirmed images are available. / لا توجد صور مؤكدة متاحة.'
        return True,''
    try:
        url=m.PACS_ORTHANC_URL+'/studies/'+quote(sid,safe='')
        response=m.requests.get(url,auth=m._orthanc_auth(),timeout=8);response.raise_for_status()
        study=response.json()
        patient=study.get('PatientMainDicomTags') or {};tags=study.get('MainDicomTags') or {}
        if study.get('ID')!=sid:return False,'PACS study identity changed. / تغيرت هوية دراسة الصور.'
        if match.match_method=='DEMOGRAPHICS_EXACT' and (str(patient.get('PatientID','')).strip()!=str(order.patient.patient_id or '').strip() or str(tags.get('AccessionNumber','')).strip()!=str(order.accession or '').strip()):
            return False,'PACS identity does not match this case. / هوية صور PACS لا تطابق الحالة.'
        if match.match_method in ('MANUAL_CONFIRMED','OVERRIDE_APPROVED') and (str(patient.get('PatientID','')).strip()!=str(match.pacs_patient_id or '').strip() or str(tags.get('AccessionNumber','')).strip()!=str(match.pacs_accession or '').strip()):
            return False,'The confirmed PACS identity changed. / تغيرت هوية الصور بعد تأكيد الربط.'
        response=m.requests.get(url+'/statistics',auth=m._orthanc_auth(),timeout=8);response.raise_for_status()
        count=int(response.json().get('CountInstances') or 0)
        if count<=0:return False,'The linked PACS study contains no images. / الدراسة المرتبطة لا تحتوي صورًا.'
    except Exception:
        return False,'PACS could not verify the images. Retry when PACS is available. / تعذر التحقق من الصور عبر PACS؛ حاول بعد عودة الاتصال.'
    return True,''

def delivery_readiness(order,item,live=False):
    if order.status in ('CANCELLED','REGISTERED','BOOKED'):
        return False,'This examination is not ready for delivery. / الفحص غير جاهز للتسليم.'
    if item=='REPORT':return report_readiness(order)
    if item=='IMAGES':return images_readiness(order,live=live)
    return False,'Invalid delivery item.'

def snapshot(order):
    return {item:dict(zip(('allowed','reason'),delivery_readiness(order,item))) for item in METHODS}
