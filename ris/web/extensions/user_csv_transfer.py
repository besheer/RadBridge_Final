"""Create-only, reviewed user migration. Never transfer credentials."""
import csv
import io
import secrets
import threading
import time
from functools import wraps

from flask import Blueprint, Response, abort, flash, redirect, render_template, request, session, url_for
from sqlalchemy.exc import IntegrityError
from werkzeug.security import generate_password_hash
from clinical_scope import SCOPE_COLUMNS

COLUMNS = ('username', 'full_name', 'role_code', 'branch_code', 'active',
           'department', 'specialty', 'phone', 'email', 'whatsapp', 'telegram', 'other_contact') + SCOPE_COLUMNS
MAX_BYTES = 2 * 1024 * 1024
MAX_ROWS = 500
TTL = 900
_stages = {}
_lock = threading.RLock()


def csv_safe(value):
    value = str(value or '')
    if value.startswith("'"):
        return "'" + value
    return "'" + value if value.lstrip().startswith(('=', '+', '-', '@')) or value.startswith(('\t', '\r')) else value


def csv_restore(value):
    if value.startswith("''"):
        return value[1:]
    return value[1:] if value.startswith("'") and csv_safe(value[1:]) == value else value


def parse_csv(raw):
    if not raw or len(raw) > MAX_BYTES:
        raise ValueError('الملف فارغ أو أكبر من 2 MB / Empty file or larger than 2 MB')
    try:
        content = raw.decode('utf-8-sig')
    except UnicodeDecodeError:
        raise ValueError('احفظ الملف بصيغة UTF-8 / Save the file as UTF-8') from None
    if '\x00' in content:
        raise ValueError('Invalid CSV / ملف CSV غير صالح')
    try:
        try:
            dialect = csv.Sniffer().sniff(content[:8192], delimiters=',;\t')
        except csv.Error:
            dialect = csv.excel
        reader = csv.reader(io.StringIO(content, newline=''), dialect, strict=True)
        headers = [v.strip().lower() for v in next(reader)]
        if len(set(headers)) != len(headers) or not set(COLUMNS[:-4]).issubset(headers) or not set(headers).issubset(COLUMNS):
            raise ValueError('استخدم أعمدة القالب دون إضافة حقول كلمات المرور / Use exactly the template columns; no password fields')
        rows = []
        for line, cells in enumerate(reader, 2):
            if not cells or not any(v.strip() for v in cells):
                continue
            if len(cells) != len(headers):
                raise ValueError('Row %s: incorrect column count / عدد أعمدة غير صحيح' % line)
            row = {k: '' for k in COLUMNS}
            row.update({k: csv_restore(v).strip() for k, v in zip(headers, cells)})
            rows.append((line, row))
            if len(rows) > MAX_ROWS:
                raise ValueError('الحد الأقصى 500 مستخدم / Maximum 500 users per file')
        if not rows:
            raise ValueError('لا توجد بيانات مستخدمين / No user rows')
        return rows
    except (csv.Error, StopIteration):
        raise ValueError('Invalid CSV / ملف CSV غير صالح') from None


