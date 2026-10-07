"""Isolated clinical correction lifecycle and permission boundaries."""
from datetime import datetime,timedelta
from types import SimpleNamespace as NS
from uuid import uuid4
import json
from pathlib import Path
import pytest
from docx import Document
import report_revisions as s
import report_revision_editor as e

@pytest.fixture
def revision_case(app_ctx,monkeypatch,tmp_path):
    m=app_ctx;key='CODEX-UAT-'+uuid4().hex[:12]
    monkeypatch.setattr(m,'REPORT_DIR',str(tmp_path))
    monkeypatch.setattr(m,'ONLYOFFICE_JWT_SECRET','CODEX-UAT-isolated-JWT-secret')
    branch=m.Branch(code=key,name=key,active=True)
    patient=m.Patient(patient_id=key,name='CODEX UAT REVISION',dob='19900101',sex='M')
    m.db.session.add_all([branch,patient]);m.db.session.flush()
    for role_code in ('RADIOLOGIST','CASE_COORDINATOR','TECHNICIAN'):
        role_row=m.Role.query.filter_by(code=role_code).one()
        role_row.permissions_json=json.dumps(m.ROLE_PERMS[role_code])
    users=[]
    for suffix,role in [('doc','RADIOLOGIST'),('consult','RADIOLOGIST'),('coord','CASE_COORDINATOR'),('tech','TECHNICIAN')]:
        u=m.User(username=key+suffix,full_name=key+suffix,password_hash='disabled-test-account',role_id=m.Role.query.filter_by(code=role).first().id,branch_id=branch.id,active=True)
        m.db.session.add(u);users.append(u)
    m.db.session.flush();doc,consult,coord,tech=users
    for u in (doc,consult):m.db.session.add(m.DoctorAssignmentProfile(user_id=u.id,modalities='DX',branches=str(branch.id),available=True))
    order=m.Order(accession=key,patient_id=patient.id,branch_id=branch.id,modality='DX',procedure='CODEX UAT Chest',
        scheduled=datetime(2037,2,3,10),status='FINAL',exam_status='REPORTING',assigned_doctor_id=doc.id)
    m.db.session.add(order);m.db.session.flush()
    path=tmp_path/'original.docx';d=Document()
    for text in ['Patient Name: '+patient.name,'Patient ID: '+key,'Accession: '+key,'FINDINGS','CODEX UAT original final findings']:d.add_paragraph(text)
    d.save(path);sha=s.digest(path)
    report=m.Report(order_id=order.id,status='FINAL',docx_path=str(path),source_path=str(path),source_type='DOCX',finalized_at=datetime.utcnow(),finalized_by=doc.username)
    m.db.session.add(report);m.db.session.flush()
    v=m.ReportVersion(report_id=report.id,accession=key,version_no=1,action='ONLYOFFICE_DRAFT',status='VERIFIED',
        docx_path=str(path),source_path=str(path),source_type='DOCX',sha256=sha,finalized_at=datetime.utcnow())
    m.db.session.add(v);m.db.session.flush()
    current={'user':doc}
    monkeypatch.setattr(m,'current_user',lambda:current['user'])
    monkeypatch.setattr(m.db.session,'commit',m.db.session.flush)
    monkeypatch.setattr(m,'pacs_demographic_gate',lambda order:(True,'MATCH'))
    c=NS(m=m,order=order,doc=doc,consult=consult,coord=coord,tech=tech,report=report,version=v,path=path,sha=sha,current=current)
    with m.app.test_request_context('/report-revisions/test'):
        yield c
    m.db.session.rollback();m.db.session.remove()

def request(c,kind='REPLACEMENT'):
    return s.request_revision(c.m,c.order,c.doc,'CODEX UAT correction reason',kind)

def approve(c,row):
    c.current['user']=c.coord
    s.review(c.m,row,c.coord,'APPROVE','CODEX UAT review approval',c.consult.id)
    c.m.db.session.flush();c.current['user']=c.consult

def token(row):
    value=uuid4().hex;row.lease_hash=e.token_hash(value);row.lease_expires_at=datetime.utcnow()+timedelta(minutes=2)
    row.editor_key='CODEX-'+uuid4().hex
    return value

