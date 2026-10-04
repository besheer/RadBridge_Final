"""Audited, copy-preserving Orthanc correction with a durable fail-closed journal."""
import hashlib
import json
import re
from datetime import datetime
from itsdangerous import URLSafeTimedSerializer, BadSignature

FIELDS = ('PatientID', 'PatientName', 'PatientBirthDate', 'PatientSex', 'AccessionNumber')


class CorrectionError(ValueError):
    pass


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=True).encode()).hexdigest()


def target(order):
    p = order.patient
    values = dict(zip(FIELDS, (p.patient_id, p.worklist_name or p.name, p.dob, p.sex, order.accession)))
    if any(not str(v or '').strip() for v in values.values()):
        raise CorrectionError('Complete patient ID, name, birth date, sex and accession before correction.')
    if not re.fullmatch(r'\d{8}', values['PatientBirthDate']):
        raise CorrectionError('Invalid birth date.')
    try:
        datetime.strptime(values['PatientBirthDate'], '%Y%m%d')
    except ValueError:
        raise CorrectionError('Invalid birth date.') from None
    if values['PatientSex'] not in ('M', 'F', 'O'):
        raise CorrectionError('Invalid patient sex.')
    return values


def allowed(m, order):
    u = m.current_user()
    if not m.has_perm('*') and (not u.branch_id or u.branch_id != order.branch_id):
        m.abort(403)
    latest = m.Report.query.filter_by(order_id=order.id).order_by(m.Report.id.desc()).first()
    if str(order.status or '').upper() in ('FINAL', 'CANCELLED', 'VERIFIED') or (
        latest and str(latest.status or '').upper() in ('FINAL', 'VERIFIED', 'LOCKED')):
        raise CorrectionError('Verified, final or cancelled cases require the correction-center workflow.')


def call(m, method, path, body=None):
    response = m.requests.request(method, m.PACS_ORTHANC_URL + path,
                                  auth=m._orthanc_auth(), json=body, timeout=90 if method == 'POST' else 15)
    response.raise_for_status()
    return response.json()


def snapshot(m, study_id, require_stable=True):
    study = call(m, 'GET', '/studies/' + study_id)
    instances = []
    pixels = []
    series = []
    tags = None
    for sid in study.get('Series', []):
        detail = call(m, 'GET', '/series/' + sid)
        series.append(detail.get('MainDicomTags', {}).get('SeriesInstanceUID', ''))
        for iid in detail.get('Instances', []):
            t = call(m, 'GET', '/instances/' + iid + '/simplified-tags')
            identity = {k: str(t.get(k) or '') for k in FIELDS}
            if tags is not None and identity != tags:
                raise CorrectionError('DICOM instances have inconsistent identities; specialist review required.')
            tags = identity
            instances.append((iid, str(t.get('SOPInstanceUID') or '')))
            pixel = m.requests.get(m.PACS_ORTHANC_URL + '/instances/' + iid + '/content/7fe0-0010',
                                   auth=m._orthanc_auth(), timeout=30)
            pixel.raise_for_status()
            pixels.append(hashlib.sha256(pixel.content).hexdigest())
    if not instances or (require_stable and not study.get('IsStable')):
        raise CorrectionError('Wait until all images have arrived and the PACS study is stable.')
    return {'tags': tags, 'study_uid': str(study.get('MainDicomTags', {}).get('StudyInstanceUID') or ''),
            'series_uids': sorted(series), 'instances': sorted(instances), 'pixels': sorted(pixels), 'count': len(instances)}


