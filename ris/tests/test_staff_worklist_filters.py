import json
from datetime import datetime,timedelta
import pytest
from test_technician_return_queue import queue_cases
from staff_worklist_filters import open_now

@pytest.fixture
def staff(queue_cases):
    f=queue_cases;m=f.m
    f.role.permissions_json=json.dumps(['technician.worklist','nursing.worklist'])
    branch=m.db.session.get(m.Branch,f.user.branch_id)
    d=m.Device(branch_id=branch.id,name='Synthetic CT',modality='CT',ae_title=f.key,room='ROOM-A',workday_start='00:00',workday_end='23:59')
    m.db.session.add(d);m.db.session.flush()
    f.cases['waiting'].device_id=d.id;f.cases['waiting'].modality='CT'
    f.device=d;f.branch=branch;m.db.session.commit()
    return f

def read(f,path):
    response=f.client.get(path,base_url='https://localhost')
    assert response.status_code==200
    rows=f.captured.get('orders',[x[0] for x in f.captured.get('rows',[])])
    return {x.id for x in rows}

@pytest.mark.parametrize('page',['technician','nursing'])
def test_exact_search_and_room_filters_intersect_scope(staff,page):
    f=staff
    assert read(f,f'/{page}?device_id={f.device.id}')=={f.cases['waiting'].id}
    assert read(f,f'/{page}?room_key={f.branch.code}/ROOM-A')=={f.cases['waiting'].id}
    assert read(f,f'/{page}?patient_id='+f.cases['waiting'].patient.patient_id)
    assert read(f,f'/{page}?accession='+f.cases['waiting'].accession)=={f.cases['waiting'].id}
    assert not read(f,f'/{page}?device_id=987654321')
    assert not read(f,f'/{page}?room_key=FOREIGN/ROOM')
    assert f.cases['other'].id not in read(f,f'/{page}?q='+f.key)

@pytest.mark.parametrize('page',['technician','nursing'])
def test_user_owned_defaults_clear_and_deletion(staff,page):
    f=staff;m=f.m;key=page.upper()
    read(f,f'/{page}?modality=CT&device_id={f.device.id}')
    token=f.captured['staff_filters_csrf']
    response=f.client.post(f'/saved-views/{key}/save',data={'staff_filters_csrf':token,'view_name':'My CT room','modality':'CT','device_id':f.device.id,'evil':'x'},base_url='https://localhost')
    assert response.status_code==302
    row=m.SavedSearchFilter.query.filter_by(user_id=f.user.id,page_key=key).order_by(m.SavedSearchFilter.id.desc()).first()
    assert json.loads(row.filter_json)=={'modality':'CT','device_id':str(f.device.id)}
    assert f.client.post(f'/saved-views/{key}/{row.id}/default',data={'staff_filters_csrf':token},base_url='https://localhost').status_code==302
    response=f.client.get(f'/{page}',base_url='https://localhost')
    assert response.status_code==302 and 'modality=CT' in response.location
    assert read(f,response.location)=={f.cases['waiting'].id}
    assert f.client.get(f'/{page}?clear_filters=1',base_url='https://localhost').status_code==200
    rowid=row.id
    other=m.User(username=f.key+'-OTHER-USER',full_name='Synthetic colleague',password_hash='not-a-login',role_id=f.role.id,branch_id=f.branch.id)
    m.db.session.add(other);m.db.session.commit()
    with f.client.session_transaction() as s:s['uid']=other.id
    for action in ('default','rename','delete','update'):
        assert f.client.post(f'/saved-views/{key}/{rowid}/{action}',data={'staff_filters_csrf':token,'view_name':'No'},base_url='https://localhost').status_code==404
    assert f.client.get(f'/saved-views/{key}/{rowid}/apply',base_url='https://localhost').status_code==404
    assert f.client.get(f'/{page}',base_url='https://localhost').status_code==200
    with f.client.session_transaction() as s:s['uid']=f.user.id
    assert f.client.post(f'/saved-views/{key}/{rowid}/delete',data={'staff_filters_csrf':token},base_url='https://localhost').status_code==302
    assert m.db.session.get(m.SavedSearchFilter,rowid) is None

def test_saved_filter_cannot_restore_old_room_access(staff):
    f=staff;m=f.m
    profile=m.get_user_profile(f.user)
    profile.settings_json=json.dumps({'clinical_scope':{'enabled':True,'modalities':['MR'],'device_keys':[],'room_keys':[]}})
    m.db.session.commit()
    assert not read(f,f'/technician?device_id={f.device.id}&q='+f.key)
    assert not f.captured['staff_devices']

def test_missing_branch_and_csrf_role_guards(staff):
    f=staff
    read(f,'/nursing?clear_filters=1')
    assert f.client.post('/saved-views/NURSING/save',data={'view_name':'CSRF'},base_url='https://localhost').status_code==403
    f.user.branch_id=None;f.m.db.session.commit()
    assert not read(f,'/nursing?clear_filters=1')
    assert not f.captured['staff_devices']
    token=f.captured['staff_filters_csrf']
    f.role.permissions_json='[]';f.m.db.session.commit()
    assert f.client.post('/saved-views/NURSING/save',data={'view_name':'No role','staff_filters_csrf':token},base_url='https://localhost').status_code==403

def test_open_rooms_maintenance_hours_and_branch_block(staff):
    f=staff;m=f.m;now=datetime(2037,2,3,12)
    assert open_now(m,f.device,now)
    f.device.operational_status='MAINTENANCE';assert not open_now(m,f.device,now)
    f.device.operational_status='ACTIVE';f.device.workday_end='11:00';assert not open_now(m,f.device,now)
    f.device.workday_end='23:59'
    block=m.DeviceBlock(device_id=f.device.id,start_at=now-timedelta(hours=1),end_at=now+timedelta(hours=1),reason='Synthetic maintenance')
    m.db.session.add(block);m.db.session.commit();assert not open_now(m,f.device,now)
    m.db.session.delete(block);m.db.session.commit()
    branchblock=m.BookingBlock(block_type='BRANCH',branch_id=f.branch.id,start_at=now-timedelta(hours=1),end_at=now+timedelta(hours=1),active=True)
    m.db.session.add(branchblock);m.db.session.commit();assert not open_now(m,f.device,now)

def test_nursing_history_document_and_consumable_filters(staff):
    f=staff;m=f.m
    assert not read(f,'/nursing?history=present')
    note=m.ClinicalNote(order_id=f.cases['waiting'].id,author_user_id=f.user.id,note_type='HISTORY',text='Synthetic history',visibility='CLINICAL_TEAM')
    m.db.session.add(note);m.db.session.commit()
    assert read(f,'/nursing?history=present')=={f.cases['waiting'].id}
    assert f.cases['waiting'].id not in read(f,'/nursing?history=missing')
    assert not read(f,'/nursing?attachments=present')
    assert not read(f,'/nursing?consumables=present')
