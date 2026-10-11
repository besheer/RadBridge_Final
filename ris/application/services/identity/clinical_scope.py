"""Explicit clinical work scope, independent of role permissions and assignment."""
import json
import secrets
from flask import abort, current_app, g, has_request_context, request, session
from sqlalchemy import and_, event, false, func, or_, select
from sqlalchemy.orm import Session, with_loader_criteria

CLINICAL_ROLES = {'RADIOTHERAPY_PHYSICIAN', 'RADIOLOGIST', 'DOCTOR', 'CONSULTANT', 'RADIOLOGY_CONSULTANT', 'TECHNICIAN', 'NURSING'}
SCOPE_COLUMNS = ('scope_enabled', 'modalities', 'device_keys', 'room_keys')


def catalog(m):
    devices = m.Device.query.order_by(m.Device.branch_id, m.Device.modality, m.Device.name).all()
    device_keys = {}
    rooms = {}
    modalities = set()
    for device in devices:
        modality = str(device.modality or '').upper()
        modalities.add(modality)
        key = '%s/%s' % (device.branch.code, device.ae_title)
        device_keys.setdefault(key, []).append(device)
        if device.room:
            rooms['%s/%s' % (device.branch.code, device.room)] = (device.branch_id, device.room)
    modalities.update(str(p.modality or '').upper() for p in m.Procedure.query.all())
    modalities.discard('')
    return modalities, device_keys, rooms


def read(m, user):
    user_id = getattr(user, 'id', None)
    profile = m.UserProfile.query.filter_by(user_id=user_id).first() if user_id else None
    raw = m.user_profile_settings(profile).get('clinical_scope') if profile else None
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


def parse(m, values, role):
    enabled = str(values.get('scope_enabled', 'false')).strip().lower()
    if enabled not in ('true', 'false', '1', '0', 'yes', 'no', ''):
        raise ValueError('scope_enabled: true / false')
    lists = {k: sorted(set(v.strip() for v in str(values.get(k, '')).split('|') if v.strip()))
             for k in ('modalities', 'device_keys', 'room_keys')}
    if enabled in ('false', '0', 'no', ''):
        if any(lists.values()):
            raise ValueError('Enable clinical scope when specifying modalities/devices/rooms / فعّل التخصيص عند اختيار الأشعة أو الأجهزة أو الغرف')
        return None
    if role.code.upper() not in CLINICAL_ROLES:
        raise ValueError('Clinical scope is for doctors, technicians and nursing / التخصيص للأطباء والفنيين والتمريض')
    if not any(lists.values()):
        raise ValueError('Select at least one modality, device or room / اختر نوع أشعة أو جهازًا أو غرفة')
    modalities, devices, rooms = catalog(m)
    lists['modalities'] = sorted(set(v.upper() for v in lists['modalities']))
    if not set(lists['modalities']).issubset(modalities):
        raise ValueError('Unknown modality / نوع أشعة غير موجود')
    if any(k not in devices or len(devices[k]) != 1 for k in lists['device_keys']):
        raise ValueError('Unknown or ambiguous device key (branch/AE) / كود جهاز غير موجود أو مكرر')
    if not set(lists['room_keys']).issubset(rooms):
        raise ValueError('Unknown room key (branch/room) / غرفة غير موجودة')
    return dict(enabled=True, device_ids=sorted(devices[key][0].id for key in lists['device_keys']), **lists)


def save(m, user, scope):
    profile = m.get_user_profile(user)
    settings = m.user_profile_settings(profile)
    if scope is None:
        settings.pop('clinical_scope', None)
    else:
        settings['clinical_scope'] = scope
    profile.settings_json = json.dumps(settings, ensure_ascii=False)


def parse_form(m, form, role):
    if 'scope_present' not in form:
        return None
    supplied = form.get('scope_csrf', '')
    if not session.get('clinical_scope_csrf') or not secrets.compare_digest(session['clinical_scope_csrf'], supplied):
        abort(403)
    values = {'scope_enabled': 'true' if form.get('scope_enabled') == 'true' else 'false'}
    values.update({k: '|'.join(form.getlist(k)) for k in ('modalities', 'device_keys', 'room_keys')})
    return parse(m, values, role)


def export_values(m, user):
    scope = read(m, user)
    if scope and scope.get('invalid'):
        raise ValueError('Invalid stored clinical scope; review the user first')
    return dict(scope_enabled='true' if scope else 'false',
                **{k: '|'.join(scope[k]) if scope else '' for k in ('modalities', 'device_keys', 'room_keys')})


def predicate(m, scope, model=None):
    if model is None:
        model = m.Order
    if not scope or scope.get('invalid'):
        return false()
    clauses = []
    if scope['modalities']:
        clauses.append(func.upper(model.modality).in_(scope['modalities']))
    d = m.Device.__table__
    b = m.Branch.__table__
    if scope['device_keys']:
        pairs = [v.split('/', 1) for v in scope['device_keys'] if '/' in v]
        ids = select(d.c.id).join(b, b.c.id == d.c.branch_id).where(or_(
            *[and_(b.c.code == branch, d.c.ae_title == ae) for branch, ae in pairs]) if pairs else false())
        ids = ids.where(d.c.id.in_(scope.get('device_ids', [])))
        clauses.append(model.device_id.in_(ids))
    if scope['room_keys']:
        pairs = [v.split('/', 1) for v in scope['room_keys'] if '/' in v]
        ids = select(d.c.id).join(b, b.c.id == d.c.branch_id).where(or_(
            *[and_(b.c.code == branch, d.c.room == room) for branch, room in pairs]) if pairs else false())
        clauses.append(model.device_id.in_(ids))
    return and_(*clauses) if clauses else false()


