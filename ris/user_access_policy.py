"""User contact storage and access review without sending messages."""
import ast,json,re
from functools import lru_cache
from pathlib import Path
CONTACT_FIELDS={'phone':'الهاتف / Phone','email':'البريد / Email','whatsapp':'WhatsApp','telegram':'Telegram username','other_contact':'تواصل آخر / Other contact'}
NO_REPORT_EDIT={'NURSING','TECHNICIAN','SERVICE','CASE_COORDINATOR'}
def contacts(user):
    import app as m
    profile=m.UserProfile.query.filter_by(user_id=user.id).first()
    data=m.user_profile_settings(profile).get('contacts',{}) if profile else {}
    return {key:str(data.get(key,'') or '') for key in CONTACT_FIELDS} if isinstance(data,dict) else {key:'' for key in CONTACT_FIELDS}
def parse_contacts(form,existing=None):
    out={}
    for key in CONTACT_FIELDS:
        value=(form.get('contact_'+key) or '').strip() if 'contact_'+key in form else (existing or {}).get(key,'')
        if len(value)>160:raise ValueError('Contact value is too long / بيانات الاتصال أطول من المسموح')
        if key in ('phone','whatsapp') and value:
            value=re.sub(r'[ ()-]','',value)
            if not re.fullmatch(r'\+?[0-9]{7,15}',value):raise ValueError('Invalid phone or WhatsApp number / رقم الهاتف غير صحيح')
        if key=='telegram' and value:
            value=value.lstrip('@')
            if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{4,31}',value):raise ValueError('Enter Telegram username / أدخل اسم مستخدم تليجرام')
        if key=='email' and value and not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',value):raise ValueError('Invalid email / البريد غير صحيح')
        if any(ord(c)<32 for c in value):raise ValueError('Invalid contact value')
        out[key]=value
    return out
def save_contacts(user,data,form):
    import app as m
    profile=m.get_user_profile(user)
    settings=m.user_profile_settings(profile);settings['contacts']=data
    profile.settings_json=json.dumps(settings,ensure_ascii=False)
    if 'department' in form:profile.department=(form.get('department') or '').strip()[:80]
    if 'specialty' in form:profile.specialty=(form.get('specialty') or '').strip()[:120]
def require_manage_target(user=None,role=None):
    import app as m
    actor=m.current_user()
    if not actor or not actor.active:m.abort(403)
    if actor.role and actor.role.code=='SUPER_ADMIN':return
    if user and user.role and (user.role.code=='SUPER_ADMIN' or '*' in user.role.permissions()):m.abort(403)
    if role:
        owned=set(actor.role.permissions() if actor.role else [])
        if role.code=='SUPER_ADMIN' or not set(role.permissions()).issubset(owned):m.abort(403)
@lru_cache(maxsize=1)
def route_catalog():
    import app as m
    tree=ast.parse(Path(m.__file__).read_text())
    gates={}
    for fn in tree.body:
        if not isinstance(fn,(ast.FunctionDef,ast.AsyncFunctionDef)):continue
        perms=[];login=False
        for dec in fn.decorator_list:
            if isinstance(dec,ast.Name) and dec.id=='login_required':login=True
            if isinstance(dec,ast.Call) and isinstance(dec.func,ast.Name) and dec.func.id=='require_perm' and dec.args and isinstance(dec.args[0],ast.Constant):
                perms.append(dec.args[0].value);login=True
        gates[fn.name]=(perms,login)
    rows=[]
    for rule in m.app.url_map.iter_rules():
        if rule.endpoint=='static' or 'GET' not in rule.methods:continue
        perms,login=gates.get(rule.endpoint,([],False))
        rows.append({'path':rule.rule,'endpoint':rule.endpoint,'permissions':perms,'login':login,'section':rule.rule.strip('/').split('/')[0] or 'dashboard','direct':'<' not in rule.rule})
    return sorted(rows,key=lambda x:(x['section'],x['path']))
def page_access(role,row):
    if not row['permissions']:return 'CUSTOM_CHECK'
    perms=set(role.permissions())
    if role.code=='SUPER_ADMIN':return 'ROLE_ALLOWED'
    if role.code in NO_REPORT_EDIT and 'reports.edit' in row['permissions']:return 'DENIED'
    if role.code=='RECEPTION' and any(p in ('payments.create','cashier.workstation') for p in row['permissions']):
        if '*' in perms or 'payments.create' in perms:perms.add('cashier.workstation')
        return 'BRANCH_DEPENDENT' if all('*' in perms or p in perms for p in row['permissions']) else 'DENIED'
    return 'ROLE_ALLOWED' if all('*' in perms or p in perms for p in row['permissions']) else 'DENIED'


def permission_catalog():
    import app as m
    names=set(m.ALL_PERMISSIONS)
    for values in m.ROLE_PERMS.values():names.update(values)
    for role in m.Role.query.all():names.update(role.permissions())
    tree=ast.parse(Path(m.__file__).read_text())
    for node in ast.walk(tree):
        if isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and node.func.id=='require_perm' and node.args and isinstance(node.args[0],ast.Constant):
            names.add(node.args[0].value)
    return sorted(name for name in names if isinstance(name,str) and name!='*')
