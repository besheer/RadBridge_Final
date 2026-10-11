"""Manual RT record input validation; no clinical decision or device control."""
from datetime import datetime,timezone
from decimal import Decimal,InvalidOperation
from zoneinfo import ZoneInfo

def amount(value):
    try:d=Decimal(str(value))
    except InvalidOperation:raise ValueError('Invalid dose or quantity / قيمة غير صحيحة')
    if not d.is_finite() or d<=0 or d>=Decimal('1000000000000') or d.as_tuple().exponent < -6:raise ValueError('Use a positive decimal with at most six decimal places / قيمة موجبة بحد أقصى 6 خانات عشرية')
    return d


def text(value,minimum=1,maximum=300):
    value=str(value or '').strip()
    if not minimum<=len(value)<=maximum:raise ValueError('Required text is missing or too long / البيانات المطلوبة ناقصة أو طويلة')
    return value


def local_time(value):
    try:dt=datetime.fromisoformat(value)
    except (ValueError,TypeError):raise ValueError('Invalid scheduled date / موعد غير صحيح')
    if dt.tzinfo is None:
        zone=ZoneInfo('Africa/Cairo')
        if dt.replace(tzinfo=zone,fold=0).utcoffset()!=dt.replace(tzinfo=zone,fold=1).utcoffset():raise ValueError('Specify an unambiguous scheduled time / وقت غير واضح بسبب تغيير الساعة')
        dt=dt.replace(tzinfo=zone)
    return dt.astimezone(timezone.utc).replace(tzinfo=None)

