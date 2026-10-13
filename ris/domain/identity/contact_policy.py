"""Contact input validation and access-review labels; not a route authorization gate."""
import re
CONTACT_FIELDS={'phone':'الهاتف / Phone','email':'البريد / Email','whatsapp':'WhatsApp','telegram':'Telegram username','other_contact':'تواصل آخر / Other contact'}
NO_REPORT_EDIT={'NURSING','TECHNICIAN','SERVICE','CASE_COORDINATOR'}

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

def page_access(role,row):
    if not row['permissions']:return 'CUSTOM_CHECK'
    perms=set(role.permissions())
    if role.code=='SUPER_ADMIN':return 'ROLE_ALLOWED'
    if role.code in NO_REPORT_EDIT and 'reports.edit' in row['permissions']:return 'DENIED'
    if role.code=='RECEPTION' and any(p in ('payments.create','cashier.workstation') for p in row['permissions']):
        if '*' in perms or 'payments.create' in perms:perms.add('cashier.workstation')
        return 'BRANCH_DEPENDENT' if all('*' in perms or p in perms for p in row['permissions']) else 'DENIED'
    return 'ROLE_ALLOWED' if all('*' in perms or p in perms for p in row['permissions']) else 'DENIED'
