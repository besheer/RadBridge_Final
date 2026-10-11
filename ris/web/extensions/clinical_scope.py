from domain.clinical.scope import CLINICAL_ROLES, normalize_scope, scope_selection, resolve_scope
from application.services.identity.scope_access import ClinicalScopeAccess
from infrastructure.adapters.identity.scope_repository import SqlAlchemyClinicalScopeRepository, scope_predicate
"""Explicit clinical work scope, independent of role permissions and assignment."""
import json
import secrets
from flask import abort, current_app, g, has_request_context, request, session
from sqlalchemy import and_, event, false, func, or_, select
from sqlalchemy.orm import Session, with_loader_criteria

SCOPE_COLUMNS = ('scope_enabled', 'modalities', 'device_keys', 'room_keys')


def catalog(m):
    return _scope_repository(m).catalog()


def read(m, user):
    return normalize_scope(_scope_repository(m).raw_scope(getattr(user, 'id', None)))


def parse(m, values, role):
    selection = scope_selection(values, role.code if role is not None else None)
    if selection is None:
        return None
    modalities, devices, rooms = catalog(m)
    identifiers = {key: [device.id for device in rows] for key, rows in devices.items()}
    return resolve_scope(selection, (modalities, identifiers, rooms))


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
    return scope_predicate(scope, model=m.Order if model is None else model, Device=m.Device, Branch=m.Branch)


def allowed(m, user, order):
    return ClinicalScopeAccess(_scope_repository(m)).allowed(user, order, read(m, user))


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



def _scope_repository(m):
    return SqlAlchemyClinicalScopeRepository(
        session=m.db.session, Order=m.Order, Device=m.Device, Branch=m.Branch,
        Profile=m.UserProfile, Procedure=m.Procedure, settings_reader=m.user_profile_settings,
        predicate=lambda scope: predicate(m, scope))
