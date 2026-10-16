import json
from datetime import datetime
from types import SimpleNamespace
import pytest
from test_technician_return_queue import queue_cases
import radiotherapy as rt

@pytest.fixture
def f(queue_cases):
    f=queue_cases;m=f.m
    f.role.permissions_json=json.dumps(list(rt.PERMISSIONS))
    f.cases['waiting'].modality='PT'
    d=m.Device(branch_id=f.user.branch_id,name='SYNTHETIC RT ROOM',modality='RT',room='SYNTHETIC RT',ae_title=f.key,operational_status='ACTIVE')
    m.db.session.add(d);m.db.session.commit();f.device=d
    with f.client.session_transaction() as s:s['rt_csrf']='synthetic-csrf'
    f.courses=[]
    yield f
    m.db.session.rollback()
    ids=[c.id for c in f.courses]
    fracids=[x.id for x in m.rt_models['Fraction'].query.filter(m.rt_models['Fraction'].course_id.in_(ids)).all()]
    for model,key,values in [('Consumable','fraction_id',fracids),('Note','course_id',ids),('PetLink','course_id',ids),('Fraction','course_id',ids),('Plan','course_id',ids),('Course','id',ids)]:
        cls=m.rt_models[model];cls.query.filter(getattr(cls,key).in_(values)).delete(synchronize_session='fetch')
    if m.db.engine.dialect.name=='sqlite':
        m.UserProfile.query.filter_by(user_id=f.user.id).delete(synchronize_session='fetch')
        m.User.query.filter_by(id=f.user.id).delete(synchronize_session='fetch')
    m.db.session.commit()

    # Dispose the fixture's identity map before another test reuses SQLite IDs.
    m.db.session.remove()

def post(f,url,**data):
    return f.client.post(url,data={'csrf_token':'synthetic-csrf',**data},base_url='https://localhost')

def course(f):
    response=post(f,'/radiotherapy/courses',accession=f.cases['waiting'].accession,reference=f.key+'-COURSE')
    assert response.status_code==302
    c=f.m.rt_models['Course'].query.filter_by(reference=f.key+'-COURSE').one();f.courses.append(c);return c

def plan(f,c,**data):
    return post(f,f'/radiotherapy/{c.id}/plans',version=c.version,external_reference='SYNTHETIC APPROVED DOCUMENT',approved_by='SYNTHETIC EXTERNAL APPROVER',approved_on='2020-01-01',target='SYNTHETIC TARGET, TEST ONLY',total_gy='2',fraction_gy='1',fractions='2',reason='Synthetic recording',**data)

def schedule(f,c,number=1):
    response=post(f,f'/radiotherapy/{c.id}/fractions',version=c.version,number=number,device_id=f.device.id,planned_gy='1',scheduled_at='2037-02-03T12:00')
    assert response.status_code==302
    return f.m.rt_models['Fraction'].query.filter_by(course_id=c.id,number=number).one()

def test_manual_course_plan_session_completion_and_idempotency(f):
    c=course(f);assert c.status=='DRAFT'
    assert plan(f,c).status_code==302 and c.status=='ACTIVE'
    row=schedule(f,c)
    assert row.scheduled_at.hour==10 # Cairo standard time in February.
    assert post(f,f'/radiotherapy/fractions/{row.id}/start',version=row.version).status_code==302
    assert row.status=='STARTED'
    data=dict(version=row.version,actual_gy='1',idempotency_key='synthetic-key-12345678',delivery_reference='SYNTHETIC MACHINE RECORD')
    assert post(f,f'/radiotherapy/fractions/{row.id}/complete',**data).status_code==302
    assert row.status=='COMPLETED' and row.actual_gy==1
    assert post(f,f'/radiotherapy/fractions/{row.id}/complete',**data).status_code==302
    assert f.m.AuditLog.query.filter_by(action='RT_FRACTION_COMPLETED',entity_id=str(row.id)).count()==1
    data['actual_gy']='2';assert post(f,f'/radiotherapy/fractions/{row.id}/complete',**data).status_code==409
    assert f.cases['waiting'].status=='SCHEDULED' and f.cases['waiting'].exam_status=='ORDERED'
    assert f.m.Report.query.filter_by(order_id=f.cases['waiting'].id).count()==0

