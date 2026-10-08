import csv
import io
import json
import re
import time

import pytest
from werkzeug.security import check_password_hash

import app as m
import user_csv_transfer as t


@pytest.fixture(autouse=True)
def isolated(app_ctx, monkeypatch):
    monkeypatch.setattr(m.db.session, 'commit', m.db.session.flush)
    t._stages.clear()
    yield
    m.db.session.rollback()
    m.db.session.remove()
    t._stages.clear()


@pytest.fixture
def actor(monkeypatch):
    role = m.Role.query.filter_by(code='SUPER_ADMIN').one()
    u = m.User(username='CSV-ACTOR', full_name='Synthetic Admin', role_id=role.id,
               active=True, password_hash='not-a-credential')
    m.db.session.add(u)
    m.db.session.flush()
    monkeypatch.setattr(m, 'current_user', lambda: u)
    c = m.app.test_client()
    with c.session_transaction() as s:
        s['uid'] = u.id
        s['user_csv_csrf'] = 'synthetic-csrf'
    return c, u


def row(**kw):
    value = {k: '' for k in t.COLUMNS}
    value.update(username='CSV-NEW', full_name='طبيب تجريبي', role_code='RADIOLOGIST', active='true')
    value.update(kw)
    return value


def data(*rows):
    out = io.StringIO(newline='')
    writer = csv.DictWriter(out, fieldnames=t.COLUMNS)
    writer.writeheader()
    writer.writerows(rows)
    return out.getvalue().encode('utf-8-sig')


def preview(c, *rows, raw=None):
    return c.post('/admin/users/import', data={'csrf_token': 'synthetic-csrf',
                  'file': (io.BytesIO(raw if raw is not None else data(*rows)), 'users.csv')})


def token(response):
    match = re.search(rb'name="preview_token" value="([^"]+)"', response.data)
    return match[1].decode() if match else None


def apply(c, tok, **extra):
    return c.post('/admin/users/import/apply', data=dict(csrf_token='synthetic-csrf',
                   preview_token=tok or '', temporary_password='Synthetic-Only-Password', **extra))


def test_export_template_roundtrip_no_credentials_and_safe_excel(actor):
    c, u = actor
    u.full_name = '=1+1'
    profile = m.get_user_profile(u)
    profile.department = 'أشعة'
    profile.settings_json = json.dumps({'contacts': {'phone': '+201000000000', 'email': 'test@example.test'}})
    response = c.get('/admin/users/export.csv')
    assert response.status_code == 200 and response.data.startswith(b'\xef\xbb\xbf')
    assert response.headers['Cache-Control'] == 'no-store'
    assert b'password' not in response.data and b'not-a-credential' not in response.data
    records = t.parse_csv(response.data)
    exported = next(r for _, r in records if r['username'] == u.username)
    assert exported['full_name'] == '=1+1' and exported['department'] == 'أشعة'
    assert exported['phone'] == '+201000000000'
    assert b"'=1+1" in response.data and b"'+201000000000" in response.data
    template = c.get('/admin/users/template.csv')
    assert template.status_code == 200
    assert list(csv.reader(io.StringIO(template.data.decode('utf-8-sig')))) == [list(t.COLUMNS)]


def test_preview_then_atomic_create_contacts_skip_existing_and_replay(actor):
    c, u = actor
    old_hash = u.password_hash
    profile = m.get_user_profile(u)
    profile.settings_json = json.dumps({'image_viewer': 'WEASIS'})
    before = m.User.query.count()
    response = preview(c, row(username=u.username, full_name='Unwanted change'),
                       row(phone='+201000000000', department='أشعة', specialty='CT', active='false'))
    assert response.status_code == 200 and token(response)
    assert m.User.query.count() == before
    assert b'SKIP' in response.data
    assert apply(c, token(response)).status_code == 302
    assert m.User.query.count() == before + 1
    new = m.User.query.filter_by(username='CSV-NEW').one()
    assert new.full_name == 'طبيب تجريبي' and not new.active and new.must_change_password
    assert check_password_hash(new.password_hash, 'Synthetic-Only-Password')
    assert u.full_name == 'Synthetic Admin' and u.password_hash == old_hash
    assert m.user_profile_settings(profile)['image_viewer'] == 'WEASIS'
    new_profile = m.UserProfile.query.filter_by(user_id=new.id).one()
    assert new_profile.department == 'أشعة' and new_profile.specialty == 'CT'
    assert m.user_profile_settings(new_profile)['contacts']['phone'] == '+201000000000'
    log = m.AuditLog.query.filter_by(action='USER_CSV_IMPORT').one()
    assert 'Created=1' in log.details and 'skipped=1' in log.details
    assert 'Password' not in log.details and '+20' not in log.details
    assert apply(c, token(response)).status_code == 409


@pytest.mark.parametrize('change', [dict(username=''), dict(username='a b'), dict(full_name=''),
    dict(username='x'*81), dict(role_code='MISSING'), dict(branch_code='MISSING'),
    dict(active='maybe'), dict(email='bad'), dict(phone='abc'), dict(telegram='https://t.me/name'),
    dict(department='x'*81), dict(other_contact='x'*161)])
def test_invalid_batch_cannot_create_any_users(actor, change):
    c, u = actor
    before = m.User.query.count()
    response = preview(c, row(username='CSV-VALID'), row(**change))
    assert response.status_code == 200 and not token(response)
    assert b'ERROR' in response.data and m.User.query.count() == before
    assert apply(c, '').status_code == 409