def preview(m, inbox, order):
    allowed(m, order)
    if not m.has_perm('*'):
        # Unowned or ambiguous studies require a global administrator. Target
        # branch alone does not grant access to another branch's DICOM data.
        candidate = m.Order.query.filter_by(accession=inbox.accession).first() if inbox.accession else None
        source_endpoint = m.DicomEndpoint.query.filter_by(ae_title=inbox.source_ae,kind='MINI_PACS').first() if inbox.source_ae else None
        source_branch = candidate.branch_id if candidate else (source_endpoint.branch_id if source_endpoint else None)
        if not source_branch or source_branch != m.current_user().branch_id:
            m.abort(403)
    if inbox.state != 'REVIEW_REQUIRED':
        raise CorrectionError('Study is not waiting for review.')
    if m.DicomCorrection.query.filter_by(source_study_id=inbox.orthanc_study_id).first():
        raise CorrectionError('A correction already exists. Review its audit history; do not repeat it.')
    # A study owned by a different order, including secondary links, cannot be moved here.
    owners = m.Order.query.filter_by(pacs_study_id=inbox.orthanc_study_id).all()
    if any(o.id != order.id for o in owners) or m.PacsExamLink.query.filter_by(
            orthanc_study_id=inbox.orthanc_study_id, active=True).first():
        raise CorrectionError('Study is already clinically linked; use the correction-center workflow.')
    before = snapshot(m, inbox.orthanc_study_id)
    after = target(order)
    payload = {'actor': m.current_user().id, 'inbox': inbox.id, 'order': order.id,
               'before': digest(before), 'after': digest(after), 'link': order.pacs_study_id or ''}
    token = URLSafeTimedSerializer(m.app.secret_key, salt='pacs-correction-v1').dumps(payload)
    return before, after, token


def validate_token(m, token, inbox, order, before, after):
    try:
        payload = URLSafeTimedSerializer(m.app.secret_key, salt='pacs-correction-v1').loads(token, max_age=600)
    except BadSignature:
        raise CorrectionError('Preview expired or invalid. Preview again.') from None
    expected = {'actor': m.current_user().id, 'inbox': inbox.id, 'order': order.id,
                'before': digest(before), 'after': digest(after), 'link': order.pacs_study_id or ''}
    if payload != expected:
        raise CorrectionError('Patient, order or PACS images changed. Preview again.')