@pytest.mark.parametrize('value',['0','-1','NaN','Infinity','1.1234567','1000000000000','abc'])
def test_amount_rejects_invalid_values(value):
    with pytest.raises(ValueError):rt.amount(value)

def test_csrf_branch_and_permission_denials(f):
    assert f.client.post('/radiotherapy/courses',data={'order_id':f.cases['waiting'].id,'reference':'NO-CSRF'},base_url='https://localhost').status_code==403
    assert post(f,'/radiotherapy/courses',accession=f.cases['other'].accession,reference='OTHER-BRANCH').status_code==403
    f.role.permissions_json='[]';f.m.db.session.commit()
    assert f.client.get('/radiotherapy',base_url='https://localhost').status_code==403

def test_plan_version_is_frozen_after_delivery_and_pending_session_needs_reschedule(f):
    c=course(f);assert plan(f,c).status_code==302
    first=schedule(f,c);second=schedule(f,c,2)
    old=first.plan_id
    assert post(f,f'/radiotherapy/fractions/{first.id}/start',version=first.version).status_code==302
    assert plan(f,c).status_code==409
    assert post(f,f'/radiotherapy/fractions/{first.id}/complete',version=first.version,actual_gy='1',idempotency_key='synthetic-idempotence').status_code==302
    assert plan(f,c).status_code==302
    assert first.plan_id==old
    assert post(f,f'/radiotherapy/fractions/{second.id}/start',version=second.version).status_code==409
    assert post(f,f'/radiotherapy/fractions/{second.id}/reschedule',version=second.version,planned_gy='1',scheduled_at='2037-02-04T12:00',reason='Synthetic revision checked').status_code==302
    assert second.plan_id!=old
    assert post(f,f'/radiotherapy/fractions/{second.id}/start',version=second.version).status_code==302

def test_paused_course_prevents_new_starts_but_allows_recording_started_session(f):
    c=course(f);plan(f,c);row=schedule(f,c);other=schedule(f,c,2)
    post(f,f'/radiotherapy/fractions/{row.id}/start',version=row.version)
    assert post(f,f'/radiotherapy/{c.id}/state',version=c.version,status='PAUSED',reason='Synthetic temporary pause').status_code==302
    assert post(f,f'/radiotherapy/fractions/{other.id}/start',version=other.version).status_code==409
    assert post(f,f'/radiotherapy/fractions/{row.id}/complete',version=row.version,actual_gy='1',idempotency_key='synthetic-record-key').status_code==302

def test_cancelled_session_preserved_and_no_delivered_dose(f):
    c=course(f);plan(f,c);row=schedule(f,c)
    assert post(f,f'/radiotherapy/fractions/{row.id}/cancel',version=row.version,status='NOT_GIVEN',reason='Synthetic patient cancellation').status_code==302
    assert row.status=='NOT_GIVEN' and row.actual_gy is None
    assert post(f,f'/radiotherapy/fractions/{row.id}/start',version=row.version).status_code==409

def test_stale_version_returns_conflict(f):
    c=course(f);plan(f,c)
    assert post(f,f'/radiotherapy/{c.id}/state',version=c.version-1,status='PAUSED',reason='Synthetic pause').status_code==409
    assert c.status=='ACTIVE'

