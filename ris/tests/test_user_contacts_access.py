import json
import pytest
import app as m
import user_access_policy as policy
from test_assignment_distribution import doctor

@pytest.fixture(autouse=True)
def isolated(app_ctx,monkeypatch):
    monkeypatch.setattr(m.db.session,'commit',m.db.session.flush)
    yield
    m.db.session.rollback();m.db.session.remove()

def client(monkeypatch,code='SUPER_ADMIN'):
    u=doctor('CODEX-UAT-CONTACT-ACTOR-'+code,code)
    u.role.permissions_json=json.dumps(m.ROLE_PERMS.get(code,[]))
    m.db.session.flush();monkeypatch.setattr(m,'current_user',lambda:u)
    c=m.app.test_client()
    with c.session_transaction() as s:s['uid']=u.id
    return c,u

def edit_data(u,**extra):
    return dict(full_name=u.full_name,role_id=u.role_id,branch_id='',active='1',**extra)

def test_contacts_saved_with_existing_preferences_preserved_and_no_message(monkeypatch):
    c,admin=client(monkeypatch);u=doctor('CODEX-UAT-CONTACT-TARGET')
    profile=m.get_user_profile(u);profile.settings_json=json.dumps({'reporting':{'preferred_editor':'ONLYOFFICE'}})
    data=edit_data(u,contact_phone='+20 100 000 0000',contact_whatsapp='+20 100 000 0001',contact_email='uat@example.test',contact_telegram='codex_uat',contact_other_contact='Internal extension 123',department='Radiology',specialty='CT')
    assert c.post('/admin/users/'+str(u.id)+'/edit',data=data).status_code==302
    assert policy.contacts(u)['phone']=='+201000000000'
    assert policy.contacts(u)['telegram']=='codex_uat'
    assert m.user_profile_settings(profile)['reporting']['preferred_editor']=='ONLYOFFICE'
    log=m.AuditLog.query.filter_by(action='USER_CONTACTS_SAVE').one()
    assert 'example.test' not in log.details and '+20' not in log.details

@pytest.mark.parametrize('field,value',[('phone','bad'),('whatsapp','javascript:alert(1)'),('telegram','https://t.me/someone'),('email','invalid'),('other_contact','x'*161)])
def test_invalid_contacts_do_not_change_user(monkeypatch,field,value):
    c,admin=client(monkeypatch);u=doctor('CODEX-UAT-invalid-contact')
    original=u.full_name
    data=edit_data(u,**{'contact_'+field:value});data['full_name']='Changed'
    assert c.post('/admin/users/'+str(u.id)+'/edit',data=data).status_code==302
    assert u.full_name==original and m.UserProfile.query.filter_by(user_id=u.id).count()==0

def test_readonly_it_sees_users_without_mutation_forms(monkeypatch):
    c,u=client(monkeypatch,'IT')
    response=c.get('/admin/users');assert response.status_code==200
    assert b'Create User</button>' not in response.data and b'Reset Password</button>' not in response.data
    assert c.post('/admin/users/'+str(u.id)+'/edit',data=edit_data(u)).status_code==403

@pytest.mark.parametrize('code',['NURSING','TECHNICIAN','SERVICE','CASE_COORDINATOR'])
def test_report_edit_blocked_even_with_corrupt_department_permissions(monkeypatch,code):
    c,u=client(monkeypatch,code);u.role.permissions_json=json.dumps(['reports.edit','*'])
    with m.app.test_request_context('/'):
        assert not m.has_perm('reports.edit')

def test_unsafe_department_role_edit_rejected(monkeypatch):
    c,admin=client(monkeypatch);r=m.Role.query.filter_by(code='TECHNICIAN').first()
    before=r.permissions_json
    assert c.post('/admin/roles',data={'role_id':r.id,'permissions':['reports.edit']}).status_code==302
    assert r.permissions_json==before

