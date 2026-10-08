"""Technician queues and audited requests for returned cases; never delete images."""
from datetime import datetime, timedelta
from sqlalchemy import select, exists, and_, or_, func
from sqlalchemy.orm import aliased


ACTIVE_CORRECTIONS = ('NEW', 'UNDER_REVIEW', 'NEED_INFO', 'APPROVED')


def scoped_order(m, order, user=None):
    user = user or m.current_user()
    if not user or not user.active:
        m.abort(403)
    from clinical_scope import allowed
    if not allowed(m,user,order):m.abort(403)
    if user.role and ('*' in user.role.permissions() or user.role.code == 'SUPER_ADMIN'):
        return
    if not user.branch_id or user.branch_id != order.branch_id:
        m.abort(403)


def mutable_return(m, order):
    report = m.Report.query.filter_by(order_id=order.id).first()
    if (order.status or '').upper() in ('FINAL', 'CANCELLED') or (report and (
        (report.status or '').upper() in ('VERIFIED', 'FINAL', 'LOCKED')
        or report.verified_at or report.finalized_at
    )):
        m.abort(409)


def return_actor(m, order):
    user = m.current_user()
    scoped_order(m, order, user)
    global_access = m.has_perm('*')
    coordinator = user.role and user.role.code == 'CASE_COORDINATOR'
    if not (global_access or coordinator or (
        m.has_perm('reports.edit') and order.assigned_doctor_id == user.id
    )):
        m.abort(403)
    mutable_return(m, order)


def returned_technician_case(m, order):
    scoped_order(m, order)
    mutable_return(m, order)
    state = m.case_return_snapshot(order.id)
    if not state['open'] or state['owner'] != 'TECHNICIAN':
        m.abort(409)
    return state


def open_tech_return(m):
    """Same timestamp/id ordering as case_return_snapshot, evaluated in SQL."""
    returned = aliased(m.CaseWorkflowEvent)
    newer = aliased(m.CaseWorkflowEvent)
    resolved = aliased(m.CaseWorkflowEvent)
    def later(row):
        return or_(row.created_at > returned.created_at,
                   and_(row.created_at == returned.created_at, row.id > returned.id))
    newer_return = exists(select(newer.id).where(
        newer.order_id == returned.order_id, newer.event_type == 'RETURNED', later(newer)
    ).correlate(returned))
    resolution = exists(select(resolved.id).where(
        resolved.order_id == returned.order_id,
        resolved.event_type.in_(('RESOLVED', 'READY_FOR_REREVIEW')), later(resolved)
    ).correlate(returned))
    return exists(select(returned.id).where(
        returned.order_id == m.Order.id, returned.event_type == 'RETURNED',
        returned.owner_role == 'TECHNICIAN', ~newer_return, ~resolution
    ).correlate(m.Order))


def render_worklist(m):
    user = m.current_user()
    q = m.Order.query.filter(m.Order.status != 'CANCELLED')
    if not m.has_perm('*'):
        q = q.filter(m.Order.branch_id == user.branch_id) if user.branch_id else q.filter(m.db.false())
    for key, delta, op in (('date_from', 0, '__ge__'), ('date_to', 1, '__lt__')):
        value = (m.request.args.get(key) or '').strip()
        if value:
            try:
                day = datetime.strptime(value, '%Y-%m-%d') + timedelta(days=delta)
                q = q.filter(getattr(m.Order.scheduled, op)(day))
            except ValueError:
                pass
    priority = (m.request.args.get('priority') or '').strip().upper()
    if priority:
        q = q.filter(m.Order.priority == priority)
    returned = open_tech_return(m)
    status = func.upper(func.coalesce(m.Order.exam_status, 'ORDERED'))
    work_order = m.Order.status.in_(('SCHEDULED','ARRIVED','IN_PROGRESS','COMPLETED','IMAGES_RECEIVED','REPORTING','MWL_ERROR'))
    filters = {
        'waiting': and_(status.in_(('BOOKED', 'ORDERED')), ~returned, work_order),
        'in_progress': and_(status == 'IN_PROGRESS', ~returned, work_order),
        'returned': and_(returned, m.Order.status != 'FINAL'),
    }
    counts = {key: q.filter(condition).count() for key, condition in filters.items()}
    view = m.request.args.get('view', 'waiting')
    if view not in filters:
        view = 'waiting'
    search = (m.request.args.get('q') or '').strip()
    if search:
        like = '%' + search + '%'
        q = q.join(m.Patient).filter(or_(
            m.Patient.name.ilike(like), m.Patient.patient_id.ilike(like),
            m.Patient.phone.ilike(like), m.Patient.national_id.ilike(like),
            m.Order.accession.ilike(like), m.Order.procedure.ilike(like),
            m.Order.modality.ilike(like)))
    else:
        q = q.filter(filters[view])
    rows = q.order_by(m.Order.scheduled.desc(), m.Order.id.desc()).limit(300).all()
    states = {order.id: m.case_return_snapshot(order.id) for order in rows}
    return m.render_template('technician.html', orders=rows, queue_counts=counts,
        queue_view=view, queue_search=bool(search), return_states=states,
        image_urls={o.id: m.clinical_image_only_url(o) for o in rows},
        attachment_counts={o.id: m._order_attachment_count(o) for o in rows},
        saved_views=m._saved_views_for('TECHNICIAN'), saved_view_page='TECHNICIAN')



