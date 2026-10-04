import io
import json
from pathlib import Path
import pytest
import app as m
import report_template_library as lib
from test_assignment_distribution import doctor,order
from test_report_template_library import doc_bytes

@pytest.fixture(autouse=True)
def isolated(app_ctx,monkeypatch,tmp_path):
    actual_rollback=m.db.session.rollback
    m.db.session.execute(m.db.text('BEGIN'))
    state={'tx':m.db.session.begin_nested()}
    def commit():state['tx'].commit();state['tx']=m.db.session.begin_nested()
    def rollback():state['tx'].rollback();state['tx']=m.db.session.begin_nested()
    monkeypatch.setattr(m.db.session,'commit',commit);monkeypatch.setattr(m.db.session,'rollback',rollback)
    monkeypatch.setattr(m,'REPORT_DIR',str(tmp_path))
    yield
    actual_rollback();m.db.session.remove()

def client(role='SUPER_ADMIN'):
    u=doctor('CODEX-UAT-REPORT-TEMPLATE',role)
    u.role.permissions_json=json.dumps(['*'] if role=='SUPER_ADMIN' else ['reports.edit'])
    c=m.app.test_client()
    with c.session_transaction() as session:session['uid']=u.id
    return c,u

def csrf(c):
    assert c.get('/doctor/templates').status_code==200
    with c.session_transaction() as session:return session['report_template_csrf']

def test_template_and_header_pages_render_and_sample_is_valid():
    c,u=client()
    assert c.get('/admin/report-header').status_code==200
    sample=c.get('/doctor/templates/sample.docx')
    assert sample.status_code==200
    assert lib.validate_docx(sample.data)

@pytest.mark.parametrize('role',['TECHNICIAN','RECEPTION','NURSE','CASE_COORDINATOR'])
def test_non_reporting_role_denied_even_with_report_permission(role):
    c,u=client(role)
    assert c.get('/doctor/templates').status_code==403
    assert c.get('/doctor/templates/sample.docx').status_code==403
    assert c.get('/admin/report-header').status_code==403

def test_csrf_rejects_upload_without_writing_file():
    c,u=client();c.get('/doctor/templates')
    assert c.post('/doctor/templates',data={'file':(io.BytesIO(doc_bytes()),'sample.docx')}).status_code==400
    assert m.DoctorWordTemplate.query.count()==0
    assert not list(Path(m.REPORT_DIR).rglob('*.docx'))

def test_personal_upload_audit_and_deactivation_preserves_file():
    c,u=client('RADIOLOGIST');token=csrf(c)
    result=c.post('/doctor/templates',data={'csrf_token':token,'name':'Synthetic CT','modality':'CT','file':(io.BytesIO(doc_bytes()),'sample.docx')})
    assert result.status_code==302
    row=m.DoctorWordTemplate.query.one();assert row.owner_user_id==u.id and row.visibility=='PERSONAL'
    assert json.loads(m.AuditLog.query.filter_by(action='REPORT_TEMPLATE_UPLOADED').one().details)['sha256']==lib.validate_docx(Path(row.file_path).read_bytes())
    assert c.post(f'/doctor/templates/{row.id}/deactivate',data={'csrf_token':token}).status_code==302
    assert not row.active and Path(row.file_path).is_file()

def test_ordinary_doctor_cannot_publish_shared_template():
    c,u=client('RADIOLOGIST');token=csrf(c)
    assert c.post('/doctor/templates',data={'csrf_token':token,'visibility':'SHARED','file':(io.BytesIO(doc_bytes()),'sample.docx')}).status_code==403
    assert m.DoctorWordTemplate.query.count()==0

def test_header_publish_retains_prior_version_and_audit():
    c,u=client();c.get('/admin/report-header')
    with c.session_transaction() as session:token=session['report_template_csrf']
    for title in ['Synthetic First','Synthetic Second']:
        assert c.post('/admin/report-header',data={'csrf_token':token,'title':title,'show_dob':'1','preserve_template_header':'1'}).status_code==302
    rows=m.StudioTemplate.query.filter_by(template_type='REPORT_HEADER').order_by(m.StudioTemplate.id).all()
    assert [r.version_no for r in rows]==[1,2]
    assert json.loads(rows[0].layout_json)['title']=='Synthetic First'
    assert m.StudioTemplateVersion.query.filter(m.StudioTemplateVersion.template_id.in_([r.id for r in rows])).count()==2
    assert m.AuditLog.query.filter_by(action='REPORT_HEADER_PUBLISHED').count()==2
    assert c.post(f'/studio/templates/{rows[0].id}/publish').status_code==403

def test_initialization_is_case_scoped_and_never_replaces_existing_document():
    c,u=client();o=order('CODEX-UAT-TEMPLATE-INITIAL');r=m.get_report(o)
    with m.app.test_request_context():
        path=Path(lib.initialize(m,o,r,u))
    m.db.session.flush()
    before=path.read_bytes()
    assert b'PK'==before[:2]
    assert lib.initialize(m,o,r,u)==str(path)
    with pytest.raises(lib.TemplateError,match='already'):lib.initialize(m,o,r,u,123)
    assert path.read_bytes()==before
    details=json.loads(m.AuditLog.query.filter_by(action='ONLYOFFICE_TEMPLATE_INITIALIZED').one().details)
    assert details['template_id'] is None and details['document_sha256']