def test_casefold_duplicates_and_existing_skip(actor):
    c, u = actor
    duplicate = preview(c, row(username='MixedCase'), row(username='mixedcase'))
    assert not token(duplicate) and b'Duplicate username' in duplicate.data
    skipped = preview(c, row(username=u.username.lower()))
    assert not token(skipped) and b'SKIP' in skipped.data


@pytest.mark.parametrize('raw', [b'', b'\xff', b'a,a\n1,2', b'username,password\nuser,secret',
    b'\x00', b'a'*(t.MAX_BYTES+1)])
def test_malformed_files(raw):
    with pytest.raises(ValueError):
        t.parse_csv(raw)


def test_limit_and_delimiters():
    with pytest.raises(ValueError):
        t.parse_csv(data(*[row(username=str(i)) for i in range(t.MAX_ROWS+1)]))
    raw = data(row()).decode('utf-8-sig').replace(',', ';').encode()
    assert t.parse_csv(raw)[0][1]['username'] == 'CSV-NEW'


@pytest.mark.parametrize('value',["'=1", "'normal", '=1+1', '@SUM(1)', '+201000000000', '-1', 'طبيب'])
def test_formula_safety_reversible(value):
    assert t.csv_restore(t.csv_safe(value)) == value


def test_mid_batch_integrity_failure_rolls_back_all(actor, monkeypatch):
    from sqlalchemy.exc import IntegrityError
    c,u=actor
    tok=token(preview(c,row(username='CSV-ATOMIC-1'),row(username='CSV-ATOMIC-2')))
    original=m.db.session.flush
    def fail_second(*args,**kwargs):
        if any(isinstance(obj,m.User) and obj.username=='CSV-ATOMIC-2' for obj in m.db.session.new):
            raise IntegrityError('synthetic unique constraint',{},Exception('synthetic'))
        return original(*args,**kwargs)
    monkeypatch.setattr(m.db.session,'flush',fail_second)
    assert apply(c,tok).status_code==409
    assert m.User.query.filter(m.User.username.in_(['CSV-ATOMIC-1','CSV-ATOMIC-2'])).count()==0


@pytest.mark.parametrize('role_code', ['RECEPTION', 'NURSING', 'TECHNICIAN', 'RADIOLOGIST', 'FINANCE', 'CASE_COORDINATOR'])
def test_direct_urls_denied(actor, role_code):
    c, u = actor
    role = m.Role.query.filter_by(code=role_code).first()
    if not role:
        role = m.Role(code=role_code, name=role_code, permissions_json='[]')
        m.db.session.add(role)
    role.permissions_json = '[]'
    m.db.session.flush()
    u.role = role
    for path in ['/admin/users/export.csv', '/admin/users/template.csv', '/admin/users/import']:
        assert c.get(path).status_code == 403
    assert preview(c, row()).status_code == 403
    assert apply(c, 'missing').status_code == 403


def test_readonly_export_allowed_but_import_denied_and_inactive_denied(actor):
    c, u = actor
    role = m.Role(code='CSV-READONLY', name='Read only', permissions_json='["users.view"]')
    m.db.session.add(role)
    m.db.session.flush()
    u.role = role
    assert c.get('/admin/users/export.csv').status_code == 200
    assert c.get('/admin/users/template.csv').status_code == 200
    assert c.get('/admin/users/import').status_code == 403
    assert preview(c, row()).status_code == 403
    u.active = False
    assert c.get('/admin/users/export.csv').status_code == 403


def test_non_superadmin_cannot_escalate(actor):
    c, u = actor
    role = m.Role(code='CSV-MANAGER', name='Manager', permissions_json='["users.view","users.manage"]')
    m.db.session.add(role)
    m.db.session.flush()
    u.role = role
    assert preview(c, row(role_code='SUPER_ADMIN')).status_code == 403
    target = m.Role.query.filter_by(code='RADIOLOGIST').one()
    target.permissions_json = '["reports.edit"]'
    assert preview(c, row()).status_code == 403


def test_csrf_owner_expiry_cancel_and_changed_state(actor, monkeypatch):
    c, u = actor
    assert c.post('/admin/users/import', data={}).status_code == 403
    response = preview(c, row())
    tok = token(response)
    assert c.post('/admin/users/import/apply', data={'preview_token':tok}).status_code == 403
    t._stages[tok]['actor'] += 1
    assert apply(c, tok).status_code == 409
    t._stages[tok]['actor'] = u.id
    t._stages[tok]['expires'] = time.monotonic()-1
    assert apply(c, tok).status_code == 409
    tok = token(preview(c, row()))
    c.get('/admin/users/import')
    assert apply(c, tok).status_code == 409
    tok = token(preview(c, row()))
    m.Role.query.filter_by(code='RADIOLOGIST').one().permissions_json = '["reports.view"]'
    assert apply(c, tok).status_code == 409
    assert not m.User.query.filter_by(username='CSV-NEW').first()


def test_concurrent_existing_user_requires_new_preview(actor):
    c, u = actor
    tok = token(preview(c, row()))
    m.db.session.add(m.User(username='CSV-NEW', full_name='Other creator', password_hash='unchanged', role_id=u.role_id))
    m.db.session.flush()
    assert apply(c, tok).status_code == 409
    assert m.User.query.filter_by(username='CSV-NEW').one().password_hash == 'unchanged'