def correction_documents_ready(m, order, state):
    rule=m.quality_rule_for(order)
    history_required=bool((rule and rule.require_history) or state['reason']=='MISSING_HISTORY')
    if history_required:
        present=m.ClinicalNote.query.filter(
            m.ClinicalNote.order_id==order.id,
            m.ClinicalNote.note_type.in_(('HISTORY','GENERAL','CLINICAL_HISTORY','NURSING_HISTORY')),
            func.length(func.trim(m.ClinicalNote.text))>0).first()
        if not present:
            return False
    return not (rule and rule.require_attachments and m._order_attachment_count(order)<1)


def register(m):
    @m.app.post('/technician/<int:order_id>/returned-note')
    @m.require_perm('technician.worklist')
    def technician_returned_note(order_id):
        order = m.Order.query.get_or_404(order_id)
        returned_technician_case(m, order)
        text = (m.request.form.get('text') or '').strip()
        kind = m.request.form.get('note_type', 'TECHNICAL')
        if kind not in ('HISTORY', 'TECHNICAL') or len(text) < 5 or len(text) > 10000:
            m.abort(400)
        m.db.session.add(m.ClinicalNote(order_id=order.id, author_user_id=m.current_user().id,
            note_type=kind, visibility='CLINICAL_TEAM', text=text))
        m.audit('RETURNED_CASE_NOTE_ADDED', 'order', order.id, f'type={kind}; text={text}')
        m.db.session.commit()
        m.flash('تم حفظ بيانات الاستكمال.' if m.current_ui_language() == 'ar' else 'Correction notes saved.', 'success')
        return m.redirect(m.url_for('technician_case_workspace', order_id=order.id))

    @m.app.post('/technician/<int:order_id>/image-replacement-request')
    @m.require_perm('technician.worklist')
    def technician_image_replacement_request(order_id):
        order = m.Order.query.get_or_404(order_id)
        returned_technician_case(m, order)
        reason = (m.request.form.get('reason') or '').strip()
        if len(reason) < 5 or len(reason) > 10000:
            m.abort(400)
        if m.CorrectionRequest.query.filter_by(order_id=order.id, request_type='WRONG_IMAGES').filter(
            m.CorrectionRequest.status.in_(ACTIVE_CORRECTIONS)).first():
            m.abort(409)
        request = m.CorrectionRequest(order_id=order.id, branch_id=order.branch_id,
            request_type='WRONG_IMAGES', status='NEW', reason=reason, requested_by=m.current_user().id)
        m.db.session.add(request)
        m.db.session.flush()
        m.audit('CORRECTION_REQUEST_CREATED', 'correction_request', request.id,
            f'order={order.id}; type=WRONG_IMAGES; source=RETURNED_TECHNICIAN_CASE; reason={reason}')
        m.create_ris_notification(order, 'IMAGE_REPLACEMENT_REQUESTED', 'Image correction request',
            reason, 'WARNING', 'CASE_COORDINATOR', commit=False)
        m.db.session.commit()
        m.flash('تم إرسال طلب مراجعة الصور؛ لم يتم حذف أي صور.' if m.current_ui_language() == 'ar'
                else 'Image correction requested. No images have been deleted.', 'success')
        return m.redirect(m.url_for('technician_case_workspace', order_id=order.id))
