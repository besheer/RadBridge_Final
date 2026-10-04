import json
import pytest
import app as m
import dicom_connections as policy
from test_assignment_distribution import doctor

@pytest.fixture(autouse=True)
def isolated(app_ctx,monkeypatch):
    monkeypatch.setattr(m.db.session,'commit',m.db.session.flush)
    yield
    m.db.session.rollback();m.db.session.remove()

def setup(monkeypatch):
    b=m.Branch(code='UAT-DICOM',name='CODEX UAT DICOM',active=True)
    other=m.Branch(code='UAT-DICOM-OTHER',name='CODEX UAT Other',active=True)
    m.db.session.add_all([b,other]);m.db.session.flush()
    u=doctor('CODEX-UAT-DICOM-ADMIN','SUPER_ADMIN');u.role.permissions_json='["*"]'
    monkeypatch.setattr(m,'current_user',lambda:u)
    monkeypatch.setattr(m.requests,'get',lambda *a,**k: (_ for _ in ()).throw(m.requests.ConnectionError()))
    e=m.DicomEndpoint(branch_id=b.id,kind='MINI_PACS',ae_title='UATMINI',calling_ae='RADBRIDGERIS',host='branch01.example.net',port=4242,active=True,echo_result='SUCCESS')
    m.db.session.add(e);m.db.session.flush()
    c=m.app.test_client()
    with c.session_transaction() as s:s['uid']=u.id
    return c,u,b,other,e

@pytest.mark.parametrize('func,value',[(policy.ae_title,''),(policy.ae_title,'A'*17),(policy.ae_title,'A\\B'),(policy.ae_title,'عربي'),(policy.ae_title,'A\nB'),(policy.host,'https://branch.test'),(policy.host,'branch.test/path'),(policy.host,'branch.test:104'),(policy.host,'-bad.test'),(policy.port,'nan'),(policy.port,'0'),(policy.port,'65536')])
def test_invalid_connection_parameters_rejected(func,value):
    with pytest.raises(ValueError):func(value)

def test_ddns_ipv4_ipv6_and_ae_normalization():
    assert policy.host('Branch01.Example.NET')=='branch01.example.net'
    assert policy.host('192.168.1.20')=='192.168.1.20'
    assert policy.host('2001:db8::1')=='2001:db8::1'
    assert policy.ae_title(' mini01 ')=='MINI01'

def test_real_c_echo_success_and_closed_port_failure():
    from pynetdicom import AE
    from pynetdicom.sop_class import Verification
    ae=AE(ae_title='UATMINI');ae.add_supported_context(Verification)
    server=ae.start_server(('127.0.0.1',0),block=False)
    target_port=server.server_address[1]
    try:assert policy.echo('127.0.0.1',target_port,'UATMINI')['result']=='SUCCESS'
    finally:server.shutdown();ae.shutdown()
    assert policy.echo('127.0.0.1',target_port,'UATMINI')['result']=='UNREACHABLE'

def test_disabled_endpoint_cannot_send_echo(monkeypatch):
    c,u,b,other,e=setup(monkeypatch);e.active=False;m.db.session.flush()
    monkeypatch.setattr(policy,'echo',lambda *a:pytest.fail('Disabled endpoint contacted'))
    assert c.post(f'/admin/dicom-connections/{e.id}/echo').status_code==409

def test_cross_branch_page_edit_and_echo_denied(monkeypatch):
    c,u,b,other,e=setup(monkeypatch)
    u.role.permissions_json='["devices.manage"]';u.branch_id=other.id;u.role.code='UAT_DICOM_IT'
    assert c.get(f'/admin/dicom-connections?branch_id={b.id}').status_code==403
    assert c.get(f'/admin/dicom-connections/branches/{b.id}').status_code==403
    assert c.post(f'/admin/dicom-connections/{e.id}/echo').status_code==403

def test_connection_edit_invalidates_old_echo_result(monkeypatch):
    c,u,b,other,e=setup(monkeypatch)
    assert c.post(f'/admin/dicom-connections/branches/{b.id}',data={'kind':'MINI_PACS','ae_title':'NEWMINI','calling_ae':'RADBRIDGERIS','host':'new.example.net','port':'4242','active':'1'}).status_code==302
    assert e.host=='new.example.net' and e.ae_title=='NEWMINI' and e.echo_result=='NOT_TESTED'
    assert e.echo_checked_at is None

def test_echo_result_persisted_and_audited(monkeypatch):
    c,u,b,other,e=setup(monkeypatch)
    monkeypatch.setattr(policy,'echo',lambda *a:{'result':'SUCCESS','message':'C-ECHO succeeded.','elapsed_ms':10})
    assert c.post(f'/admin/dicom-connections/{e.id}/echo').status_code==302
    assert e.echo_checked_at and e.echo_elapsed_ms==10
    assert m.AuditLog.query.filter_by(action='DICOM_CECHO',entity_id=str(e.id)).count()==1

def test_inactive_branch_cannot_enable_endpoint(monkeypatch):
    c,u,b,other,e=setup(monkeypatch);b.active=False;m.db.session.flush();e.active=False
    assert c.post(f'/admin/dicom-connections/branches/{b.id}',data={'kind':'MINI_PACS','ae_title':'UATMINI','calling_ae':'RADBRIDGERIS','host':'branch.test','port':'4242','active':'1'}).status_code==302
    assert not e.active

def test_branch_name_code_activation_and_collection_are_editable(monkeypatch):
    c,u,b,other,e=setup(monkeypatch)
    assert c.post(f'/admin/branches/{b.id}/edit',data={'code':'UAT-EDITED','name':'CODEX UAT Edited','active':'1','reception_collection_enabled':'1'}).status_code==302
    assert b.code=='UAT-EDITED' and b.name=='CODEX UAT Edited' and b.reception_collection_enabled
    assert e.branch_id==b.id

@pytest.mark.parametrize('role',['RECEPTION','NURSING','TECHNICIAN'])
def test_clinical_roles_without_it_permission_denied(monkeypatch,role):
    c,u,b,other,e=setup(monkeypatch)
    actor=doctor('CODEX-UAT-DICOM-'+role,role);actor.role.permissions_json='[]';actor.branch_id=b.id
    monkeypatch.setattr(m,'current_user',lambda:actor)
    assert c.get('/admin/dicom-connections').status_code==403
    assert c.post(f'/admin/dicom-connections/{e.id}/echo').status_code==403