def test_same_patient_pet_link_only_and_original_order_unchanged(f):
    c=course(f)
    a=f.cases['waiting'];before=(a.patient_id,a.exam_status,a.pacs_study_id)
    assert post(f,f'/radiotherapy/{c.id}/pet-links',version=c.version,accession=a.accession,purpose='BASELINE',reason='Synthetic baseline scan').status_code==302
    assert before==(a.patient_id,a.exam_status,a.pacs_study_id)
    bad=f.cases['progress'];bad.modality='PT'
    p=f.m.Patient(patient_id=f.key+'WRONG',name='Synthetic unrelated patient');f.m.db.session.add(p);f.m.db.session.flush();bad.patient_id=p.id;f.m.db.session.commit()
    assert post(f,f'/radiotherapy/{c.id}/pet-links',version=c.version,accession=bad.accession,purpose='FOLLOW_UP',reason='Synthetic wrong patient').status_code==409

def test_nurse_can_record_preparation_and_consumables_without_dose_editing(f,monkeypatch):
    c=course(f);plan(f,c);row=schedule(f,c)
    real=f.user
    fake=SimpleNamespace(id=real.id,username=real.username,active=True,branch_id=real.branch_id,role=SimpleNamespace(code='NURSING',permissions=lambda:list(rt.PERMISSIONS)))
    monkeypatch.setattr(f.m,'current_user',lambda:fake)
    assert post(f,f'/radiotherapy/fractions/{row.id}/start',version=row.version).status_code==403
    assert plan(f,c).status_code==403
    assert post(f,f'/radiotherapy/{c.id}/notes',kind='PREPARATION',body='Synthetic nursing preparation',fraction_id=row.id).status_code==302
    assert post(f,f'/radiotherapy/fractions/{row.id}/consumables',name='Synthetic disposable',quantity='1',unit='piece').status_code==302
    assert f.m.rt_models['Consumable'].query.filter_by(fraction_id=row.id).count()==1

def test_clinical_device_scope_intersection_and_direct_url_denial(f):
    c=course(f);plan(f,c)
    profile=f.m.get_user_profile(f.user)
    profile.settings_json=json.dumps({'clinical_scope':{'enabled':True,'modalities':['PT'],'device_keys':[],'room_keys':[]}});f.m.db.session.commit()
    assert post(f,f'/radiotherapy/{c.id}/fractions',version=c.version,number=1,device_id=f.device.id,planned_gy='1',scheduled_at='2037-02-03T12:00').status_code==403
    profile.settings_json=json.dumps({'clinical_scope':{'enabled':True,'modalities':['CT'],'device_keys':[],'room_keys':[]}});f.m.db.session.commit()
    assert f.client.get(f'/radiotherapy/{c.id}',base_url='https://localhost').status_code in (403,404)

@pytest.mark.parametrize('lang',['ar','en'])
def test_bilingual_real_pages_and_optional_visuals(f,monkeypatch,lang):
    c=course(f);plan(f,c);schedule(f,c)
    monkeypatch.setattr(f.m,'current_ui_language',lambda:lang)
    import os,pathlib
    for label,url in [('list','/radiotherapy'),('course',f'/radiotherapy/{c.id}')]:
        r=f.client.get(url,base_url='https://localhost');assert r.status_code==200
        assert b'rt-' in r.data or b'/radiotherapy' in r.data
        if os.getenv('RADBRIDGE_SYNTHETIC_VISUAL')=='1':
            p=pathlib.Path('/tmp/visual');p.mkdir(exist_ok=True);(p/(lang+'-'+label+'.html')).write_bytes(r.data)


def test_rebooking_keeps_cancelled_attempt_without_reusing_delivered_number(f):
    c=course(f);plan(f,c);row=schedule(f,c)
    post(f,f'/radiotherapy/fractions/{row.id}/cancel',version=row.version,status='NOT_GIVEN',reason='Synthetic not delivered')
    response=post(f,f'/radiotherapy/{c.id}/fractions',version=c.version,number=1,device_id=f.device.id,planned_gy='1',scheduled_at='2037-02-04T12:00',reason='Synthetic patient rebooked')
    assert response.status_code==302
    attempts=f.m.rt_models['Fraction'].query.filter_by(course_id=c.id,number=1).order_by(f.m.rt_models['Fraction'].attempt).all()
    assert len(attempts)==2 and attempts[0].status=='NOT_GIVEN' and attempts[0].actual_gy is None and attempts[1].attempt==2
    row=attempts[1]
    post(f,f'/radiotherapy/fractions/{row.id}/start',version=row.version)
    post(f,f'/radiotherapy/fractions/{row.id}/complete',version=row.version,actual_gy='1',idempotency_key='synthetic-completion-key')
    assert post(f,f'/radiotherapy/{c.id}/fractions',version=c.version,number=1,device_id=f.device.id,planned_gy='1',scheduled_at='2037-02-05T12:00',reason='Synthetic duplicate delivery').status_code==409

