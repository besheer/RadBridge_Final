import json
import pytest
from werkzeug.exceptions import HTTPException
from test_technician_return_queue import queue_cases
import procedure_staff_workflow as staff

@pytest.fixture
def f(queue_cases):
    f=queue_cases;m=f.m
    existing=m.Role.query.filter_by(code='NURSING').first()
    if existing:f.user.role=existing;f.role=existing
    else:f.role.code='NURSING'
    old_permissions=f.role.permissions_json
    f.role.permissions_json=json.dumps(['nursing.worklist','consumables.use','attachments.view','clinical.notes'])
    proc=m.Procedure(code=f.key,name='Synthetic ECG',modality='OT')
    m.db.session.add(proc);m.db.session.flush();f.proc=proc
    for o in f.cases.values():o.procedure_id=proc.id
    m.db.session.commit()
    f.policy=dict(owner='NURSING',mode='EXAM',require_images=False,require_history=False,require_attachments=False,require_consumables=False)
    yield f
    m.db.session.rollback();f.role.permissions_json=old_permissions
    # Remove this fixture's user so repeated synthetic runs do not exceed the user CSV roundtrip limit.
    m.User.query.filter_by(id=f.user.id).delete(synchronize_session='fetch');m.db.session.commit()

def configure(f,**changes):
    policy={**f.policy,**changes};previous=staff.policies(f.m).get(f.proc.id)
    with f.m.app.test_request_context():
        staff.save(f.m,f.proc,policy,'Synthetic policy configuration',previous['version'] if previous else 0);f.m.db.session.commit()

def token(f):
    with f.client.session_transaction() as s:s['staff_policy_csrf']='synthetic-csrf'
    return 'synthetic-csrf'

def post(f,target,label='waiting',csrf=True):
    return f.client.post(f'/nursing/{f.cases[label].id}/exam-status',data={'status':target,'csrf_token':token(f) if csrf else ''},base_url='https://localhost')

def test_nursing_start_finish_without_pacs_and_no_assignment(f,monkeypatch):
    configure(f)
    monkeypatch.setattr(f.m,'pacs_readiness_evidence',lambda *a:pytest.fail('Non-image procedure must not call PACS'))
    monkeypatch.setattr(f.m,'coordinate_post_exam_assignment',lambda *a,**k:pytest.fail('Non-image completion must not assign a radiologist'))
    assert post(f,'IN_PROGRESS').status_code==302
    o=f.cases['waiting'];assert o.exam_status=='IN_PROGRESS' and o.exam_started_at
    assert post(f,'EXAM_COMPLETED').status_code==302
    assert o.exam_status=='EXAM_COMPLETED' and o.exam_completed_at
    assert f.m.AuditLog.query.filter_by(action='NURSING_EXAM_STATUS',entity_id=str(o.id)).count()==2
    assert staff.policy(f.m,o)['frozen']

@pytest.mark.parametrize('label,status',[('other',403),('final',409)])
def test_branch_and_final_protection(f,label,status):
    configure(f);assert post(f,'IN_PROGRESS',label).status_code==status

def test_nursing_csrf_role_and_forward_only(f):
    configure(f)
    assert post(f,'IN_PROGRESS',csrf=False).status_code==403
    assert post(f,'EXAM_COMPLETED').status_code==302
    assert f.cases['waiting'].exam_status=='ORDERED'
    role=f.m.Role.query.filter_by(code='TECHNICIAN').first()
    if not role:
        role=f.m.Role(code='TECHNICIAN',name='Synthetic technician',permissions_json=f.role.permissions_json);f.m.db.session.add(role)
    f.user.role=role;f.m.db.session.commit()
    assert post(f,'IN_PROGRESS').status_code==403

def test_verified_report_blocks_start(f):
    configure(f);f.m.db.session.add(f.m.Report(order_id=f.cases['waiting'].id,status='VERIFIED'));f.m.db.session.commit()
    assert post(f,'IN_PROGRESS').status_code==409

def test_tasks_mode_blocks_start_and_finish(f):
    configure(f,mode='TASKS');assert post(f,'IN_PROGRESS').status_code==409
    assert f.cases['waiting'].exam_status=='ORDERED'

def test_required_notes_documents_consumables(f,monkeypatch):
    configure(f,require_history=True,require_attachments=True,require_consumables=True)
    o=f.cases['waiting'];assert post(f,'IN_PROGRESS').status_code==302
    assert post(f,'EXAM_COMPLETED').status_code==302 and o.exam_status=='IN_PROGRESS'
    assert set(staff.requirements(f.m,o)['blockers'])=={'HISTORY_OR_NOTE_REQUIRED','CASE_ATTACHMENT_REQUIRED','CONSUMABLES_CONFIRMATION_REQUIRED'}
    f.m.db.session.add(f.m.ClinicalNote(order_id=o.id,author_user_id=f.user.id,note_type='HISTORY',text='Synthetic history'))
    f.m.db.session.commit();assert 'HISTORY_OR_NOTE_REQUIRED' not in staff.requirements(f.m,o)['blockers']
    f.m.db.session.add(f.m.Attachment(order_id=o.id,patient_id=o.patient_id,original_name='Synthetic.txt',stored_path='/synthetic/unopened.txt'))
    with f.m.app.test_request_context():f.m.audit('NURSING_CONSUMABLES_CONFIRMED','order',o.id,'Synthetic zero actual consumption')
    f.m.db.session.commit()
    assert staff.requirements(f.m,o)['allowed']
    assert post(f,'EXAM_COMPLETED').status_code==302 and o.exam_status=='EXAM_COMPLETED'

