import io
import zipfile
from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from pydicom.dataset import FileDataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian, MRImageStorage
from dicom_export_routes import validate_archive, ExportBlocked


def dicom(**fields):
    meta = FileMetaDataset()
    meta.MediaStorageSOPClassUID = MRImageStorage
    meta.MediaStorageSOPInstanceUID = '1.2.3.4.5'
    meta.TransferSyntaxUID = ExplicitVRLittleEndian
    ds = FileDataset('', {}, file_meta=meta, preamble=b'\0' * 128)
    ds.SOPClassUID, ds.SOPInstanceUID = MRImageStorage, '1.2.3.4.5'
    ds.StudyInstanceUID, ds.PatientID, ds.PatientBirthDate = '1.2.3', 'UAT', '20000101'
    for name, value in fields.items(): setattr(ds, name, value)
    result = io.BytesIO()
    ds.save_as(result, enforce_file_format=True)
    return result.getvalue()


def archive(content=None, name='study/image.dcm'):
    result = io.BytesIO()
    with zipfile.ZipFile(result, 'w') as z:
        if name: z.writestr(name, content if content is not None else dicom())
    result.seek(0)
    return result


def check(stream, **limits):
    return validate_archive(stream, study_uid='1.2.3', patient_id='UAT', dob='20000101', **limits)


def test_original_bytes_preserved_and_stream_rewound():
    stream = archive(); before = stream.getvalue()
    assert check(stream) == 1 and stream.tell() == 0
    assert stream.getvalue() == before


@pytest.mark.parametrize('fields,code', [
    ({'StudyInstanceUID':'9.8.7'}, 'DICOM_STUDY_MISMATCH'),
    ({'PatientID':'OTHER'}, 'DICOM_PATIENT_MISMATCH'),
    ({'PatientBirthDate':'19990101'}, 'DICOM_DOB_MISMATCH'),
    ({'SOPInstanceUID':''}, 'INVALID_DICOM_OBJECT'),
])
def test_wrong_object_identity_blocked(fields, code):
    with pytest.raises(ExportBlocked, match=code): check(archive(dicom(**fields)))


@pytest.mark.parametrize('name', ['../image.dcm', '/image.dcm', 'C:/image.dcm', 'folder/../../image.dcm'])
def test_unsafe_paths_never_extracted(name):
    with pytest.raises(ExportBlocked, match='UNSAFE_ARCHIVE_PATH'): check(archive(name=name))


def test_empty_corrupt_or_oversized_archives_blocked():
    for stream in [archive(name=''), io.BytesIO(b'not zip'), archive(b'not DICOM')]:
        with pytest.raises(ExportBlocked): check(stream)
    with pytest.raises(ExportBlocked, match='ARCHIVE_SIZE_LIMIT'):
        check(archive(), max_uncompressed=1)


@pytest.fixture
def export_api(app_ctx, monkeypatch):
    m = app_ctx
    patient = SimpleNamespace(patient_id='UAT', dob='20000101')
    order = SimpleNamespace(id=9, branch_id=2, patient=patient, pacs_study_id='a'*40)
    user = SimpleNamespace(id=41, active=True, branch_id=2,
        role=SimpleNamespace(code='RADIOLOGIST', permissions=lambda:['reports.view']))
    monkeypatch.setattr(m.db.session, 'get', lambda model, oid: order)
    monkeypatch.setattr(m.db.session, 'expire_all', Mock())
    monkeypatch.setattr(m.db.session, 'commit', Mock())
    monkeypatch.setattr(m, 'require_ohif_doctor_user', Mock(return_value=(user, None)))
    monkeypatch.setattr(m, 'validate_ohif_case_context', lambda _: (True, {}))
    monkeypatch.setattr(m, 'pacs_demographic_gate', Mock(return_value=(True, 'AUTO_SAFE')))
    monkeypatch.setattr(m, '_orthanc_study_detail', lambda _: {'MainDicomTags':{'StudyInstanceUID':'1.2.3'}})
    upstream = Mock(status_code=200)
    upstream.__enter__ = Mock(return_value=upstream)
    upstream.__exit__ = Mock(return_value=False)
    upstream.iter_content.return_value = [archive().getvalue()]
    get = Mock(return_value=upstream)
    monkeypatch.setattr(m.requests, 'get', get)
    monkeypatch.setattr(m, 'audit_as_user', Mock())
    return m, order, user, get


def invoke(fixture, query=''):
    m, *_ = fixture
    with m.app.test_request_context('/api/ohif/report/9/dicom-download?StudyInstanceUIDs=1.2.3'+query):
        return m.app.view_functions['dicom_export.download'].__wrapped__(9)