def test_letterhead_settings_publish_audited_geometry():
    c,u=client();token=csrf(c)
    data={'csrf_token':token,'preprinted_letterhead':'1','letterhead_space_mm':'30','top_margin_mm':'70','left_margin_mm':'17.5'}
    assert c.post('/admin/report-header',data=data).status_code==302
    row=m.StudioTemplate.query.filter_by(template_type='REPORT_HEADER').one()
    layout=json.loads(row.layout_json)
    assert layout['preprinted_letterhead'] is True
    assert layout['letterhead_space_mm']==30 and layout['top_margin_mm']==70 and layout['left_margin_mm']==17.5
    audit=json.loads(m.AuditLog.query.filter_by(action='REPORT_HEADER_PUBLISHED').one().details)
    assert audit['layout']==layout
    assert json.loads(m.StudioTemplateVersion.query.filter_by(template_id=row.id).one().snapshot_json)==layout

def test_invalid_logo_clearance_cannot_publish():
    c,u=client();token=csrf(c)
    result=c.post('/admin/report-header',data={'csrf_token':token,'preprinted_letterhead':'1','letterhead_space_mm':'50','top_margin_mm':'60'})
    assert result.status_code==200
    with c.session_transaction() as session:
        assert any('40 mm' in message for category,message in session.get('_flashes',[])) or b'40 mm' in result.data, result.data[result.data.find(b'<main'):result.data.find(b'<main')+1400]
    assert m.StudioTemplate.query.filter_by(template_type='REPORT_HEADER').count()==0
    assert m.AuditLog.query.filter_by(action='REPORT_HEADER_PUBLISHED').count()==0

def test_bulk_upload_keeps_valid_files_and_lists_each_result():
    c,u=client('RADIOLOGIST');token=csrf(c)
    response=c.post('/doctor/templates',data={'csrf_token':token,'modality':'CT','name':'Normal','file':[(io.BytesIO(doc_bytes()),'Brain.docx'),(io.BytesIO(b'bad'),'Broken.docx'),(io.BytesIO(doc_bytes()),'Chest.docx')]},follow_redirects=True)
    assert response.status_code==200 and b'2 of 3 files uploaded' in response.data
    rows=m.DoctorWordTemplate.query.order_by(m.DoctorWordTemplate.id).all()
    assert [r.name for r in rows]==['Normal — Brain','Normal — Chest']
    assert all(r.owner_user_id==u.id and r.modality=='CT' and r.visibility=='PERSONAL' for r in rows)
    assert m.AuditLog.query.filter_by(action='REPORT_TEMPLATE_UPLOADED').count()==2
    assert len(list(Path(m.REPORT_DIR).rglob('*.docx')))==2
    assert b'Broken.docx' in response.data and b'Cannot read' in response.data
    assert b'Upload results' not in c.get('/doctor/templates').data

def test_bulk_names_default_to_filenames_and_input_supports_multiple():
    c,u=client();token=csrf(c)
    assert b'multiple required' in c.get('/doctor/templates').data
    assert c.post('/doctor/templates',data={'csrf_token':token,'file':[(io.BytesIO(doc_bytes()),'Normal.docx'),(io.BytesIO(doc_bytes()),'Follow-up.docx')]}).status_code==302
    assert {r.name for r in m.DoctorWordTemplate.query.all()}=={'Normal','Follow-up'}

@pytest.mark.parametrize('count,size',[(11,1),(6,4*1024*1024+512*1024)])
def test_bulk_limits_reject_entire_batch_before_writing(count,size):
    c,u=client();token=csrf(c)
    response=c.post('/doctor/templates',data={'csrf_token':token,'file':[(io.BytesIO(b'x'*size),f'{i}.docx') for i in range(count)]})
    assert response.status_code==302
    assert m.DoctorWordTemplate.query.count()==0
    assert not list(Path(m.REPORT_DIR).rglob('*.docx'))

def test_bulk_permission_failure_precedes_writing():
    c,u=client('RADIOLOGIST');token=csrf(c)
    assert c.post('/doctor/templates',data={'csrf_token':token,'visibility':'SHARED','file':[(io.BytesIO(doc_bytes()),'one.docx'),(io.BytesIO(doc_bytes()),'two.docx')]}).status_code==403
    assert m.DoctorWordTemplate.query.count()==0
    assert not list(Path(m.REPORT_DIR).rglob('*.docx'))

def test_bulk_database_failure_removes_only_failed_file(monkeypatch):
    c,u=client();token=csrf(c)
    audit=m.audit_as_user
    counter={'calls':0}
    def fail_middle(*args,**kwargs):
        counter['calls']+=1
        if counter['calls']==2:raise RuntimeError('Synthetic failure')
        return audit(*args,**kwargs)
    monkeypatch.setattr(m,'audit_as_user',fail_middle)
    response=c.post('/doctor/templates',data={'csrf_token':token,'file':[(io.BytesIO(doc_bytes()),f'{i}.docx') for i in range(3)]},follow_redirects=True)
    assert response.status_code==200 and b'2 of 3 files uploaded' in response.data
    assert {r.name for r in m.DoctorWordTemplate.query.all()}=={'0','2'}
    assert len(list(Path(m.REPORT_DIR).rglob('*.docx')))==2
    assert m.AuditLog.query.filter_by(action='REPORT_TEMPLATE_UPLOADED').count()==2
