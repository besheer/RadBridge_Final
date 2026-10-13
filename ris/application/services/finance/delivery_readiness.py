"""Manual delivery evidence checks through explicit read-only dependencies."""
from domain.finance.delivery_evidence import METHODS, live_study_identity


class DeliveryReadiness:
    def __init__(self, repository, *, report_files, pacs, demographic_gate):
        self.repository,self.report_files=repository,report_files
        self.pacs,self.demographic_gate=pacs,demographic_gate

    def report_readiness(self, order):
        report=order.report
        if not report or report.status!='FINAL':
            return False,'A FINAL report is required. / يجب اعتماد التقرير نهائيًا أولًا.'
        if self.report_files.matches(order,report):return True,''
        return False,'The final report file is missing, invalid, or does not match this case. / ملف التقرير النهائي غير متاح أو غير مطابق للحالة.'

    def images_readiness(self, order, live=False):
        sid=(order.pacs_study_id or '').strip()
        if not sid:return False,'No PACS study is linked to this examination. / لا توجد دراسة صور مرتبطة بالفحص.'
        match=self.repository.current_match(order.id,sid)
        if not match:return False,'The image-to-case link is not verified. / ربط الصور بالحالة غير مؤكد.'
        safe,reason=self.demographic_gate(order)
        if not safe:return False,'Image identity needs review. / هوية الصور تحتاج مراجعة.'
        if not live:
            if (order.pacs_image_count or 0)<=0 or order.pacs_status in ('PACS_OFFLINE','WAITING','ERROR'):
                return False,'No confirmed images are available. / لا توجد صور مؤكدة متاحة.'
            return True,''
        try:
            study=self.pacs.study(sid)
            safe,reason=live_study_identity(order,match,study,sid)
            if not safe:return False,reason
            count=self.pacs.instance_count(sid)
            if count<=0:return False,'The linked PACS study contains no images. / الدراسة المرتبطة لا تحتوي صورًا.'
        except Exception:
            return False,'PACS could not verify the images. Retry when PACS is available. / تعذر التحقق من الصور عبر PACS؛ حاول بعد عودة الاتصال.'
        return True,''

    def delivery_readiness(self, order, item, live=False):
        if order.status in ('CANCELLED','REGISTERED','BOOKED'):
            return False,'This examination is not ready for delivery. / الفحص غير جاهز للتسليم.'
        if item=='REPORT':return self.report_readiness(order)
        if item=='IMAGES':return self.images_readiness(order,live=live)
        return False,'Invalid delivery item.'

    def snapshot(self, order):
        return {item:dict(zip(('allowed','reason'),self.delivery_readiness(order,item))) for item in METHODS}
