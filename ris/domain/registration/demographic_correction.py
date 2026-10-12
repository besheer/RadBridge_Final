"""Input policy for a reviewed demographic request, never an identity mutation."""
import re
from datetime import datetime

FIELDS={'name':'الاسم / Name','dob':'تاريخ الميلاد / DOB','sex':'النوع / Sex','phone':'الهاتف / Phone','national_id':'الرقم القومي / National ID','address':'العنوان / Address','email':'البريد / Email','nationality':'الجنسية / Nationality'}
IDENTITY_FIELDS={'name','dob','sex'}


def normalize_value(field, value, today):
    if field not in FIELDS:raise ValueError('Unsupported patient field')
    value=str(value or '').strip()
    if len(value)>255:raise ValueError('Value is too long / القيمة أطول من المسموح')
    if field=='name' and len(value.split())<3:raise ValueError('Three-part name required / الاسم ثلاثي مطلوب')
    if field=='dob':
        value=value.replace('-','')
        if not re.fullmatch(r'[0-9]{8}',value):raise ValueError('Invalid date of birth')
        try:born=datetime.strptime(value,'%Y%m%d').date()
        except ValueError:raise ValueError('Invalid date of birth')
        if born>today:raise ValueError('Date of birth cannot be in the future')
    if field=='sex' and value not in ('M','F','O'):raise ValueError('Select M, F or O')
    if field=='email' and value and not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',value):raise ValueError('Invalid email')
    if any(ord(c)<32 for c in value):raise ValueError('Invalid value')
    return value
