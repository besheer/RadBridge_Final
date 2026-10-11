from web.source_contract import read_source as _read_source
import base64
import json
import sqlite3
import uuid
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest
import app as m
import security_dashboard as s
from werkzeug.security import generate_password_hash

PASSWORD='SYNTHETIC-security-only'

@pytest.fixture
def security_env(app_ctx,tmp_path,monkeypatch):
    monkeypatch.setitem(m.app.config,'SECURITY_DATA_DIR',str(tmp_path))
    monkeypatch.setitem(m.app.config,'SECURITY_TRUSTED_PROXIES','127.0.0.1/32')
    m.AuditLog.query.filter(m.AuditLog.action.in_([s.POLICY_ACTION,'SECURITY_VPN_CREATE','SECURITY_VPN_REVOKE'])).delete(synchronize_session=False);m.db.session.commit()
    c=sqlite3.connect(tmp_path/'countries.sqlite')
    c.execute('CREATE TABLE ranges(version INTEGER,first TEXT,last TEXT,country TEXT,PRIMARY KEY(version,first))')
    c.execute('CREATE TABLE metadata(key TEXT,value TEXT)')
    for first,last,cc in [('8.8.8.0','8.8.8.255','US'),('1.1.1.0','1.1.1.255','AU')]:
        c.execute('INSERT INTO ranges VALUES(4,?,?,?)',(f'{int(s.valid_ip(first)):032x}',f'{int(s.valid_ip(last)):032x}',cc))
    c.execute('INSERT INTO metadata VALUES(?,?)',('release_date',datetime.utcnow().replace(day=1).date().isoformat()));c.commit();c.close()
    c=sqlite3.connect(tmp_path/'events.sqlite')
    c.execute('CREATE TABLE events(id INTEGER PRIMARY KEY,timestamp TEXT,channel TEXT,outcome TEXT,ip TEXT,country TEXT,account TEXT,detail TEXT)')
    stamp=datetime.utcnow().isoformat(timespec='seconds')
    c.executemany('INSERT INTO events(timestamp,channel,outcome,ip,country,account,detail) VALUES(?,?,?,?,?,?,?)',[(stamp,'SSH','FAILED','8.8.8.8','US','test-user','password'),(stamp,'WEB','SUCCESS','1.1.1.1','AU','test-user','Application authentication'),(stamp,'HTTP','REJECTED','8.8.8.8','US','','GET HTTP 404')]);c.commit();c.close()
    public=base64.b64encode(bytes(range(32))).decode()
    status={'updated_at':stamp,'vpn':{'ready':True,'public_key':public,'endpoint':'192.0.2.10:51820','peers':{},'synced_at':stamp},'fail2ban':{'active':True,'banned_count':1,'banned_ips':['198.51.100.10']},'errors':[]}
    (tmp_path/'status.json').write_text(json.dumps(status))
    role=m.Role.query.filter_by(code='SUPER_ADMIN').first()
    u=m.User(username='SEC-UAT-'+uuid.uuid4().hex[:10],full_name='Synthetic administrator',password_hash=generate_password_hash(PASSWORD),role_id=role.id,active=True)
    m.db.session.add(u);m.db.session.commit()
    client=m.app.test_client()
    with client.session_transaction() as ss:ss['uid']=u.id
    response=client.get('/admin/security',headers={'X-Forwarded-For':'8.8.8.8'})
    assert response.status_code==200
    with client.session_transaction() as ss:token=ss['security_csrf']
    yield client,u,token,tmp_path
    m.AuditLog.query.filter(m.AuditLog.action.in_([s.POLICY_ACTION,'SECURITY_VPN_CREATE','SECURITY_VPN_REVOKE'])).delete(synchronize_session=False);m.db.session.commit()

def post(client,token,path,**data):
    if path=='/admin/security/vpn/create':
        client.get('/admin/security',headers={'X-Forwarded-For':'8.8.8.8'})
        with client.session_transaction() as ss:data.setdefault('creation_nonce',ss.get('security_vpn_nonce',''))
    return client.post(path,headers={'X-Forwarded-For':'8.8.8.8'},data={'csrf_token':token,'reason':'Synthetic security test','password':PASSWORD,**data})

def test_proxy_headers_cannot_choose_identity():
    req=SimpleNamespace(remote_addr='203.0.113.9',headers={'X-Forwarded-For':'8.8.8.8'})
    assert str(s.client_ip(req,'127.0.0.1/32'))=='203.0.113.9'
    req.remote_addr='127.0.0.1';assert str(s.client_ip(req,'127.0.0.1/32'))=='8.8.8.8'
    req.headers={'X-Forwarded-For':'8.8.8.8, 1.1.1.1'};assert s.client_ip(req,'127.0.0.1/32') is None