def test_self_disable_or_admin_demotion_blocked(monkeypatch):
    c,u=client(monkeypatch)
    data=edit_data(u);data['active']='0'
    c.post('/admin/users/'+str(u.id)+'/edit',data=data)
    assert u.active
    r=m.Role.query.filter_by(code='RADIOLOGIST').first();data['active']='1';data['role_id']=r.id
    c.post('/admin/users/'+str(u.id)+'/edit',data=data)
    assert u.role.code=='SUPER_ADMIN'

@pytest.mark.parametrize('action',['edit','toggle','reset-password'])
def test_delegated_user_manager_cannot_change_superadmin(monkeypatch,action):
    c,u=client(monkeypatch,'IT');u.role.permissions_json=json.dumps(['users.view','users.manage'])
    admin=doctor('CODEX-UAT-protected-admin','SUPER_ADMIN')
    assert c.post('/admin/users/'+str(admin.id)+'/'+action,data=edit_data(admin)).status_code==403

def test_delegated_manager_cannot_assign_higher_privileges(monkeypatch):
    c,u=client(monkeypatch,'IT');u.role.permissions_json=json.dumps(['users.view','users.manage'])
    target=doctor('CODEX-UAT-ordinary-target')
    role=m.Role.query.filter_by(code='SUPER_ADMIN').first()
    data=edit_data(target);data['role_id']=role.id
    assert c.post('/admin/users/'+str(target.id)+'/edit',data=data).status_code==403

def test_inactive_session_cannot_open_profile(monkeypatch):
    c,u=client(monkeypatch);u.active=False
    assert c.get('/my/profile').status_code==302

def test_route_catalog_maps_pages_and_admin_review_renders(monkeypatch):
    c,u=client(monkeypatch)
    rows=policy.route_catalog();target=next(x for x in rows if x['path']=='/admin/users')
    assert target['permissions']==['users.view']
    assert c.get('/admin/access-review').status_code==200
    r=m.Role.query.filter_by(code='TECHNICIAN').first()
    assert policy.page_access(r,dict(permissions=['reports.edit']))=='DENIED'

@pytest.mark.parametrize('code',list(m.ROLE_PERMS))
def test_department_direct_admin_page_denial(monkeypatch,code):
    c,u=client(monkeypatch,code)
    if code=='SUPER_ADMIN':
        assert c.get('/admin/users').status_code==200
        assert c.get('/admin/access-review').status_code==200
    else:
        assert c.get('/admin/access-review').status_code==403
        assert c.get('/admin/roles').status_code==403
        assert c.get('/admin/branches').status_code==403
        if code!='IT':assert c.get('/admin/users').status_code==403


@pytest.mark.parametrize('code',list(m.ROLE_PERMS))
def test_all_simple_decorated_pages_deny_ungranted_department(monkeypatch,code):
    c,u=client(monkeypatch,code)
    rows=policy.route_catalog()
    for row in rows:
        if not row['direct'] or not row['permissions']:continue
        with m.app.test_request_context('/'):
            granted=all(m.has_perm(perm) for perm in row['permissions'])
        if not granted:
            response=c.get(row['path'])
            assert response.status_code==403,(code,row['path'],response.status_code)

def test_omitted_contact_fields_preserve_saved_contacts(monkeypatch):
    c,admin=client(monkeypatch);u=doctor('CODEX-UAT-contact-preserve')
    policy.save_contacts(u,{'phone':'+201000000000'}, {})
    assert c.post('/admin/users/'+str(u.id)+'/edit',data=edit_data(u)).status_code==302
    assert policy.contacts(u)['phone']=='+201000000000'

def test_create_user_can_store_contact_details(monkeypatch):
    c,admin=client(monkeypatch)
    role=m.Role.query.filter_by(code='RADIOLOGIST').first()
    response=c.post('/admin/users',data={'username':'CODEX-UAT-new-contact','full_name':'CODEX UAT Contact','password':'Synthetic-Test-Password','role_id':role.id,'contact_email':'uat@example.test','contact_telegram':'codex_uat'})
    assert response.status_code==200
    u=m.User.query.filter_by(username='CODEX-UAT-new-contact').one()
    assert policy.contacts(u)['email']=='uat@example.test' and u.must_change_password
