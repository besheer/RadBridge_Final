"""Authenticated, audited export of one verified study; no public PACS URL."""
import re
import tempfile
import zipfile
from pathlib import PurePosixPath
import pydicom
from flask import Blueprint, jsonify, request, send_file


class ExportBlocked(Exception):
    pass


class HeaderReader:
    """Bound header parsing before pixels; never inflate an unbounded tag."""
    def __init__(self, source, size):
        self.source, self.size, self.consumed = source, size, 0
        self.limit = 8 * 1024**2

    def read(self, size=-1):
        if size < 0 or self.consumed + size > self.limit:
            raise ExportBlocked('DICOM_HEADER_SIZE_LIMIT')
        data = self.source.read(size)
        self.consumed += len(data)
        return data

    def tell(self):
        return self.source.tell()

    def seek(self, offset, whence=0):
        position = offset + (self.tell() if whence == 1 else self.size if whence == 2 else 0)
        if position < 0 or position > self.limit:
            raise ExportBlocked('DICOM_HEADER_SIZE_LIMIT')
        return self.source.seek(offset, whence)


def validate_archive(stream, *, study_uid, patient_id, dob, max_uncompressed=4 * 1024**3):
    """Inspect original headers without decoding or rewriting pixels."""
    stream.seek(0)
    try:
        with zipfile.ZipFile(stream) as archive:
            infos = [info for info in archive.infolist() if not info.is_dir()]
            if not infos or len(infos) > 20000 or sum(i.file_size for i in infos) > max_uncompressed:
                raise ExportBlocked('ARCHIVE_SIZE_LIMIT')
            images = 0
            for info in infos:
                path = PurePosixPath(info.filename.replace('\\', '/'))
                if path.is_absolute() or '..' in path.parts or ':' in info.filename:
                    raise ExportBlocked('UNSAFE_ARCHIVE_PATH')
                with archive.open(info) as source:
                    ds = pydicom.dcmread(HeaderReader(source, info.file_size), stop_before_pixels=True)
                if path.name.upper() == 'DICOMDIR':
                    if str(ds.file_meta.MediaStorageSOPClassUID) != '1.2.840.10008.1.3.10':
                        raise ExportBlocked('INVALID_DICOMDIR')
                    for record in getattr(ds, 'DirectoryRecordSequence', []):
                        if str(getattr(record, 'DirectoryRecordType', '')) == 'PATIENT':
                            if str(getattr(record, 'PatientID', '')) != patient_id:
                                raise ExportBlocked('DICOM_PATIENT_MISMATCH')
                        if str(getattr(record, 'DirectoryRecordType', '')) == 'STUDY':
                            if str(getattr(record, 'StudyInstanceUID', '')) != study_uid:
                                raise ExportBlocked('DICOM_STUDY_MISMATCH')
                    continue
                if not getattr(ds, 'SOPInstanceUID', None):
                    raise ExportBlocked('INVALID_DICOM_OBJECT')
                if str(getattr(ds, 'StudyInstanceUID', '')) != study_uid:
                    raise ExportBlocked('DICOM_STUDY_MISMATCH')
                if str(getattr(ds, 'PatientID', '')) != patient_id:
                    raise ExportBlocked('DICOM_PATIENT_MISMATCH')
                if str(getattr(ds, 'PatientBirthDate', '')) != dob:
                    raise ExportBlocked('DICOM_DOB_MISMATCH')
                images += 1
            if not images:
                raise ExportBlocked('NO_DICOM_OBJECTS')
    except ExportBlocked:
        raise
    except Exception as exc:
        raise ExportBlocked('INVALID_DICOM_ARCHIVE') from exc
    stream.seek(0)
    return images