def test_received_images_or_receiving_never_bypass_checks(f,monkeypatch):
    configure(f);o=f.cases['waiting']
    def stop(*args):raise RuntimeError('normal image evidence check')
    monkeypatch.setattr(f.m,'pacs_readiness_evidence',stop)
    for study,count,status in [('synthetic-study',1,'IMAGES_COMPLETE'),(None,0,'RECEIVING')]:
        o.pacs_study_id=study;o.pacs_image_count=count;o.pacs_status=status
        with pytest.raises(RuntimeError,match='normal image'):f.m.technician_completion_evidence(o)

def test_snapshot_survives_configuration_change_and_filters(f):
    configure(f);assert post(f,'IN_PROGRESS').status_code==302
    configure(f,owner='TECHNICIAN',require_images=True)
    assert staff.policy(f.m,f.cases['waiting'])['owner']=='NURSING'
    ids={o.id for o in staff.filter_worklist(f.m,f.m.Order.query,'NURSING').all()}
    assert f.cases['waiting'].id in ids
    assert f.cases['other'].id not in ids
    tech={o.id for o in staff.filter_worklist(f.m,f.m.Order.query,'TECHNICIAN').all()}
    assert f.cases['waiting'].id not in tech
    assert post(f,'IN_PROGRESS','other').status_code==403

def test_policy_edit_requires_permission_csrf_reason_and_version(f):
    assert f.client.get(f'/admin/procedures/{f.proc.id}/staff-workflow',base_url='https://localhost').status_code==403
    f.role.permissions_json=json.dumps(['procedures.view','workflow.override']);f.m.db.session.commit()
    data={**f.policy,'csrf_token':token(f),'version':'0','reason':'x'}
    data['require_images']='';data['require_history']='';data['require_attachments']='';data['require_consumables']=''
    assert f.client.post(f'/admin/procedures/{f.proc.id}/staff-workflow',data=data,base_url='https://localhost').status_code==400
    data['reason']='Synthetic administrator review'
    assert f.client.post(f'/admin/procedures/{f.proc.id}/staff-workflow',data=data,base_url='https://localhost').status_code==302
    assert f.client.post(f'/admin/procedures/{f.proc.id}/staff-workflow',data=data,base_url='https://localhost').status_code==409
    data['csrf_token']='wrong';assert f.client.post(f'/admin/procedures/{f.proc.id}/staff-workflow',data=data,base_url='https://localhost').status_code==403

def test_unconfigured_legacy_not_silently_changed(f):
    p=staff.policy(f.m,f.cases['waiting']);assert p['owner']=='BOTH' and p['require_images'] and not p['configured']

def test_malformed_policy_fails_closed(f):
    with f.m.app.test_request_context():f.m.audit(staff.ACTION,'procedure',f.proc.id,'{}');f.m.db.session.commit()
    assert staff.policy(f.m,f.cases['waiting'])['invalid']
    assert post(f,'IN_PROGRESS').status_code==403
    assert f.cases['waiting'].id not in {o.id for o in staff.filter_worklist(f.m,f.m.Order.query,'NURSING').all()}

@pytest.mark.parametrize('lang',['en','ar'])
def test_real_bilingual_templates_and_optional_visuals(f,monkeypatch,lang):
    configure(f)
    monkeypatch.undo()
    monkeypatch.setattr(f.m,'current_ui_language',lambda:lang)
    pages={}
    for label,url in [('nursing-list','/nursing?clear_filters=1'),('nursing-case',f'/nursing/{f.cases["waiting"].id}')]:
        r=f.client.get(url,base_url='https://localhost');assert r.status_code==200
        pages[label]=r.data
    assert b'nursing-exam-controls' in pages['nursing-case']
    assert b'value="IN_PROGRESS"' in pages['nursing-case']
    assert b'No PACS image received' not in pages['nursing-case']
    f.role.permissions_json='["*"]';f.m.db.session.commit()
    r=f.client.get(f'/admin/procedures/{f.proc.id}/staff-workflow',base_url='https://localhost');assert r.status_code==200
    pages['policy']=r.data;assert b'procedure-staff-workflow' in r.data
    import os,pathlib
    if os.getenv('RADBRIDGE_SYNTHETIC_VISUAL')=='1':
        path=pathlib.Path('/tmp/visual');path.mkdir(exist_ok=True)
        for label,data in pages.items():(path/(lang+'-'+label+'.html')).write_bytes(data)
