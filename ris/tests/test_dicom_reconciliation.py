import json
import pytest
import app as m
import dicom_reconciliation as d
from test_assignment_distribution import doctor,order

SOURCE='11111111-11111111-11111111-11111111-11111111'
NEW='22222222-22222222-22222222-22222222-22222222'

@pytest.fixture(autouse=True)
def isolated(app_ctx,monkeypatch):
    # Commits release savepoints into an outer test transaction; subsequent
    # rollback must preserve the durable journal just as production does.
    actual_rollback=m.db.session.rollback
    m.db.session.execute(m.db.text('BEGIN'))
    state={'tx':m.db.session.begin_nested()}
    def commit():
        state['tx'].commit();state['tx']=m.db.session.begin_nested()
    def rollback():
        state['tx'].rollback();state['tx']=m.db.session.begin_nested()
    monkeypatch.setattr(m.db.session,'commit',commit)
    monkeypatch.setattr(m.db.session,'rollback',rollback)
    yield
    actual_rollback();m.db.session.remove()

def setup(monkeypatch):
    u=doctor('CODEX-UAT-CORRECTION','SUPER_ADMIN');u.role.permissions_json='["*"]'
    o=order('CODEX-UAT-CORRECTION');o.patient.dob='19900101';o.patient.sex='M'
    x=m.PacsStudyInbox(orthanc_study_id=SOURCE,state='REVIEW_REQUIRED',image_count=1)
    m.db.session.add(x);m.db.session.flush()
    monkeypatch.setattr(m,'current_user',lambda:u)
    original={'tags':dict(zip(d.FIELDS,('WRONG','CODEX UAT Wrong','19800101','F','WRONG'))),
              'study_uid':'1.2.3','series_uids':['1.2.3.1'],'instances':[('old','1.2.3.1.1')], 'pixels':['pixelhash'], 'count':1}
    def snap(module,sid,require_stable=True):
        if sid==SOURCE:return original
        return dict(original,tags=d.target(o),study_uid='1.2.4',instances=[('new','1.2.4.1.1')])
    monkeypatch.setattr(d,'snapshot',snap)
    monkeypatch.setattr(d,'call',lambda *a,**k:{'ID':NEW})
    monkeypatch.setattr(m,'evaluate_case_readiness',lambda *a:None)
    c=m.app.test_client()
    with c.session_transaction() as s:s['uid']=u.id
    return c,u,o,x,original

def token(c,o):
    r=c.get(f'/pacs/reconciliation/{SOURCE}/preview?order_id={o.id}')
    assert r.status_code==200
    assert r.headers['Cache-Control']=='no-store'
    return r.json['token']

def post(c,o,t,**extras):
    data={'order_id':o.id,'preview_token':t,'identity_confirmed':'1','reason':'CODEX UAT identity correction'};data.update(extras)
    return c.post(f'/pacs/reconciliation/{SOURCE}/correct-dicom',data=data)

def test_verified_copy_links_only_after_validation_with_complete_audit(monkeypatch):
    c,u,o,x,before=setup(monkeypatch);t=token(c,o)
    assert post(c,o,t).status_code==302
    job=m.DicomCorrection.query.one()
    assert job.status=='COMPLETED' and job.source_study_id==SOURCE and job.new_study_id==NEW
    assert o.pacs_study_id==NEW and x.state=='CORRECTED_SOURCE'
    log=m.AuditLog.query.filter_by(action='DICOM_CORRECTION_COMPLETED').one()
    details=json.loads(log.details)
    assert details['before']==before['tags'] and details['after']==d.target(o)
    assert log.user_id==u.id and job.finished_at
    assert post(c,o,t).status_code==302
    assert m.DicomCorrection.query.count()==1