def register(m):
    bp = Blueprint('dicom_export', __name__)

    @bp.get('/api/ohif/report/<int:order_id>/dicom-download')
    @m.require_ohif_token
    def download(order_id):
        def denied(code, status=409):
            response = jsonify(ok=False, error=code, message=(
                'تعذر تنزيل DICOM؛ راجع مطابقة الحالة أو الصلاحيات. / '
                'DICOM download blocked; review case matching or permissions. ' + code))
            response.status_code = status
            response.headers['Cache-Control'] = 'no-store'
            return response

        order = m.db.session.get(m.Order, order_id)
        if not order:
            return denied('ORDER_NOT_FOUND', 404)
        user, error = m.require_ohif_doctor_user(order_id)
        if error:
            return error
        permissions = user.role.permissions() if user.role else []
        if user.role.code.upper() != 'SUPER_ADMIN' and not ('*' in permissions or 'reports.view' in permissions):
            return denied('REPORT_ACCESS_DENIED', 403)
        if user.role.code.upper() != 'SUPER_ADMIN' and user.branch_id and user.branch_id != order.branch_id:
            return denied('BRANCH_ACCESS_DENIED', 403)
        valid, detail = m.validate_ohif_case_context(order)
        if not valid:
            return denied(detail['error'])
        valid, reason = m.pacs_demographic_gate(order)
        if not valid:
            return denied(reason)
        study_id = str(order.pacs_study_id or '')
        if not re.fullmatch(r'[a-fA-F0-9-]{36,45}', study_id):
            return denied('PACS_STUDY_REQUIRED')
        format_name = request.args.get('format', 'archive')
        if format_name not in ('archive', 'media'):
            return denied('INVALID_EXPORT_FORMAT', 400)
        detail = m._orthanc_study_detail(study_id)
        uid = str((detail.get('MainDicomTags') or {}).get('StudyInstanceUID') or '')
        if not uid or uid != request.args.get('StudyInstanceUIDs'):
            return denied('PACS_STUDY_CHANGED')
        patient = order.patient
        pid, dob = str(patient.patient_id or '').strip(), str(patient.dob or '').strip()[:8]
        if not pid or not dob:
            return denied('PATIENT_IDENTITY_INCOMPLETE')
        stream = tempfile.TemporaryFile(mode='w+b')
        try:
            # Only the server-held PACS address and verified internal ID are used.
            # Credentials never leave the server or follow a redirect.
            with m.requests.get(f'{m.PACS_ORTHANC_URL}/studies/{study_id}/{format_name}',
                                auth=m._orthanc_auth(), stream=True,
                                allow_redirects=False, timeout=(10, 60)) as upstream:
                if upstream.status_code != 200:
                    raise ExportBlocked('PACS_EXPORT_UNAVAILABLE')
                size = 0
                for chunk in upstream.iter_content(1024 * 1024):
                    size += len(chunk)
                    if size > 1024**3:
                        raise ExportBlocked('ARCHIVE_SIZE_LIMIT')
                    stream.write(chunk)
            objects = validate_archive(stream, study_uid=uid, patient_id=pid, dob=dob)
            # Recheck after preparation: assignment or reconciliation may have
            # changed while a large archive was being fetched and inspected.
            m.db.session.expire_all()
            user, error = m.require_ohif_doctor_user(order_id)
            if error:
                stream.close()
                return error
            permissions = user.role.permissions() if user.role else []
            if user.role.code.upper() != 'SUPER_ADMIN' and not ('*' in permissions or 'reports.view' in permissions):
                raise ExportBlocked('REPORT_ACCESS_DENIED')
            if (str(order.pacs_study_id or '') != study_id
                    or str(order.patient.patient_id or '').strip() != pid
                    or str(order.patient.dob or '').strip()[:8] != dob):
                raise ExportBlocked('CASE_CHANGED_DURING_EXPORT')
            if user.role.code.upper() != 'SUPER_ADMIN' and user.branch_id and user.branch_id != order.branch_id:
                raise ExportBlocked('BRANCH_ACCESS_DENIED')
            valid, reason = m.pacs_demographic_gate(order)
            if not valid:
                raise ExportBlocked(reason)
            m.audit_as_user(user, 'DICOM_EXPORT_PREPARED', 'Order', order.id,
                            f'format={format_name}; objects={objects}; bytes={size}; original files unchanged')
            m.db.session.commit()
            response = send_file(stream, mimetype='application/zip', as_attachment=True,
                                 download_name=f'RadBridge-Study-{order.id}-{format_name}.zip',
                                 conditional=False, etag=False)
            response.headers['Cache-Control'] = 'no-store'
            response.headers['X-Content-Type-Options'] = 'nosniff'
            response.call_on_close(stream.close)
            return response
        except ExportBlocked as exc:
            stream.close()
            return denied(str(exc))
        except Exception:
            stream.close()
            m.db.session.rollback()
            return denied('PACS_EXPORT_UNAVAILABLE', 502)

    m.app.register_blueprint(bp)
    return bp
