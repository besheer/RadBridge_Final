import io, re, hashlib, zipfile
from urllib.parse import unquote, urlsplit
import pydicom, pytest
from itsdangerous import TimestampSigner
from test_viewer_choice import imaging, STUDY, UID
from test_doctor_unified_workspace import workspace
import viewer_choice as v

@pytest.fixture
def radiant(imaging, monkeypatch):
    w=imaging; m=w.m
    monkeypatch.setattr(m, 'RIS_PUBLIC_URL', 'https://ris.invalid')
    w.patient.dob='19800101';m.db.session.commit()
    ds=pydicom.dcmread(io.BytesIO(w.binary));ds.PatientBirthDate=w.patient.dob
    stream=io.BytesIO();pydicom.dcmwrite(stream,ds,enforce_file_format=True)
    archive=io.BytesIO()
    with zipfile.ZipFile(archive,'w') as z:z.writestr('synthetic.dcm',stream.getvalue())
    w.archive=archive.getvalue()
    old=m.requests.get
    class Response:
        status_code=200
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def iter_content(self,size):
            yield w.archive
            if getattr(w,'after_download',None):w.after_download()
    def get(url,**kwargs):
        if url.endswith('/archive'):
            assert kwargs['allow_redirects'] is False
            return Response()
        return old(url,**kwargs)
    monkeypatch.setattr(m.requests,'get',get)
    return w

def launch(w):
    page=w.client.get(f'/doctor/cases/{w.mine.id}/open?viewer=RADIANT')
    assert page.status_code==200
    uri=re.search(r'id="rbOpenRadiAnt" href="([^"]+)"',page.text)[1]
    assert uri.startswith('radbridge-radiant://open?url=')
    return urlsplit(unquote(uri.split('?url=',1)[1])).path

def test_original_zip_anonymous_delivery_and_checksum(radiant):
    w=radiant;path=launch(w)
    result=w.m.app.test_client().get(path)
    assert result.status_code==200 and result.data==w.archive
    assert result.headers['X-RadBridge-SHA256']==hashlib.sha256(w.archive).hexdigest()
    assert result.headers['Cache-Control']=='no-store'
    assert result.headers['Referrer-Policy']=='no-referrer'

@pytest.mark.parametrize('change',['assignment','inactive','permission','branch','study','patient','dob','uid','demographics'])
def test_capability_rechecks_current_authority(radiant,monkeypatch,change):
    w=radiant;path=launch(w)
    if change=='assignment':w.mine.assigned_doctor_id=w.other.id
    elif change=='inactive':w.doctor.active=False
    elif change=='permission':w.doctor.role.permissions_json='[]'
    elif change=='branch':w.doctor.branch_id=54321
    elif change=='study':w.mine.pacs_study_id='d'*40
    elif change=='patient':w.patient.patient_id+='-RADIANT-CHANGED'
    elif change=='dob':w.patient.dob='19900101'
    elif change=='uid':w.payloads['/studies/'+STUDY]['MainDicomTags']['StudyInstanceUID']=UID+'.99'
    else:monkeypatch.setattr(w.m,'pacs_demographic_gate',lambda order:(False,'REVIEW'))
    w.m.db.session.commit()
    assert w.client.get(path).status_code in (403,409)

def test_recheck_after_download_and_wrong_archive(radiant):
    w=radiant;path=launch(w)
    w.archive=b'not a ZIP'
    assert w.client.get(path).status_code==409

def test_reassignment_during_preparation_denied(radiant):
    w=radiant;path=launch(w)
    def change():
        w.mine.assigned_doctor_id=w.other.id;w.m.db.session.commit()
    w.after_download=change
    assert w.client.get(path).status_code==403

def test_expiry_tamper_cross_purpose_and_cross_order(radiant,monkeypatch):
    w=radiant;path=launch(w)
    assert w.client.get(path.replace('/study.zip','x/study.zip')).status_code==403
    assert w.client.get(path.replace(f'/{w.mine.id}/',f'/{w.foreign.id}/')).status_code==403
    assert w.client.get(path.replace('/radiant-images/','/weasis-images/').replace('/study.zip','/manifest.xml')).status_code==403
    now=TimestampSigner.get_timestamp
    monkeypatch.setattr(TimestampSigner,'get_timestamp',lambda self:now(self)+v.MAX_AGE+1)
    assert w.client.get(path).status_code==403

@pytest.mark.parametrize('origin',['http://ris.invalid','https://ris.invalid/path','https://name:pass@ris.invalid','https://ris.invalid?x=1'])
def test_invalid_public_origin_denied(radiant,monkeypatch,origin):
    w=radiant;monkeypatch.setattr(w.m,'RIS_PUBLIC_URL',origin)
    assert w.client.get(f'/doctor/cases/{w.mine.id}/open?viewer=RADIANT').status_code==503

def test_missing_identity_preference_and_setup(radiant):
    w=radiant;page=w.client.get(f'/doctor/cases/{w.mine.id}/viewers')
    assert all(name in page.text for name in ('OHIF','Weasis','RadiAnt'))
    with w.client.session_transaction() as session:csrf=session['viewer_choice_csrf']
    assert w.client.post('/doctor/viewer-preference',data={'viewer':'RADIANT','csrf_token':csrf}).status_code==302
    assert w.client.get(f'/doctor/cases/{w.mine.id}/open').status_code==200
    setup=w.client.get('/doctor/viewers/radiant/setup.zip')
    assert setup.status_code==200
    with zipfile.ZipFile(io.BytesIO(setup.data)) as z:
        assert set(z.namelist())=={'Install-RadiAntBridge.ps1','Open-RadiAnt.ps1','README.md'}
    w.patient.dob='';w.m.db.session.commit()
    assert w.client.get(f'/doctor/cases/{w.mine.id}/open?viewer=RADIANT').status_code==409
    w.login(w.tech)
    assert w.client.get('/doctor/viewers/radiant/setup.zip').status_code==403