@pytest.mark.parametrize('change',['patient','source','token','actor'])
def test_stale_or_tampered_preview_does_not_contact_pacs_mutation(monkeypatch,change):
    c,u,o,x,before=setup(monkeypatch);t=token(c,o)
    if change=='patient':o.patient.name='CODEX UAT Changed'
    if change=='source':before['count']=2
    if change=='token':t+='tampered'
    if change=='actor':u.id+=100
    monkeypatch.setattr(d,'call',lambda *a,**k:pytest.fail('Mutation must be blocked'))
    assert post(c,o,t).status_code==302
    assert m.DicomCorrection.query.count()==0 and not o.pacs_study_id

@pytest.mark.parametrize('failure',['timeout','count','pixels','tags','uid','link'])
def test_partial_failure_retains_source_and_blocks_unverified_link(monkeypatch,failure):
    c,u,o,x,before=setup(monkeypatch);t=token(c,o)
    oldsnap=d.snapshot
    if failure=='timeout':
        monkeypatch.setattr(d,'call',lambda *a,**k:(_ for _ in ()).throw(m.requests.Timeout()))
    else:
        def snap(mod,sid,require_stable=True):
            result=oldsnap(mod,sid,require_stable)
            if sid==NEW:
                if failure=='count':result['count']=2
                if failure=='pixels':result['pixels']=['different']
                if failure=='tags':result['tags']=before['tags']
                if failure=='uid':result['study_uid']=before['study_uid']
                if failure=='link':o.pacs_study_id='concurrent-other-study'
            return result
        monkeypatch.setattr(d,'snapshot',snap)
    assert post(c,o,t).status_code==302
    job=m.DicomCorrection.query.one()
    assert job.status=='NEEDS_REVIEW' and x.state=='REVIEW_REQUIRED'
    assert not m.PacsStudyMatch.query.filter_by(orthanc_study_id=NEW).first()
    assert m.AuditLog.query.filter_by(action='DICOM_CORRECTION_NEEDS_REVIEW').count()==1

def test_missing_confirmation_direct_post_denied(monkeypatch):
    c,u,o,x,b=setup(monkeypatch);t=token(c,o)
    assert post(c,o,t,identity_confirmed='').status_code==400
    assert m.DicomCorrection.query.count()==0

@pytest.mark.parametrize('role',['RECEPTION','NURSING','TECHNICIAN','RADIOLOGIST','FINANCE'])
def test_non_administrator_cannot_correct_dicom(monkeypatch,role):
    c,u,o,x,b=setup(monkeypatch)
    u.role=m.Role(code='UAT_CORRECT_'+role,name=role,permissions_json='["pacs.reconcile"]')
    m.db.session.flush()
    assert post(c,o,'').status_code==403

def test_branch_scope_and_final_report_protected(monkeypatch):
    c,u,o,x,b=setup(monkeypatch)
    u.role=m.Role(code='UAT_SCOPE_CORRECT',name='Scoped',permissions_json='["pacs.reconcile","correction.review"]');u.branch_id=999
    m.db.session.flush()
    assert c.get(f'/pacs/reconciliation/{SOURCE}/preview?order_id={o.id}').status_code==403
    # Only a canonical unrestricted role escapes registration branch scope;
    # a wildcard permission on an ordinary branch role does not.
    u.role.code='CALL_CENTER';u.role.permissions_json='["*"]';o.status='FINAL'
    assert c.get(f'/pacs/reconciliation/{SOURCE}/preview?order_id={o.id}').status_code==409

def test_retained_original_skipped_by_automatic_intake_and_safe_match(monkeypatch):
    c,u,o,x,b=setup(monkeypatch);post(c,o,token(c,o))
    monkeypatch.setattr(m,'_orthanc_recent_studies',lambda *a:[{'ID':SOURCE}])
    monkeypatch.setattr(m,'_study_tags_extended',lambda *a:dict(study_id=SOURCE,instances=1))
    monkeypatch.setattr(m,'discover_dicom_node_from_tags',lambda *a:None)
    monkeypatch.setattr(m,'strict_pacs_demographic_match',lambda *a:pytest.fail('Retained original must not auto-match'))
    m.pacs_auto_intake_once()
    assert c.post('/pacs/reconciliation/auto-safe').status_code==302
    assert x.state=='CORRECTED_SOURCE'