def allowed(m, user, order):
    scope = read(m, user)
    if not scope:
        return True
    if not user or not user.active or not order or scope.get('invalid'):
        return False
    # Explicit predicate works outside requests (assignment workers) and for signed viewer identities.
    return m.db.session.query(m.Order.id).filter(m.Order.id == order.id, predicate(m, scope)).first() is not None


def register(m):
    from flask import flash, redirect, render_template, url_for
    from user_access_policy import require_manage_target

    def context(user=None):
        modalities, devices, rooms = catalog(m)
        session.setdefault('clinical_scope_csrf', secrets.token_urlsafe(32))
        return dict(scope_modalities=sorted(modalities), scope_devices=devices,
                    scope_rooms=rooms, clinical_roles=CLINICAL_ROLES,
                    scope=read(m, user) if user else None, scope_user=user,
                    scope_csrf=session['clinical_scope_csrf'])

    m.app.context_processor(lambda: {'clinical_scope_context': context, 'clinical_scope_roles': CLINICAL_ROLES})

    @m.app.route('/admin/users/<int:user_id>/clinical-scope', methods=['GET', 'POST'])
    @m.require_perm('users.manage')
    def user_clinical_scope(user_id):
        user = m.User.query.get_or_404(user_id)
        require_manage_target(user=user)
        if request.method == 'POST':
            supplied = request.form.get('scope_csrf', '')
            if not session.get('clinical_scope_csrf') or not secrets.compare_digest(session['clinical_scope_csrf'], supplied):
                abort(403)
            values = {'scope_enabled': 'true' if request.form.get('scope_enabled') == 'true' else 'false'}
            values.update({k: '|'.join(request.form.getlist(k)) for k in ('modalities', 'device_keys', 'room_keys')})
            try:
                scope = parse(m, values, user.role)
            except ValueError as exc:
                return render_template('clinical_scope.html', error=str(exc), **context(user)), 400
            save(m, user, scope)
            m.audit('USER_CLINICAL_SCOPE_SAVE', 'user', user.id, 'Restricted clinical scope' if scope else 'Clinical restriction removed')
            m.db.session.commit()
            flash('تم حفظ نطاق العمل والرؤية / Clinical work and visibility scope saved', 'success')
            return redirect(url_for('admin_users'))
        return render_template('clinical_scope.html', **context(user))

    # All requests get fresh scope; no cached permission survives an admin change.
    def guard():
        g.pop('rb_clinical_scope', None)
        user = m.current_user()
        scope = read(m, user)
        if not scope:
            return
        g.rb_clinical_scope = scope
        if not user.active:
            abort(403)
        # Generic unlinked PACS/admin operations cannot expose cases outside this clinical scope.
        if request.path.startswith('/admin') or (request.path.startswith('/pacs') and
                request.path not in ('/pacs/tracking',) and not request.path.startswith('/pacs/actions/')):
            abort(403)
        args = request.view_args or {}
        order_id = args.get('order_id')
        if order_id is None:
            order_id = request.values.get('order_id', type=int)
        if order_id is not None:
            order = m.db.session.get(m.Order, order_id)
            if not order or not allowed(m, user, order):
                abort(403)
        if args.get('accession'):
            if not m.Order.query.filter_by(accession=args['accession']).first():
                abort(403)
        for key, model in [('patient_id', m.Patient), ('attachment_id', m.Attachment),
                           ('report_id', m.Report), ('version_id', m.ReportVersion)]:
            if key in args and not m.db.session.query(model).filter(model.id == args[key]).first():
                abort(403)
        if request.path == '/attachments/upload' and order_id is None:
            abort(403)  # Unbound uploads cannot be tied to an allowed examination.

    # Run before legacy ownership guards, after the existing origin hardening.
    m.app.before_request_funcs.setdefault(None, []).insert(1, guard)

    @m.app.teardown_request
    def clear_request_scope(error=None):
        g.pop('rb_clinical_scope', None)

    @event.listens_for(Session, 'do_orm_execute')
    def restrict_queries(state):
        if not has_request_context() or current_app._get_current_object() is not m.app or not getattr(g, 'rb_clinical_scope', None) or not state.is_select or not state.is_orm_statement:
            return
        scope = g.rb_clinical_scope
        condition = predicate(m, scope)
        orders = m.Order.__table__
        # Use Core subqueries to avoid recursively re-applying loader criteria.
        order_ids = select(orders.c.id).where(predicate(m, scope, orders.c))
        patient_ids = select(orders.c.patient_id).where(predicate(m, scope, orders.c))
        reports = m.Report.__table__
        report_ids = select(reports.c.id).where(reports.c.order_id.in_(order_ids))
        options = [with_loader_criteria(m.Order, condition, include_aliases=True),
                   with_loader_criteria(m.Patient, m.Patient.id.in_(patient_ids), include_aliases=True)]
        for mapper in m.db.Model.registry.mappers:
            model = mapper.class_
            if model in (m.Order, m.Patient):
                continue
            if 'order_id' in mapper.columns:
                options.append(with_loader_criteria(model, model.order_id.in_(order_ids), include_aliases=True))
            elif 'report_id' in mapper.columns:
                options.append(with_loader_criteria(model, model.report_id.in_(report_ids), include_aliases=True))
            elif 'patient_id' in mapper.columns:
                # Patient-level information only for patients with an allowed case.
                options.append(with_loader_criteria(model, model.patient_id.in_(patient_ids), include_aliases=True))
        state.statement = state.statement.options(*options)

    m.app.extensions.setdefault('radbridge_orm_listeners', []).append((Session, 'do_orm_execute', restrict_queries))