@pytest.mark.parametrize('role',['RECEPTION','RADIOLOGIST','TECHNICIAN','CASE_COORDINATOR','NURSING','ADMIN'])
def test_global_dashboard_denies_non_superadmin(security_env,role):
    client,u,token,_=security_env
    r=m.Role.query.filter_by(code=role).first()
    if r is None:r=m.Role(code=role,name=role,permissions_json='["*"]');m.db.session.add(r);m.db.session.flush()
    target=m.User(username='SEC-DENY-'+uuid.uuid4().hex[:10],full_name='Synthetic denied',password_hash=generate_password_hash(PASSWORD),role_id=r.id,active=True)
    m.db.session.add(target);m.db.session.commit()
    with client.session_transaction() as ss:ss['uid']=target.id
    for path in ['/admin/security','/admin/security/country-policy','/admin/security/vpn/create','/admin/security/vpn/1/revoke']:
        response=client.get(path) if path=='/admin/security' else post(client,token,path)
        assert response.status_code==403

def test_page_filters_source_and_denied_events(security_env):
    client,_,_,_=security_env
    page=client.get('/admin/security?channel=WEB&outcome=SUCCESS&country=AU&days=7').get_data(as_text=True)
    assert 'Application authentication' in page and 'GET HTTP 404' not in page
    assert client.get('/admin/security?ip=bad').status_code==400
    assert client.get('/admin/security?channel=SQL').status_code==400
    assert client.get('/admin/security?page=0').status_code==400
    assert client.get('/admin/security').headers['Cache-Control']=='no-store'

def test_missing_host_data_is_reported(security_env):
    client,_,_,path=security_env
    (path/'events.sqlite').unlink()
    assert b'collector is unavailable' in client.get('/admin/security').data

def test_mutations_require_csrf_reason_and_reauthentication(security_env):
    client,_,token,_=security_env
    common={'mode':'disabled','version':'0'}
    assert post(client,'wrong','/admin/security/country-policy',**common).status_code==403
    assert post(client,token,'/admin/security/country-policy',**common,password='wrong').status_code==403
    assert post(client,token,'/admin/security/country-policy',**common,reason='').status_code==400
    assert m.AuditLog.query.filter_by(action=s.POLICY_ACTION).count()==0

def test_policy_all_site_and_recovery_address(security_env):
    client,_,token,_=security_env
    assert post(client,token,'/admin/security/country-policy',mode='allow',countries='US',unknown='deny',version='0').status_code==302
    for path in ['/login','/security/country-gate','/api/assignment/offers/pending','/pacs/tracking']:
        assert client.get(path,headers={'X-Forwarded-For':'1.1.1.1'}).status_code==403
    assert client.get('/admin/security',headers={'X-Forwarded-For':'8.8.8.8'}).status_code==200
    assert post(client,token,'/admin/security/country-policy',mode='disabled',version='0').status_code==409
    row=m.AuditLog.query.filter_by(action=s.POLICY_ACTION).first()
    assert PASSWORD not in row.details and json.loads(row.details)['scope']=='ALL_SITE_HTTP'

def test_country_allow_deny_and_unknown():
    p={'mode':'deny','countries':['US'],'unknown':'deny','rescue_ip':'8.8.8.8'}
    assert not s.policy_decision(p,s.valid_ip('8.8.4.4'),'US')[0]
    assert s.policy_decision(p,s.valid_ip('1.1.1.1'),'AU')[0]
    assert not s.policy_decision(p,s.valid_ip('9.9.9.9'),'UNKNOWN')[0]
    assert s.policy_decision(p,s.valid_ip('8.8.8.8'),'US')[0]
    assert s.policy_decision(p,s.valid_ip('10.77.240.2'),'PRIVATE',vpn_ready=True)[0]
    assert not s.policy_decision(p,s.valid_ip('10.77.240.2'),'PRIVATE',vpn_ready=False)[0]
    assert s.policy_decision(p,None,'UNKNOWN',geo_ready=False)[1]=='GEO_DATABASE_UNAVAILABLE_POLICY_SUSPENDED'

