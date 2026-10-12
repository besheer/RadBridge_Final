"""Read-only delivery identity decisions; no transport or persistence."""
METHODS={'REPORT':{'IN_PERSON','EMAIL','PORTAL','WHATSAPP'},'IMAGES':{'CD','FILM','PORTAL','LINK'}}


def live_study_identity(order, match, study, study_id):
    patient=study.get('PatientMainDicomTags') or {}
    tags=study.get('MainDicomTags') or {}
    if study.get('ID')!=study_id:
        return False,'PACS study identity changed. / تغيرت هوية دراسة الصور.'
    if match.match_method=='DEMOGRAPHICS_EXACT' and (
        str(patient.get('PatientID','')).strip()!=str(order.patient.patient_id or '').strip()
        or str(tags.get('AccessionNumber','')).strip()!=str(order.accession or '').strip()):
        return False,'PACS identity does not match this case. / هوية صور PACS لا تطابق الحالة.'
    if match.match_method in ('MANUAL_CONFIRMED','OVERRIDE_APPROVED') and (
        str(patient.get('PatientID','')).strip()!=str(match.pacs_patient_id or '').strip()
        or str(tags.get('AccessionNumber','')).strip()!=str(match.pacs_accession or '').strip()):
        return False,'The confirmed PACS identity changed. / تغيرت هوية الصور بعد تأكيد الربط.'
    return True,''