def test_valid_export_rechecks_access_audits_and_hides_pacs_auth(export_api):
    m, _, _, get = export_api
    response = invoke(export_api)
    assert response.status_code == 200 and response.mimetype == 'application/zip'
    assert response.headers['Cache-Control'] == 'no-store'
    assert 'RadBridge-Study-9-archive.zip' in response.headers['Content-Disposition']
    assert get.call_args.kwargs['allow_redirects'] is False
    assert get.call_args.kwargs['stream'] is True
    assert m.require_ohif_doctor_user.call_count == 2
    assert m.audit_as_user.call_args.args[1] == 'DICOM_EXPORT_PREPARED'
    response.close()


@pytest.mark.parametrize('boundary', ['identity', 'permission', 'branch', 'study', 'readiness', 'changed_uid', 'format'])
def test_denied_before_archive_request(export_api, monkeypatch, boundary):
    m, order, user, get = export_api
    if boundary == 'identity': m.require_ohif_doctor_user.return_value = (None,(m.jsonify(ok=False),403))
    if boundary == 'permission': user.role.permissions = lambda: []
    if boundary == 'branch': order.branch_id = 3
    if boundary == 'study': monkeypatch.setattr(m,'validate_ohif_case_context',lambda _: (False,{'error':'MISMATCH'}))
    if boundary == 'readiness': m.pacs_demographic_gate.return_value = (False,'REVIEW_REQUIRED')
    if boundary == 'changed_uid': monkeypatch.setattr(m,'_orthanc_study_detail',lambda _: {'MainDicomTags':{'StudyInstanceUID':'9.8.7'}})
    response = invoke(export_api, '&format=invalid' if boundary == 'format' else '')
    status = response[1] if isinstance(response,tuple) else response.status_code
    assert status in (400,403,409)
    get.assert_not_called(); m.audit_as_user.assert_not_called();m.db.session.commit.assert_not_called()


def test_revoked_assignment_during_preparation_never_delivers(export_api):
    m, _, user, _ = export_api
    m.require_ohif_doctor_user.side_effect = [(user,None),(None,(m.jsonify(ok=False),403))]
    assert invoke(export_api)[1] == 403
    m.audit_as_user.assert_not_called();m.db.session.commit.assert_not_called()


def test_case_changed_during_preparation_never_delivers(export_api):
    m, order, *_ = export_api
    m.db.session.expire_all.side_effect = lambda: setattr(order,'pacs_study_id','b'*40)
    assert invoke(export_api).status_code == 409
    m.audit_as_user.assert_not_called()


@pytest.mark.parametrize('patient_id,study_uid,blocked', [('UAT','1.2.3',False),('OTHER','1.2.3',True),('UAT','9.8.7',True)])
def test_media_directory_identity(patient_id, study_uid, blocked):
    from pydicom.dataset import Dataset
    from pydicom.sequence import Sequence
    import pydicom
    ds = pydicom.dcmread(io.BytesIO(dicom()))
    ds.SOPClassUID = ds.file_meta.MediaStorageSOPClassUID = '1.2.840.10008.1.3.10'
    patient = Dataset(); patient.DirectoryRecordType = 'PATIENT'; patient.PatientID = patient_id
    study = Dataset(); study.DirectoryRecordType = 'STUDY'; study.StudyInstanceUID = study_uid
    ds.DirectoryRecordSequence = Sequence([patient,study])
    directory = io.BytesIO(); ds.save_as(directory, enforce_file_format=True)
    stream = archive()
    with zipfile.ZipFile(stream,'a') as z: z.writestr('DICOMDIR', directory.getvalue())
    if blocked:
        with pytest.raises(ExportBlocked): check(stream)
    else: assert check(stream) == 1


def test_header_reader_bounds_reads_and_seeks():
    from dicom_export_routes import HeaderReader
    reader = HeaderReader(io.BytesIO(b'abc'),3)
    with pytest.raises(ExportBlocked,match='DICOM_HEADER_SIZE_LIMIT'): reader.read(8*1024**2+1)
    with pytest.raises(ExportBlocked,match='DICOM_HEADER_SIZE_LIMIT'): reader.seek(8*1024**2+1)


def test_upstream_failure_does_not_audit_or_deliver(export_api):
    m, _, _, get = export_api
    get.return_value.status_code = 503
    response = invoke(export_api)
    assert response.status_code == 409
    m.audit_as_user.assert_not_called()
