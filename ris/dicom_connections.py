import ipaddress,re,subprocess,sys,json

KINDS={'MINI_PACS':'Mini PACS','WORKLIST':'Worklist'}

def ae_title(value):
    value=str(value or '').strip().upper()
    if not value or len(value)>16 or any(ord(c)<32 or ord(c)>126 or c=='\\' for c in value):
        raise ValueError('AE Title: 1–16 ASCII characters, without backslash.')
    return value

def host(value):
    value=str(value or '').strip()
    if not value:return ''
    try:ipaddress.ip_address(value);return value
    except ValueError:pass
    if len(value)>253 or not all(re.fullmatch(r'[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?',part) for part in value.rstrip('.').split('.')):
        raise ValueError('Enter an IP address or DDNS hostname, without http://, path or port.')
    return value.rstrip('.').lower()

def port(value):
    try:value=int(str(value))
    except (ValueError,TypeError):raise ValueError('Port must be an integer from 1 to 65535.')
    if not 1<=value<=65535:raise ValueError('Port must be from 1 to 65535.')
    return value

def branch_allowed(branch_id):
    import app as m
    user=m.current_user()
    return bool(user and (m.has_perm('*') or (user.branch_id and user.branch_id==branch_id)))

def echo(target_host,target_port,called_ae,calling_ae='RADBRIDGERIS'):
    target_host=host(target_host)
    if not target_host:raise ValueError('Configure the IP or DDNS first.')
    args=[sys.executable,'-m','dicom_echo_worker',target_host,str(port(target_port)),ae_title(called_ae),ae_title(calling_ae)]
    try:
        result=subprocess.run(args,capture_output=True,text=True,timeout=12)
        data=json.loads(result.stdout) if result.returncode==0 else {}
        if data.get('result') in ('SUCCESS','FAILED','UNREACHABLE'):
            return data
    except subprocess.TimeoutExpired:return {'result':'UNREACHABLE','message':'Connection test timed out.','elapsed_ms':12000}
    except (ValueError,OSError):pass
    return {'result':'FAILED','message':'Connection test could not be completed.','elapsed_ms':0}
