"""Clinical scope configuration validation; malformed configured scopes fail closed."""
CLINICAL_ROLES = {'RADIOTHERAPY_PHYSICIAN', 'RADIOLOGIST', 'DOCTOR', 'CONSULTANT', 'RADIOLOGY_CONSULTANT', 'TECHNICIAN', 'NURSING'}

def normalize_scope(raw):
    if raw is None:
        return None
    # Corrupt configured scopes fail closed, never become unrestricted.
    if not isinstance(raw, dict) or raw.get('enabled') is not True:
        return {'enabled': True, 'invalid': True}
    if any(not isinstance(raw.get(k), list) or any(not isinstance(v, str) for v in raw[k])
           for k in ('modalities', 'device_keys', 'room_keys')):
        return {'enabled': True, 'invalid': True}
    if raw['device_keys'] and (not isinstance(raw.get('device_ids'), list) or
            any(type(value) is not int for value in raw['device_ids'])):
        return {'enabled': True, 'invalid': True}
    return raw


def scope_selection(values, role_code):
    enabled = str(values.get('scope_enabled', 'false')).strip().lower()
    if enabled not in ('true', 'false', '1', '0', 'yes', 'no', ''):
        raise ValueError('scope_enabled: true / false')
    lists = {k: sorted(set(v.strip() for v in str(values.get(k, '')).split('|') if v.strip()))
             for k in ('modalities', 'device_keys', 'room_keys')}
    if enabled in ('false', '0', 'no', ''):
        if any(lists.values()):
            raise ValueError('Enable clinical scope when specifying modalities/devices/rooms / فعّل التخصيص عند اختيار الأشعة أو الأجهزة أو الغرف')
        return None
    if role_code.upper() not in CLINICAL_ROLES:
        raise ValueError('Clinical scope is for doctors, technicians and nursing / التخصيص للأطباء والفنيين والتمريض')
    if not any(lists.values()):
        raise ValueError('Select at least one modality, device or room / اختر نوع أشعة أو جهازًا أو غرفة')
    return lists


def resolve_scope(lists, catalog):
    lists = {key: list(values) for key, values in lists.items()}
    modalities, devices, rooms = catalog
    lists['modalities'] = sorted(set(v.upper() for v in lists['modalities']))
    if not set(lists['modalities']).issubset(modalities):
        raise ValueError('Unknown modality / نوع أشعة غير موجود')
    if any(k not in devices or len(devices[k]) != 1 for k in lists['device_keys']):
        raise ValueError('Unknown or ambiguous device key (branch/AE) / كود جهاز غير موجود أو مكرر')
    if not set(lists['room_keys']).issubset(rooms):
        raise ValueError('Unknown room key (branch/room) / غرفة غير موجودة')
    return dict(enabled=True, device_ids=sorted(devices[key][0] for key in lists['device_keys']), **lists)


def parse_scope(values, role_code, catalog):
    selection = scope_selection(values, role_code)
    return None if selection is None else resolve_scope(selection, catalog)