def execute(m, inbox, order, token, reason):
    from pacs_resolution_service import atomic_primary_link
    # Locks serialize correction against existing RIS primary-link operations.
    order = m.Order.query.filter_by(id=order.id).with_for_update().one()
    m.Patient.query.filter_by(id=order.patient_id).with_for_update().one()
    inbox = m.PacsStudyInbox.query.filter_by(id=inbox.id).with_for_update().one()
    before, after, _ = preview(m, inbox, order)
    validate_token(m, token, inbox, order, before, after)
    job = m.DicomCorrection(source_study_id=inbox.orthanc_study_id, order_id=order.id,
                            actor_user_id=m.current_user().id, status='PENDING', reason=reason,
                            before_json=json.dumps(before), after_json=json.dumps(after))
    m.db.session.add(job)
    m.db.session.flush()
    job_id, order_id, inbox_id = job.id, order.id, inbox.id
    m.audit('DICOM_CORRECTION_STARTED', 'dicom_correction', job_id,
            json.dumps({'source': job.source_study_id, 'order': order_id, 'before': before['tags'],
                        'after': after, 'reason': reason}, ensure_ascii=False))
    # Durable before external mutation. Interrupted operations remain visibly blocked.
    m.db.session.commit()
    try:
        result = call(m, 'POST', '/studies/' + job.source_study_id + '/modify',
                      {'Replace': after, 'Force': True, 'KeepSource': True,
                       'Keep': [], 'Synchronous': True})
        new_id = result.get('ID', '')
        if not re.fullmatch(r'[0-9a-f]{8}(?:-[0-9a-f]{8}){4}', new_id) or new_id == job.source_study_id:
            raise CorrectionError('PACS did not return a separate corrected study.')
        job.new_study_id = new_id
        job.status = 'CREATED'
        m.db.session.commit()
        # Orthanc can take a stability interval after storing a copy. Verification
        # checks every instance independently, without relying on the summary tags.
        verified = snapshot(m, new_id, require_stable=False)
        if verified['tags'] != after or verified['count'] != before['count'] or verified['pixels'] != before['pixels']:
            raise CorrectionError('Corrected DICOM tags or image count did not verify.')
        if verified['study_uid'] == before['study_uid'] or set(x[1] for x in verified['instances']) & set(x[1] for x in before['instances']):
            raise CorrectionError('Corrected copy must have new study and instance identifiers.')
        original = snapshot(m, job.source_study_id)
        if original != before:
            raise CorrectionError('Source study changed during correction; review both copies.')
        order = m.Order.query.filter_by(id=order_id).with_for_update().one()
        m.Patient.query.filter_by(id=order.patient_id).with_for_update().one()
        allowed(m, order)
        expected_link = URLSafeTimedSerializer(m.app.secret_key, salt='pacs-correction-v1').loads(token, max_age=600)['link']
        if (order.pacs_study_id or '') != expected_link:
            raise CorrectionError('RIS PACS link changed during correction.')
        if target(order) != after:
            raise CorrectionError('RIS patient changed during correction.')
        inbox = m.PacsStudyInbox.query.filter_by(id=inbox_id).with_for_update().one()
        if inbox.state != 'REVIEW_REQUIRED' or m.PacsExamLink.query.filter_by(
                orthanc_study_id=job.source_study_id, active=True).first():
            raise CorrectionError('Source review state or clinical links changed during correction.')
        new_inbox = m.PacsStudyInbox(orthanc_study_id=new_id, study_instance_uid=verified['study_uid'],
                        pacs_patient_id=after['PatientID'], pacs_patient_name=after['PatientName'],
                        accession=after['AccessionNumber'], image_count=verified['count'],
                        modality=inbox.modality, study_description=inbox.study_description, source_ae=inbox.source_ae)
        m.db.session.add(new_inbox)
        m.db.session.flush()
        atomic_primary_link(db=m.db, Order=m.Order, Report=m.Report, PacsStudyInbox=m.PacsStudyInbox,
            PacsStudyMatch=m.PacsStudyMatch, PacsResolutionEvent=m.PacsResolutionEvent,
            order_id=order_id, orthanc_study_id=new_id, study_instance_uid=verified['study_uid'],
            image_count=verified['count'], match_method='DICOM_CORRECTED', confidence='CONFIRMED',
            actor_user_id=m.current_user().id, reason=reason, pacs_patient_id=after['PatientID'],
            pacs_patient_name=after['PatientName'], pacs_accession=after['AccessionNumber'], inbox_state='MANUALLY_MATCHED')
        inbox.order_id = None
        inbox.state = 'CORRECTED_SOURCE'
        inbox.match_method = 'DICOM_ORIGINAL_RETAINED'
        job = m.db.session.get(m.DicomCorrection, job_id)
        job.status = 'COMPLETED'
        job.finished_at = datetime.utcnow()
        job.new_uid = verified['study_uid']
        m.audit('DICOM_CORRECTION_COMPLETED', 'dicom_correction', job_id,
                json.dumps({'source': job.source_study_id, 'corrected': new_id,
                            'old_uid': before['study_uid'], 'new_uid': verified['study_uid'],
                            'count': verified['count'], 'before': before['tags'], 'after': after,
                            'reason': reason}, ensure_ascii=False))
        m.evaluate_case_readiness(order)
        m.db.session.commit()
        return job
    except Exception:
        m.db.session.rollback()
        job = m.db.session.get(m.DicomCorrection, job_id)
        job.status = 'NEEDS_REVIEW'
        job.error_code = 'PACS_CORRECTION_NOT_VERIFIED'
        m.audit('DICOM_CORRECTION_NEEDS_REVIEW', 'dicom_correction', job_id,
                'External correction was not fully verified; inspect retained source and any new copy. No automatic retry.')
        m.db.session.commit()
        raise CorrectionError('Correction not completed. Source retained; review correction #' + str(job_id) + ' before retrying.') from None