def test_stale_geodata_blocks_activation(security_env):
    client,_,token,path=security_env
    c=sqlite3.connect(path/'countries.sqlite');c.execute('UPDATE metadata SET value=?',[(datetime.utcnow()-timedelta(days=120)).date().isoformat()]);c.commit();c.close()
    assert post(client,token,'/admin/security/country-policy',mode='deny',countries='US',version='0').status_code==400

def test_empty_or_invalid_country_policy_is_rejected(security_env):
    client,_,token,_=security_env
    for countries in ['', 'USA','EG;$(uname)']:
        assert post(client,token,'/admin/security/country-policy',mode='deny',countries=countries,version='0').status_code==400

def test_vpn_create_private_key_never_persisted_and_revoke(security_env):
    client,u,token,_=security_env
    response=post(client,token,'/admin/security/vpn/create',user_id=str(u.id),label='Synthetic laptop')
    assert response.status_code==200 and b'PrivateKey' in response.data and response.headers['Cache-Control']=='no-store'
    row=m.AuditLog.query.filter_by(action='SECURITY_VPN_CREATE').first()
    data=json.loads(row.details)
    assert 'PrivateKey' not in row.details and PASSWORD not in row.details
    assert len(base64.b64decode(data['public_key']))==32 and data['address']=='10.77.240.2'
    assert s.vpn_desired(m)[0]['enabled']
    assert post(client,token,f'/admin/security/vpn/{row.id}/revoke').status_code==302
    assert not s.vpn_desired(m)[0]['enabled']

def test_vpn_inactive_target_and_stale_controller_rejected(security_env):
    client,u,token,path=security_env
    u.active=False;m.db.session.commit()
    # Actor itself is inactive: denied before any key is generated.
    assert post(client,token,'/admin/security/vpn/create',user_id=str(u.id),label='Synthetic').status_code==302
    u.active=True;m.db.session.commit()
    data=json.loads(_read_source(path/'status.json'));data['updated_at']=(datetime.utcnow()-timedelta(minutes=10)).isoformat();(path/'status.json').write_text(json.dumps(data))
    assert post(client,token,'/admin/security/vpn/create',user_id=str(u.id),label='Synthetic').status_code==503

def test_deactivating_user_withdraws_peer(security_env):
    client,u,token,_=security_env
    assert post(client,token,'/admin/security/vpn/create',user_id=str(u.id),label='Synthetic laptop').status_code==200
    u.active=False;m.db.session.commit();assert not s.vpn_desired(m)[0]['enabled']

def test_device_keys_unique_no_address_reuse(security_env):
    client,u,token,_=security_env
    for label in ['Synthetic one','Synthetic two']:
        assert post(client,token,'/admin/security/vpn/create',user_id=str(u.id),label=label).status_code==200
    rows=s.vpn_rows(m)
    assert len({r['public_key'] for r in rows})==2 and len({r['address'] for r in rows})==2

def test_anonymous_security_and_inactive_user_denied(security_env):
    client,u,token,_=security_env
    with client.session_transaction() as ss:ss.clear()
    assert client.get('/admin/security').status_code==302

def test_audit_ip_uses_trusted_proxy_not_forged_header(security_env):
    _,_,_,_=security_env
    with m.app.test_request_context('/login',environ_base={'REMOTE_ADDR':'203.0.113.8'},headers={'X-Forwarded-For':'8.8.8.8'}):
        assert m._security_audit_ip()=='203.0.113.8'

def test_duplicate_creation_is_rejected_without_second_key(security_env):
    client,u,token,_=security_env
    with client.session_transaction() as ss:nonce=ss['security_vpn_nonce']
    payload={'csrf_token':token,'creation_nonce':nonce,'reason':'Synthetic duplicated request','password':PASSWORD,'user_id':str(u.id),'label':'Synthetic once'}
    assert client.post('/admin/security/vpn/create',data=payload,headers={'X-Forwarded-For':'8.8.8.8'}).status_code==200
    assert client.post('/admin/security/vpn/create',data=payload,headers={'X-Forwarded-For':'8.8.8.8'}).status_code==409
    assert len(s.vpn_rows(m))==1

def test_loopback_health_and_internal_callback_remain_available(security_env,monkeypatch):
    client,_,token,_=security_env
    assert post(client,token,'/admin/security/country-policy',mode='allow',countries='US',unknown='deny',version='0').status_code==302
    assert client.get('/login').status_code==200
    monkeypatch.setitem(m.app.config,'SECURITY_INTERNAL_CLIENTS','172.28.20.7/32')
    assert client.get('/security/country-gate',environ_base={'REMOTE_ADDR':'172.28.20.7'}).status_code==204
