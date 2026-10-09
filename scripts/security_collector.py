"""Root-only host collector/controller. Application receives sanitized, read-only data."""
import base64
import datetime as dt
import hashlib
import ipaddress
import json
import os
import re
import sqlite3
import subprocess
from pathlib import Path

DATA = Path('/opt/radbridge/config/server-security/data')
STATE = Path('/opt/radbridge/config/server-security/state')
IFACE = 'wg-radbridge'
CONFIG = Path('/etc/wireguard/wg-radbridge.conf')
RIS = 'radbridge-ris-95fee0e-canary'

def run(args, **kw):
    return subprocess.run(args, capture_output=True, text=True, timeout=45, **kw)

def atomic_json(path, data):
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(data))
    tmp.chmod(0o600)
    os.replace(tmp, path)

def ip_value(text):
    try:return str(ipaddress.ip_address(text))
    except ValueError:return ''

def geo(c, text):
    try:
        ip = ipaddress.ip_address(text)
        if not ip.is_global:return 'PRIVATE'
        key = f'{int(ip):032x}'
        row = c.execute('SELECT last,country FROM ranges WHERE version=? AND first<=? ORDER BY first DESC LIMIT 1',(ip.version,key)).fetchone()
        return row[1] if row and key <= row[0] else 'UNKNOWN'
    except (ValueError, sqlite3.Error):return 'UNKNOWN'

def ssh_event(record):
    msg = record.get('MESSAGE','')
    if not isinstance(msg,str):return None
    match = re.search(r'(Accepted|Failed) (password|publickey) for (?:invalid user )?(\S+) from ([0-9a-fA-F:.]+)',msg)
    if not match:return None
    action, method, account, ip = match.groups()
    timestamp = dt.datetime.fromtimestamp(int(record['__REALTIME_TIMESTAMP'])/1e6,dt.timezone.utc).replace(tzinfo=None).isoformat(timespec='seconds')
    return (record['__CURSOR'],timestamp,'SSH','SUCCESS' if action=='Accepted' else 'FAILED',ip_value(ip),account[:80],method)

def collect_journal(events, country_db, state):
    args = ['journalctl','-u','ssh','--no-pager','-o','json']
    args += ['--after-cursor',state['ssh_cursor']] if state.get('ssh_cursor') else ['--since','7 days ago']
    p = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    cursor, batch = state.get('ssh_cursor',''), []
    for line in p.stdout:
        record = json.loads(line)
        cursor = record.get('__CURSOR',cursor)
        event = ssh_event(record)
        if event:
            key, stamp, channel, outcome, ip, account, detail = event
            batch.append((key,stamp,channel,outcome,ip,geo(country_db,ip),account,detail))
        if len(batch)==1000:
            events.executemany('INSERT OR IGNORE INTO events(event_key,timestamp,channel,outcome,ip,country,account,detail) VALUES(?,?,?,?,?,?,?,?)',batch);batch=[]
    if batch:events.executemany('INSERT OR IGNORE INTO events(event_key,timestamp,channel,outcome,ip,country,account,detail) VALUES(?,?,?,?,?,?,?,?)',batch)
    _, error=p.communicate(timeout=30)
    if p.returncode:raise RuntimeError('SSH journal read failed; collector cursor was not advanced')
    state['ssh_cursor']=cursor

def application_data(last_id):
    code="""import json,app as m
from security_dashboard import vpn_desired
with m.app.app_context():
 rows=m.AuditLog.query.filter(m.AuditLog.id>LAST_ID,m.AuditLog.action.in_(['LOGIN','LOGIN_FAILED'])).order_by(m.AuditLog.id).limit(10000).all()
 print(json.dumps({'web':[{'id':r.id,'timestamp':r.created_at.isoformat(timespec='seconds'),'ip':r.ip,'account':r.username or '', 'outcome':'SUCCESS' if r.action=='LOGIN' else 'FAILED'} for r in rows], 'vpn':vpn_desired(m)}))
""".replace('LAST_ID',str(int(last_id)))
    p=run(['docker','exec',RIS,'python','-c',code])
    if p.returncode:raise RuntimeError('Application security source unavailable')
    return json.loads(p.stdout)