def save(c,row,action='draft',base=0,cid=None):
    t=token(row)
    with c.m.app.test_request_context('/report-revisions/'+str(row.id)+'/commit',method='POST',headers={'X-RadBridge-Revision-Lease':t}):
        result=e.commit(c.m,row,c.order,c.consult,{'action':action,'base_version_no':base,'commit_id':cid or str(uuid4())},[])
        c.m.db.session.flush();return result

def test_request_and_review_preserve_original(revision_case):
    c=revision_case;row=request(c);approve(c,row)
    assert row.status=='DRAFT' and row.doctor_id==c.consult.id
    assert c.report.status==c.order.status=='FINAL'
    assert c.order.assigned_doctor_id==c.doc.id and s.digest(c.path)==c.sha
    assert c.m.ReportVersion.query.filter_by(report_id=c.report.id).count()==1
    assert c.m.AuditLog.query.filter_by(entity='report_revision',entity_id=str(row.id)).count()==2

def test_full_lifecycle_uses_separate_versions(revision_case):
    c=revision_case;row=request(c);approve(c,row)
    working=e.prepare(c.m,row,c.order);doc=Document(working);doc.add_paragraph('CODEX UAT corrected findings');doc.save(working)
    result=save(c,row);assert result['version_no']==1
    assert c.order.status==c.report.status=='FINAL'
    assert c.m.ReportVersion.query.filter_by(report_id=c.report.id).count()==1
    assert c.m.ReportRevisionVersion.query.filter_by(report_id=row.id).count()==1
    save(c,row,'verify',1);assert row.status=='VERIFIED'
    save(c,row,'finalize',1);assert row.status=='FINAL' and row.active_order_id is None
    assert c.m.ReportRevisionVersion.query.filter_by(report_id=row.id).count()==1
    assert s.latest(c.m,row).finalized_at is not None
    assert c.report.status==c.order.status=='FINAL' and s.digest(c.path)==c.sha
    assert c.order.assigned_doctor_id==c.doc.id

def test_no_duplicate_open_request(revision_case):
    c=revision_case;request(c)
    with pytest.raises(s.RevisionError,match='ACTIVE'):request(c)

def test_pending_revision_does_not_replace_final_document(revision_case):
    c=revision_case;row=request(c);approve(c,row)
    assert s.final_document(c.m,c.order) is None

def test_final_correction_is_selected_and_original_remains_downloadable(revision_case):
    c=revision_case;row=request(c);approve(c,row)
    p=e.prepare(c.m,row,c.order);doc=Document(p);doc.add_paragraph('CODEX UAT approved correction');doc.save(p)
    save(c,row);save(c,row,'verify',1);save(c,row,'finalize',1)
    result=c.m._rb_authoritative_docx_download(c.order,c.report)
    assert result['revision_id']==row.id and result['path']!=str(c.path)
    assert s.digest(c.path)==c.sha
    Path(result['path']).write_bytes(b'corrupted')
    with pytest.raises(s.RevisionError,match='DOCUMENT'):s.final_document(c.m,c.order)

def test_empty_correction_cannot_be_verified(revision_case):
    c=revision_case;row=request(c);approve(c,row);save(c,row)
    with pytest.raises(s.RevisionError,match='CORRECTION_CONTENT_REQUIRED'):save(c,row,'verify',1)
    assert row.status=='DRAFT' and c.report.status=='FINAL'

def test_pdf_conversion_failure_never_serves_original_pdf(revision_case,monkeypatch):
    c=revision_case;row=request(c);approve(c,row)
    p=e.prepare(c.m,row,c.order);doc=Document(p);doc.add_paragraph('CODEX UAT corrected result');doc.save(p)
    save(c,row);save(c,row,'verify',1);save(c,row,'finalize',1)
    def fail(*a,**kw):raise RuntimeError('isolated unavailable converter')
    monkeypatch.setattr(c.m.requests,'post',fail)
    from werkzeug.exceptions import ServiceUnavailable
    with pytest.raises(ServiceUnavailable):c.m._rb_revision_pdf_download(c.order,s.final_document(c.m,c.order))

