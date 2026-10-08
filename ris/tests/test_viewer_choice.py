"""No clinical data or network: real routes, permissions and DICOM headers."""
import io
import re
from types import SimpleNamespace
from urllib.parse import unquote
from xml.etree import ElementTree as ET
import pytest
import pydicom
from itsdangerous import TimestampSigner
from test_doctor_unified_workspace import workspace
import viewer_choice as v
import app as m

STUDY='a'*40
SERIES='b'*40
INSTANCE='c'*40
UID='1.2.826.0.1.3680043.10.100.1'
SUID=UID+'.2'
IUID=UID+'.3'


@pytest.fixture
def imaging(workspace, monkeypatch):
    w=workspace;w.m=m
    monkeypatch.setattr(m,'orthanc_ok',lambda:False)
    w.mine.pacs_study_id=STUDY;w.mine.study_instance_uid=UID
    m.db.session.commit()
    monkeypatch.setattr(m,'pacs_demographic_gate',lambda order:(True,'AUTO_SAFE'))
    payloads={
        '/studies/'+STUDY:{'ID':STUDY,'Series':[SERIES], 'MainDicomTags':{'StudyInstanceUID':UID,'AccessionNumber':w.mine.accession},
            'PatientMainDicomTags':{'PatientID':w.patient.patient_id,'PatientName':'Synthetic <Patient>'}},
        '/studies/'+STUDY+'/instances':[{'ID':INSTANCE,'ParentSeries':SERIES,'MainDicomTags':{'SOPInstanceUID':IUID,'InstanceNumber':'1'}}],
        '/series/'+SERIES:{'ParentStudy':STUDY,'MainDicomTags':{'SeriesInstanceUID':SUID,'Modality':'DX'}},
        '/instances/'+INSTANCE:{'ParentSeries':SERIES,'MainDicomTags':{'SOPInstanceUID':IUID}}
    }
    ds=pydicom.Dataset();ds.file_meta=pydicom.dataset.FileMetaDataset()
    ds.file_meta.TransferSyntaxUID=pydicom.uid.ExplicitVRLittleEndian
    ds.file_meta.MediaStorageSOPClassUID=pydicom.uid.SecondaryCaptureImageStorage
    ds.file_meta.MediaStorageSOPInstanceUID=IUID
    ds.SOPClassUID=pydicom.uid.SecondaryCaptureImageStorage;ds.SOPInstanceUID=IUID
    ds.StudyInstanceUID=UID;ds.SeriesInstanceUID=SUID;ds.PatientID=w.patient.patient_id
    ds.Rows=1;ds.Columns=1;ds.BitsAllocated=8;ds.PixelData=b'\x01\x00'
    image=io.BytesIO();pydicom.dcmwrite(image,ds,enforce_file_format=True)
    w.binary=image.getvalue();w.payloads=payloads;w.calls=[]
    class Response:
        status_code=200
        def __init__(self,path):self.path=path
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def json(self):return payloads[self.path]
        def iter_content(self,size):yield w.binary
    def get(url,**kwargs):
        assert kwargs['allow_redirects'] is False
        path=url.removeprefix(m.PACS_ORTHANC_URL.rstrip('/'))
        w.calls.append(path);return Response(path)
    monkeypatch.setattr(m.requests,'get',get)
    yield w


def launch(w):
    response=w.client.get(f'/doctor/cases/{w.mine.id}/open?viewer=WEASIS')
    assert response.status_code==200
    uri=re.search(r'id="rbOpenWeasis" href="([^"]+)"',response.text)[1]
    command=unquote(uri.split('?',1)[1])
    assert command.startswith('$dicom:get -w "')
    url=command.split('"')[1]
    path=url.removeprefix(w.m.RIS_PUBLIC_URL)
    assert path.startswith('/viewer/weasis/')
    return path


def test_real_manifest_and_original_dicom_delivery(imaging):
    w=imaging;path=launch(w)
    response=w.client.get(path);assert response.status_code==200
    root=ET.fromstring(response.data);ns={'w':'http://www.weasis.org/xsd/2.5'}
    arc=root.find('w:arcQuery',ns);obj=root.find('.//w:Instance',ns)
    assert obj.attrib['SOPInstanceUID']==IUID
    assert root.find('.//w:Patient',ns).attrib['PatientName']=='Synthetic <Patient>'
    image_path=arc.attrib['baseUrl'].removeprefix(w.m.RIS_PUBLIC_URL)+obj.attrib['DirectDownloadFile']
    result=w.client.get(image_path)
    assert result.status_code==200 and result.data==w.binary
    assert result.mimetype=='application/dicom'
    assert result.headers['Cache-Control']=='no-store'
    assert 'orthanc' not in response.text.lower()


def test_preference_is_per_doctor_and_default_route_uses_it(imaging):
    w=imaging
    assert w.client.get(f'/doctor/cases/{w.mine.id}/open').status_code==302
    page=w.client.get(f'/doctor/cases/{w.mine.id}/viewers')
    token=re.search(r'name="csrf_token" value="([^"]+)"',page.text)[1]
    result=w.client.post('/doctor/viewer-preference',data={'viewer':'WEASIS','csrf_token':token,'order_id':w.mine.id})
    assert result.status_code==302
    assert w.client.get(f'/doctor/cases/{w.mine.id}/open').status_code==200
    profile=w.m.UserProfile.query.filter_by(user_id=w.other.id).first()
    assert v.preference(w.m,profile)=='OHIF'
    assert w.client.get(f'/doctor/cases/{w.mine.id}/open?viewer=OHIF').status_code==302