def collect_other_journal(events,country_db,state,kind):
    cursor_key=kind.lower()+'_cursor'
    args=['journalctl','--no-pager','-o','json', 'SYSLOG_IDENTIFIER=sudo' if kind=='SUDO' else '_TRANSPORT=kernel']
    args += ['--after-cursor',state[cursor_key]] if state.get(cursor_key) else ['--since','7 days ago']
    p=subprocess.Popen(args,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    cursor=state.get(cursor_key,'')
    for line in p.stdout:
        r=json.loads(line);cursor=r.get('__CURSOR',cursor);msg=r.get('MESSAGE','')
        if not isinstance(msg,str):continue
        ip,account,outcome,detail='','','',''
        if kind=='SUDO':
            if 'authentication failure' in msg or 'incorrect password' in msg:
                outcome='FAILED';detail='Privileged authentication failed'
                match=re.search(r'user=(\S+)',msg);account=match.group(1)[:80] if match else ''
            elif 'COMMAND=' in msg:
                outcome='SUCCESS';detail='Privileged command invoked (arguments excluded)'
                account=msg.split(':',1)[0].strip()[:80]
        elif '[UFW BLOCK]' in msg:
            src=re.search(r'\bSRC=([0-9a-fA-F:.]+)',msg);proto=re.search(r'\bPROTO=(\w+)',msg);port=re.search(r'\bDPT=(\d+)',msg)
            ip=ip_value(src.group(1)) if src else '';outcome='REJECTED'
            detail='Firewall blocked '+(proto.group(1) if proto else '')+' port '+(port.group(1) if port else '—')
        if outcome:
            stamp=dt.datetime.fromtimestamp(int(r['__REALTIME_TIMESTAMP'])/1e6,dt.timezone.utc).replace(tzinfo=None).isoformat(timespec='seconds')
            events.execute('INSERT OR IGNORE INTO events(event_key,timestamp,channel,outcome,ip,country,account,detail) VALUES(?,?,?,?,?,?,?,?)',(r['__CURSOR'],stamp,kind,outcome,ip,geo(country_db,ip),account,detail))
    p.communicate(timeout=30)
    if p.returncode:raise RuntimeError(kind+' journal unavailable')
    state[cursor_key]=cursor

def sync_vpn(desired):
    if not CONFIG.exists() or run(['wg','show',IFACE,'public-key']).returncode:
        return {'ready':False}
    valid=[]
    used=set()
    for peer in desired:
        key=peer['public_key'];address=ipaddress.ip_address(peer['address'])
        if not re.fullmatch(r'[A-Za-z0-9+/]{43}=',key) or len(base64.b64decode(key,validate=True))!=32:
            raise ValueError('Invalid WireGuard public key')
        if address not in ipaddress.ip_network('10.77.240.0/24') or str(address) in ('10.77.240.0','10.77.240.1','10.77.240.255'):
            raise ValueError('Invalid WireGuard peer address')
        if peer['enabled']:
            if str(address) in used:raise ValueError('Duplicate VPN address')
            used.add(str(address));valid.append((key,str(address)))
    current=CONFIG.read_text()
    header=current.split('[Peer]')[0].rstrip()+'\n'
    candidate=header+''.join(f'\n[Peer]\nPublicKey = {key}\nAllowedIPs = {address}/32\n' for key,address in valid)
    if candidate!=current:
        temp=CONFIG.parent/'rb-wg-stage.conf';temp.write_text(candidate);temp.chmod(0o600)
        stripped=run(['wg-quick','strip',str(temp)])
        if stripped.returncode:raise RuntimeError('WireGuard configuration validation failed')
        syncfile=CONFIG.parent/'rb-wg-sync.conf';syncfile.write_text(stripped.stdout);syncfile.chmod(0o600)
        try:applied=run(['wg','syncconf',IFACE,str(syncfile)])
        finally:syncfile.unlink(missing_ok=True)
        if applied.returncode:raise RuntimeError('WireGuard peer synchronization failed')
        os.replace(temp,CONFIG)
    handshakes=run(['wg','show',IFACE,'latest-handshakes'])
    if handshakes.returncode:raise RuntimeError('WireGuard state read failed')
    peers={}
    for line in handshakes.stdout.splitlines():
        key,stamp=line.split();value=int(stamp)
        peers[key]={'handshake_at':dt.datetime.fromtimestamp(value,dt.timezone.utc).replace(tzinfo=None).isoformat(timespec='seconds') if value else None}
    return {'ready':True,'public_key':run(['wg','show',IFACE,'public-key']).stdout.strip(),'endpoint':'198.244.185.119:51820','peers':peers,'synced_at':dt.datetime.utcnow().isoformat(timespec='seconds')}

def collect_http(events,country_db,state):
    path=Path('/var/log/radbridge-security-http.log')
    if not path.is_file():return
    st=path.stat();offset=state.get('http_offset',0)
    if state.get('http_inode')!=st.st_ino or st.st_size<offset:offset=0
    with path.open() as stream:
        stream.seek(offset)
        for line in stream:
            r=json.loads(line);status=int(r['status'])
            if status in (401,403,404,429) or status>=500:
                ip=ip_value(r['ip']);stamp=dt.datetime.fromisoformat(r['time']).astimezone(dt.timezone.utc).replace(tzinfo=None).isoformat(timespec='seconds')
                key='HTTP:'+hashlib.sha256((str(st.st_ino)+':'+line).encode()).hexdigest()
                events.execute('INSERT OR IGNORE INTO events(event_key,timestamp,channel,outcome,ip,country,account,detail) VALUES(?,?,?,?,?,?,?,?)',(key,stamp,'HTTP','REJECTED',ip,geo(country_db,ip),'',r['method']+' HTTP '+str(status)))
        state['http_offset']=stream.tell();state['http_inode']=st.st_ino

def main():
    DATA.mkdir(parents=True,exist_ok=True,mode=0o700);STATE.mkdir(parents=True,exist_ok=True,mode=0o700)
    sp=STATE/'collector.json';state=json.loads(sp.read_text()) if sp.exists() else {}
    events=sqlite3.connect(DATA/'events.sqlite',timeout=10)
    events.execute('PRAGMA journal_mode=DELETE')
    events.execute('CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY,event_key TEXT UNIQUE,timestamp TEXT,channel TEXT,outcome TEXT,ip TEXT,country TEXT,account TEXT,detail TEXT)')
    events.execute('CREATE INDEX IF NOT EXISTS security_time ON events(timestamp)')
    events.execute('CREATE INDEX IF NOT EXISTS security_channel ON events(channel,timestamp)')
    country_db=sqlite3.connect((DATA/'countries.sqlite').resolve().as_uri()+'?mode=ro',uri=True)
    errors=[]
    try:collect_journal(events,country_db,state)
    except Exception as exc:errors.append(type(exc).__name__+': SSH collection failed')
    for kind in ['SUDO','FIREWALL']:
        try:collect_other_journal(events,country_db,state,kind)
        except Exception as exc:errors.append(type(exc).__name__+': '+kind+' collection failed')
    appdata=None
    try:
        appdata=application_data(state.get('web_id',0))
        for row in appdata['web']:
            ip=ip_value(row['ip'])
            events.execute('INSERT OR IGNORE INTO events(event_key,timestamp,channel,outcome,ip,country,account,detail) VALUES(?,?,?,?,?,?,?,?)',('WEB:'+str(row['id']),row['timestamp'],'WEB',row['outcome'],ip,geo(country_db,ip),row['account'][:80],'Application authentication'))
            state['web_id']=row['id']
    except Exception as exc:errors.append(type(exc).__name__+': application security collection failed')
    try:collect_http(events,country_db,state)
    except Exception as exc:errors.append(type(exc).__name__+': HTTP collection failed')
    events.execute('DELETE FROM events WHERE timestamp<?',[(dt.datetime.utcnow()-dt.timedelta(days=30)).isoformat(timespec='seconds')]);events.commit();events.close();country_db.close()
    (DATA/'events.sqlite').chmod(0o600)
    atomic_json(sp,state)
    vpn={'ready':False}
    if appdata is not None:
        try:vpn=sync_vpn(appdata['vpn'])
        except Exception as exc:errors.append(type(exc).__name__+': VPN synchronization failed')
    banned=run(['fail2ban-client','get','sshd','banip'])
    ips=[x for x in banned.stdout.split() if ip_value(x)] if banned.returncode==0 else []
    result={'updated_at':dt.datetime.utcnow().isoformat(timespec='seconds'),'errors':errors,'vpn':vpn,'fail2ban':{'active':banned.returncode==0,'banned_count':len(ips),'banned_ips':ips},'reboot_required':Path('/var/run/reboot-required').exists()}
    atomic_json(DATA/'status.json',result)
    print(json.dumps({'collected':True,'errors':errors,'VPN_ready':vpn['ready'],'banned_count':len(ips)}))
    if errors:raise SystemExit(1)

if __name__=='__main__':main()