def register(m):
    from user_access_policy import CONTACT_FIELDS, contacts, parse_contacts, save_contacts, require_manage_target
    import clinical_scope
    bp = Blueprint('user_csv', __name__)

    @bp.after_request
    def private_response(response):
        response.headers['Cache-Control'] = 'no-store'
        return response

    def manage(fn):
        @wraps(fn)
        @m.require_perm('users.view')
        def wrapped(*args, **kwargs):
            if not m.has_perm('users.manage'):
                abort(403)
            return fn(*args, **kwargs)
        return wrapped

    def csrf():
        token = session.get('user_csv_csrf')
        supplied = request.form.get('csrf_token', '')
        if not token or not secrets.compare_digest(token, supplied):
            abort(403)

    def context(**kw):
        if not session.get('user_csv_csrf'):
            session['user_csv_csrf'] = secrets.token_urlsafe(32)
        return dict(roles=m.Role.query.order_by(m.Role.code).all(),
                    branches=m.Branch.query.order_by(m.Branch.code).all(), columns=COLUMNS,
                    csrf_token=session['user_csv_csrf'], **kw)

    def fingerprint(role, branch):
        return (role.id, role.code, tuple(sorted(role.permissions())),
                (branch.id, branch.code, branch.active) if branch else None)

    def validate(rows):
        roles = {r.code.casefold(): r for r in m.Role.query.all()}
        branches = {b.code.casefold(): b for b in m.Branch.query.all()}
        existing = {u.username.casefold() for u in m.User.query.all()}
        seen = set()
        results = []
        for line, data in rows:
            item = dict(line=line, data=data, status='NEW', errors=[], identity=None)
            errors = item['errors']
            for key, limit in [('username', 80), ('full_name', 120), ('department', 80), ('specialty', 120)]:
                if len(data[key]) > limit or any(ord(c) < 32 for c in data[key]):
                    errors.append('%s: invalid value / قيمة غير صالحة' % key)
            if not data['username'] or any(c.isspace() for c in data['username']):
                errors.append('username: required without spaces / مطلوب بدون مسافات')
            if not data['full_name']:
                errors.append('full_name: required / الاسم مطلوب')
            folded = data['username'].casefold()
            if folded in seen:
                errors.append('Duplicate username in file / اسم مستخدم مكرر بالملف')
            seen.add(folded)
            if folded in existing:
                item['status'] = 'SKIP'
            role = roles.get(data['role_code'].casefold())
            branch = branches.get(data['branch_code'].casefold()) if data['branch_code'] else None
            if not role:
                errors.append('Unknown role_code / كود دور غير موجود')
            else:
                # Enforce authorization even for skipped rows; never silently accept escalation.
                require_manage_target(role=role)
            if data['branch_code'] and not branch:
                errors.append('Unknown branch_code / كود فرع غير موجود')
            if data['active'].lower() not in ('true', 'false', '1', '0', 'yes', 'no'):
                errors.append('active: use true or false / استخدم true أو false')
            try:
                item['contacts'] = parse_contacts({'contact_' + k: data[k] for k in CONTACT_FIELDS})
            except ValueError as exc:
                errors.append(str(exc))
            if role:
                item['identity'] = fingerprint(role, branch)
                item['role_id'] = role.id
                item['branch_id'] = branch.id if branch else None
                try:
                    item['scope'] = clinical_scope.parse(m, data, role)
                    if item['scope']:
                        _, devices, rooms = clinical_scope.catalog(m)
                        item['scope_catalog'] = tuple((key, tuple((d.id,d.branch_id,d.modality,d.ae_title,d.room) for d in value)) for key,value in sorted(devices.items()))
                except ValueError as exc:
                    errors.append(str(exc))
            item['active'] = data['active'].lower() in ('true', '1', 'yes')
            if errors:
                item['status'] = 'ERROR'
            results.append(item)
        return results

    def download(rows, filename):
        stream = io.StringIO(newline='')
        writer = csv.writer(stream, lineterminator='\r\n')
        writer.writerow(COLUMNS)
        writer.writerows([[csv_safe(row.get(k, '')) for k in COLUMNS] for row in rows])
        return Response(('\ufeff' + stream.getvalue()).encode('utf-8'),
                        content_type='text/csv; charset=utf-8',
                        headers={'Content-Disposition': 'attachment; filename="%s"' % filename,
                                 'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff'})

    @bp.get('/admin/users/export.csv')
    @m.require_perm('users.view')
    def export():
        profiles = {p.user_id: p for p in m.UserProfile.query.all()}
        rows = []
        for user in m.User.query.order_by(m.User.username):
            profile = profiles.get(user.id)
            rows.append(dict(username=user.username, full_name=user.full_name,
                             role_code=user.role.code, branch_code=user.branch.code if user.branch else '',
                             active='true' if user.active else 'false',
                             department=profile.department or '' if profile else '',
                             specialty=profile.specialty or '' if profile else '', **contacts(user),
                             **clinical_scope.export_values(m, user)))
        return download(rows, 'radbridge-users.csv')

    @bp.get('/admin/users/template.csv')
    @m.require_perm('users.view')
    def template():
        return download([], 'radbridge-users-template.csv')

    @bp.route('/admin/users/import', methods=['GET', 'POST'])
    @manage
    def upload():
        if request.method == 'GET':
            with _lock:
                for key, stage in list(_stages.items()):
                    if stage['actor'] == m.current_user().id or stage['expires'] <= time.monotonic():
                        del _stages[key]
            return render_template('user_csv_import.html', **context())
        if request.content_length and request.content_length > MAX_BYTES + 65536:
            abort(413)
        csrf()
        with _lock:
            for key, stage in list(_stages.items()):
                if stage['actor'] == m.current_user().id or stage['expires'] <= time.monotonic():
                    del _stages[key]
        file = request.files.get('file')
        try:
            rows = parse_csv(file.stream.read(MAX_BYTES + 1) if file else b'')
            results = validate(rows)
        except ValueError as exc:
            return render_template('user_csv_import.html', **context(error=str(exc))), 400
        actor = m.current_user()
        token = None
        if not any(i['errors'] for i in results) and any(i['status'] == 'NEW' for i in results):
            with _lock:
                now = time.monotonic()
                for key, stage in list(_stages.items()):
                    if stage['expires'] <= now or stage['actor'] == actor.id:
                        del _stages[key]
                while len(_stages) >= 16:
                    del _stages[next(iter(_stages))]
                token = secrets.token_urlsafe(32)
                _stages[token] = dict(actor=actor.id, expires=now + TTL, rows=rows, results=results)
        return render_template('user_csv_preview.html', **context(results=results, token=token,
                              new_count=sum(i['status'] == 'NEW' for i in results),
                              skip_count=sum(i['status'] == 'SKIP' for i in results),
                              error_count=sum(bool(i['errors']) for i in results)))

    @bp.post('/admin/users/import/apply')
    @manage
    def apply():
        csrf()
        token = request.form.get('preview_token', '')
        password = request.form.get('temporary_password', '')
        if not 10 <= len(password) <= 128:
            flash('كلمة المرور المؤقتة من 10 إلى 128 حرفاً. أعد معاينة الملف / Temporary password: 10–128 characters; preview again', 'error')
            return redirect(url_for('user_csv.upload'))
        with _lock:
            stage = _stages.get(token)
            if not stage or stage['actor'] != m.current_user().id or stage['expires'] <= time.monotonic():
                abort(409, description='Preview expired or unavailable; upload again / أعد رفع الملف للمعاينة')
            current = validate(stage['rows'])
            if current != stage['results']:
                _stages.pop(token, None)
                abort(409, description='Users, roles or branches changed; preview again / تغيرت البيانات، أعد المعاينة')
            try:
                created = 0
                for item in current:
                    if item['status'] != 'NEW':
                        continue
                    data = item['data']
                    user = m.User(username=data['username'], full_name=data['full_name'],
                                  role_id=item['role_id'], branch_id=item['branch_id'], active=item['active'],
                                  password_hash=generate_password_hash(password), must_change_password=True)
                    m.db.session.add(user)
                    m.db.session.flush()
                    save_contacts(user, item['contacts'], data)
                    clinical_scope.save(m, user, item['scope'])
                    m.audit('USER_CREATE', 'user', str(user.id), 'Created by reviewed CSV import')
                    created += 1
                m.audit('USER_CSV_IMPORT', 'user', '', 'Created=%s; skipped=%s' %
                        (created, sum(i['status'] == 'SKIP' for i in current)))
                m.db.session.commit()
            except IntegrityError:
                m.db.session.rollback()
                _stages.pop(token, None)
                abort(409, description='Concurrent user change; no users imported / لم يُحفظ أي مستخدم؛ أعد المعاينة')
            _stages.pop(token, None)
        flash('تم استيراد %s مستخدم وتخطي %s موجود. تغيير كلمة المرور مطلوب عند أول دخول / Imported %s; skipped %s existing users' %
              (created, sum(i['status'] == 'SKIP' for i in current), created, sum(i['status'] == 'SKIP' for i in current)), 'success')
        return redirect(url_for('admin_users'))

    m.app.register_blueprint(bp)