def test_completed_session_and_wrong_attachment_cannot_be_modified(f):
    c=course(f);plan(f,c);row=schedule(f,c)
    post(f,f'/radiotherapy/fractions/{row.id}/start',version=row.version)
    post(f,f'/radiotherapy/fractions/{row.id}/complete',version=row.version,actual_gy='1',idempotency_key='synthetic-original-key')
    before=(row.actual_gy,row.plan_id,row.started_at,row.ended_at)
    assert post(f,f'/radiotherapy/fractions/{row.id}/reschedule',version=row.version,planned_gy='2',scheduled_at='2037-02-04T12:00',reason='Synthetic denied edit').status_code==409
    assert post(f,f'/radiotherapy/fractions/{row.id}/cancel',version=row.version,status='CANCELLED',reason='Synthetic denied cancellation').status_code==409
    assert before==(row.actual_gy,row.plan_id,row.started_at,row.ended_at)
    a=f.m.Attachment(order_id=f.cases['other'].id,patient_id=f.cases['other'].patient_id,original_name='SYNTHETIC.txt',stored_path='/synthetic/unopened.txt')
    f.m.db.session.add(a);f.m.db.session.commit()
    assert plan(f,c,attachment_id=a.id).status_code==409

def test_simultaneous_completion_is_idempotent_on_postgresql(f):
    if f.m.db.engine.dialect.name!='postgresql':pytest.skip('PostgreSQL row-lock concurrency test')
    c=course(f);plan(f,c);row=schedule(f,c)
    post(f,f'/radiotherapy/fractions/{row.id}/start',version=row.version)
    fid,uid,version=row.id,f.user.id,row.version
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    barrier=Barrier(2)
    def send():
        with f.m.app.app_context():
            client=f.m.app.test_client()
            with client.session_transaction() as s:s['uid']=uid;s['rt_csrf']='synthetic-concurrent-csrf'
            barrier.wait(timeout=10)
            return client.post(f'/radiotherapy/fractions/{fid}/complete',data={'csrf_token':'synthetic-concurrent-csrf','version':version,'actual_gy':'1','idempotency_key':'synthetic-concurrent-key'},base_url='https://localhost').status_code
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(lambda _:send(),range(2)))
    assert results==[302,302]
    assert f.m.AuditLog.query.filter_by(action='RT_FRACTION_COMPLETED',entity_id=str(fid)).count()==1


def test_coordinator_cannot_change_prescribed_dose_and_actual_variance_requires_reason(f):
    c=course(f);plan(f,c)
    assert post(f,f'/radiotherapy/{c.id}/fractions',version=c.version,number=1,device_id=f.device.id,planned_gy='2',scheduled_at='2037-02-03T12:00').status_code==409
    row=schedule(f,c);post(f,f'/radiotherapy/fractions/{row.id}/start',version=row.version)
    data={'version':row.version,'actual_gy':'2','idempotency_key':'synthetic-variance-key'}
    assert post(f,f'/radiotherapy/fractions/{row.id}/complete',**data).status_code==302
    assert row.status=='STARTED' and row.actual_gy is None
    data['dose_variance_reason']='Synthetic transcription from external delivery record'
    assert post(f,f'/radiotherapy/fractions/{row.id}/complete',**data).status_code==302
    assert row.status=='COMPLETED' and row.actual_gy==2 and row.reason==data['dose_variance_reason']