@pytest.mark.parametrize('role',['tech','other'])
def test_wrong_doctor_or_clinical_role_denied(imaging,role):
    w=imaging;path=launch(w);w.login(getattr(w,role))
    assert w.client.get(f'/doctor/cases/{w.mine.id}/open?viewer=WEASIS').status_code==403
    assert w.client.get(f'/doctor/cases/{w.mine.id}/viewers').status_code==403
    # A signed capability is tied to its issuing doctor, independent of browser cookies.
    w.mine.assigned_doctor_id=w.other.id;w.m.db.session.commit()
    assert w.client.get(path).status_code==403


@pytest.mark.parametrize('change',['assignment','inactive','permission','branch','study','patient','uid','demographics'])
def test_authorization_rechecked_for_every_fetch(imaging,monkeypatch,change):
    w=imaging;path=launch(w)
    if change=='assignment':w.mine.assigned_doctor_id=w.other.id
    elif change=='inactive':w.doctor.active=False
    elif change=='permission':w.doctor.role.permissions_json='[]'
    elif change=='branch':w.doctor.branch_id=54321
    elif change=='study':w.mine.pacs_study_id='d'*40
    elif change=='patient':w.patient.patient_id='CHANGED'
    elif change=='uid':w.payloads['/studies/'+STUDY]['MainDicomTags']['StudyInstanceUID']=UID+'.99'
    else:monkeypatch.setattr(w.m,'pacs_demographic_gate',lambda order:(False,'REVIEW'))
    w.m.db.session.commit()
    assert w.client.get(path).status_code in (403,409)


def test_expired_and_tampered_capabilities_denied(imaging,monkeypatch):
    w=imaging;path=launch(w)
    assert w.client.get(path.replace('/manifest.xml','X/manifest.xml')).status_code==403
    now=TimestampSigner.get_timestamp
    monkeypatch.setattr(TimestampSigner,'get_timestamp',lambda self:now(self)+v.MAX_AGE+1)
    assert w.client.get(path).status_code==403


def test_anonymous_manifest_requires_capability_not_browser_session(imaging):
    w=imaging;path=launch(w)
    client=w.m.app.test_client()
    assert client.get(path).status_code==200
    assert client.get(f'/viewer/weasis/{w.mine.id}/bad/manifest.xml').status_code==403
    assert client.get(f'/doctor/cases/{w.mine.id}/viewers').status_code==302
    assert client.post(path).status_code==405


def test_cross_study_instance_cannot_be_downloaded(imaging):
    w=imaging;path=launch(w)
    w.payloads['/series/'+SERIES]['ParentStudy']='d'*40
    assert w.client.get(path).status_code==409
    assert w.client.get(path.replace('/manifest.xml','/instances/'+INSTANCE+'.dcm')).status_code==403
    assert not any(call.endswith('/file') for call in w.calls)


def test_dicom_header_mismatch_rejected(imaging):
    w=imaging;path=launch(w)
    ds=pydicom.dcmread(io.BytesIO(w.binary));ds.PatientID='WRONG'
    result=io.BytesIO();pydicom.dcmwrite(result,ds,enforce_file_format=True);w.binary=result.getvalue()
    assert w.client.get(path.replace('/manifest.xml','/instances/'+INSTANCE+'.dcm')).status_code==409


def test_preference_csrf_invalid_values_and_scope(imaging):
    w=imaging
    assert w.client.post('/doctor/viewer-preference',data={'viewer':'WEASIS'}).status_code==403
    w.client.get(f'/doctor/cases/{w.mine.id}/viewers')
    with w.client.session_transaction() as session:csrf=session['viewer_choice_csrf']
    assert w.client.post('/doctor/viewer-preference',data={'viewer':'javascript:bad','csrf_token':csrf}).status_code==400
    assert w.client.post('/doctor/viewer-preference',data={'viewer':'WEASIS','csrf_token':csrf},headers={'Origin':'https://evil.invalid'}).status_code==403
    assert w.client.get(f'/doctor/cases/{w.mine.id}/open?viewer=INVALID').status_code==400
    w.login(w.tech)
    assert w.client.post('/doctor/viewer-preference',data={'viewer':'WEASIS','csrf_token':csrf}).status_code==403


def test_profile_save_preserves_reporting_and_unrelated_settings(imaging):
    w=imaging;p=w.m.get_user_profile(w.doctor)
    p.settings_json='{"image_viewer":"WEASIS","unrelated":{"keep":17}}';w.m.db.session.commit()
    response=w.client.post('/me/profile',data={'preferred_editor':'ONLYOFFICE','preferred_layout':'70_30'})
    # Resolve the actual existing profile route rather than introducing an alias.
    if response.status_code==404:
        with w.m.app.test_request_context():path=w.m.url_for('my_profile')
        response=w.client.post(path,data={'preferred_editor':'ONLYOFFICE','preferred_layout':'70_30'})
    assert response.status_code==302
    settings=w.m.user_profile_settings(p)
    assert settings['image_viewer']=='WEASIS' and settings['unrelated']=={'keep':17}
    assert settings['reporting']['preferred_layout']=='70_30'


@pytest.mark.parametrize('raw',['not json','[]','{"image_viewer": []}','{"image_viewer":"unknown"}'])
def test_corrupt_preference_falls_back(app_ctx,raw):
    assert v.preference(app_ctx,SimpleNamespace(settings_json=raw))=='OHIF'