def test_rejected_request_leaves_original_and_can_request_again(revision_case):
    c=revision_case;row=request(c)
    s.review(c.m,row,c.coord,'REJECT','CODEX UAT rejected reason')
    c.m.db.session.flush()
    assert row.status=='REJECTED' and row.active_order_id is None
    assert request(c).revision_no==2 and c.report.status=='FINAL'

@pytest.mark.parametrize('boundary',['inactive','modality','branch','unavailable'])
def test_unqualified_consultant_denied(revision_case,boundary):
    c=revision_case;row=request(c)
    profile=c.m.DoctorAssignmentProfile.query.filter_by(user_id=c.consult.id).one()
    if boundary=='inactive':c.consult.active=False
    elif boundary=='modality':profile.modalities='MR'
    elif boundary=='branch':profile.branches='99999'
    else:profile.available=False
    with pytest.raises(s.RevisionError,match='DOCTOR'):approve(c,row)
    assert row.status=='REQUESTED' and c.report.status=='FINAL'

def test_repeated_review_denied(revision_case):
    c=revision_case;row=request(c);approve(c,row)
    with pytest.raises(s.RevisionError,match='STATE'):approve(c,row)

def test_addendum_original_text_cannot_change(revision_case):
    c=revision_case;row=request(c,'ADDENDUM');approve(c,row)
    p=e.prepare(c.m,row,c.order);d=Document(p);d.paragraphs[4].text='WRONG replacement of original text';d.save(p)
    with pytest.raises(s.RevisionError,match='ADDENDUM_ORIGINAL_CONTENT_CHANGED'):save(c,row)
    assert c.m.ReportRevisionVersion.query.filter_by(report_id=row.id).count()==0
    assert s.digest(c.path)==c.sha

def test_addendum_append_is_allowed(revision_case):
    c=revision_case;row=request(c,'ADDENDUM');approve(c,row)
    p=e.prepare(c.m,row,c.order);d=Document(p);d.add_paragraph('CODEX UAT additional finding');d.save(p)
    assert save(c,row)['version_no']==1 and s.digest(c.path)==c.sha

def test_stale_base_and_patient_mismatch_denied(revision_case):
    c=revision_case;row=request(c);approve(c,row)
    p=e.prepare(c.m,row,c.order);d=Document(p);d.paragraphs[1].text='Patient ID: WRONG';d.save(p)
    with pytest.raises(s.RevisionError,match='DOCUMENT'):save(c,row)
    assert c.m.ReportRevisionVersion.query.filter_by(report_id=row.id).count()==0

def test_retry_does_not_create_version_or_hide_changed_content(revision_case):
    c=revision_case;row=request(c);approve(c,row);cid=str(uuid4())
    save(c,row,cid=cid)
    assert save(c,row,cid=cid)['retry']
    c.m.db.session().commit()  # Persist the accepted commit before testing rollback on a conflicting request.
    p=e.prepare(c.m,row,c.order);d=Document(p);d.add_paragraph('Changed after network retry');d.save(p)
    with pytest.raises(s.RevisionError,match='IDEMPOTENT_CONTENT_CHANGED'):save(c,row,cid=cid)
    with pytest.raises(Exception):save(c,row,base=0)
    assert c.m.ReportRevisionVersion.query.filter_by(report_id=row.id).count()==1

def test_pacs_gate_still_blocks_revision_verification(revision_case,monkeypatch):
    c=revision_case;row=request(c);approve(c,row)
    working=e.prepare(c.m,row,c.order);doc=Document(working);doc.add_paragraph('CODEX UAT corrected findings');doc.save(working);save(c,row)
    monkeypatch.setattr(c.m,'pacs_demographic_gate',lambda order:(False,'MISMATCH'))
    with pytest.raises(s.RevisionError,match='PACS_IDENTITY_NOT_VERIFIED'):save(c,row,'verify',1)
    assert row.status=='DRAFT' and c.report.status=='FINAL'

def test_missing_lease_blocks_commit(revision_case):
    c=revision_case;row=request(c);approve(c,row)
    with c.m.app.test_request_context('/report-revisions/1/commit',method='POST'):
        with pytest.raises(s.RevisionError,match='REVISION_EDIT_LOCKED'):e.commit(c.m,row,c.order,c.consult,{'action':'draft','base_version_no':0,'commit_id':str(uuid4())})

