"""Registration field/date/sex and role branch decisions over explicit facts."""
from datetime import datetime

FIELDS = ('name', 'phone', 'national_id', 'address', 'email', 'nationality', 'dob', 'sex')

def validate_patient_fields(values, rules, validate_value, today):
    for key in FIELDS:
        ok, message = validate_value(rules.get('patient.'+key), values.get(key, ''))
        if not ok:
            raise ValueError(message)

    dob = (values.get('dob') or '').strip()
    if dob:
        try:
            parsed = datetime.strptime(dob, '%Y%m%d').date()
            if len(dob) != 8 or parsed > today:
                raise ValueError()
        except ValueError:
            raise ValueError('Enter a valid date of birth that is not in the future.')
    if (values.get('sex') or '').strip() not in ('', 'M', 'F', 'O'):
        raise ValueError('Choose a valid patient sex.')


def allowed_registration_branches(user):
    """None means all active branches; ordinary staff use their assigned branch."""
    if user and user.role and user.role.code in ('SUPER_ADMIN','CALL_CENTER'):
        return None
    return [user.branch_id] if user and getattr(user,'branch_id',None) else []