@pytest.mark.parametrize('path',['/case/{order}/report-corrections','/coordinator/report-corrections','/report-revisions/{row}'])
def test_technician_cannot_open_clinical_correction(revision_case,path):
    c=revision_case;row=request(c);c.current['user']=c.tech
    assert c.m.app.test_client().get(path.format(order=c.order.id,row=row.id)).status_code==403

def test_coordinator_cannot_write_and_other_branch_denied(revision_case):
    c=revision_case;row=request(c);approve(c,row);client=c.m.app.test_client()
    c.current['user']=c.coord
    with client.session_transaction() as session:session['report_revision_csrf']='CODEX-CSRF'
    assert client.post(f'/report-revisions/{row.id}/lease',json={},headers={'X-Report-Revision-CSRF':'CODEX-CSRF'}).status_code==403
    c.coord.branch_id=99999
    assert client.get(f'/report-revisions/{row.id}').status_code==403

def test_csrf_required_for_review(revision_case):
    c=revision_case;row=request(c);c.current['user']=c.coord
    assert c.m.app.test_client().post(f'/coordinator/report-corrections/{row.id}/review',data={'action':'APPROVE','doctor_id':c.consult.id,'reason':'CODEX UAT approved reason'}).status_code==403
    assert row.status=='REQUESTED'

def test_callback_link_revoked_after_final_and_foreign_revision(revision_case):
    c=revision_case;row=request(c);approve(c,row);token(row)
    t=e.link(c.m,row,'callback')
    assert e.check_link(c.m,row,'callback',t)
    row.status='FINAL'
    assert not e.check_link(c.m,row,'callback',t)
    assert not e.check_link(c.m,row,'document',t)

def test_unsafe_cache_path_never_fetched(revision_case,monkeypatch):
    c=revision_case
    from unittest.mock import Mock
    fetch=Mock();monkeypatch.setattr(c.m.requests,'get',fetch)
    for url in ['http://attacker/admin','http://attacker/cache/files/%2e%2e/secret','http://attacker/cache/files/%252e%252e/secret']:
        with pytest.raises(s.RevisionError):e.callback_bytes(c.m,url)
    fetch.assert_not_called()

def test_tampered_callback_payload_is_rejected_before_fetch(revision_case,monkeypatch):
    c=revision_case;row=request(c);approve(c,row);token(row);e.prepare(c.m,row,c.order)
    from unittest.mock import Mock
    fetch=Mock();monkeypatch.setattr(c.m.requests,'get',fetch)
    payload={'key':row.editor_key,'status':6,'url':'http://server/cache/files/safe.docx','userdata':'nonce'}
    signed=c.m._onlyoffice_jwt_encode(payload)
    payload['url']='http://server/cache/files/other.docx'
    payload['token']=signed
    result=c.m.app.test_client().post(f'/report-revisions/{row.id}/callback?token='+e.link(c.m,row,'callback'),json=payload)
    assert result.status_code==403
    fetch.assert_not_called()

def test_pdf_uses_signed_current_document_and_reuses_hash_cache(revision_case,monkeypatch):
    c=revision_case;row=request(c);approve(c,row)
    p=e.prepare(c.m,row,c.order);doc=Document(p);doc.add_paragraph('CODEX UAT clinical correction');doc.save(p)
    save(c,row);save(c,row,'verify',1);save(c,row,'finalize',1)
    from unittest.mock import Mock
    response=Mock();response.json.return_value={'endConvert':True,'fileUrl':'http://internal/cache/files/result.pdf'}
    post=Mock(return_value=response);monkeypatch.setattr(c.m.requests,'post',post)
    monkeypatch.setattr(e,'callback_bytes',lambda *a:b'%PDF-1.4\nCODEX-UAT\n%%EOF')
    document=s.final_document(c.m,c.order)
    target=e.final_pdf(c.m,document)
    assert target.name=='final-'+document['sha256']+'.pdf'
    assert e.final_pdf(c.m,document)==target and post.call_count==1
    sent=post.call_args.kwargs['json']
    assert sent['outputtype']=='pdf' and '/report-revisions/'+str(row.id)+'/document?token=' in sent['url']
    assert c.m._onlyoffice_jwt_valid(sent['token'])
