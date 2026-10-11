"""Per-procedure staff responsibility and completion requirements, with audited versions."""
import json,secrets
from types import SimpleNamespace
from flask import abort,g,has_request_context,request,session,redirect,url_for,render_template
from sqlalchemy import or_

ACTION='PROCEDURE_STAFF_POLICY'
SNAPSHOT='EXAM_STAFF_POLICY_SNAPSHOT'
ROLES=('TECHNICIAN','NURSING','BOTH')
KEYS=('owner','mode','require_images','require_history','require_attachments','require_consumables')

def validate(data):
    if not isinstance(data,dict) or data.get('owner') not in ROLES or data.get('mode') not in ('EXAM','TASKS'):
        raise ValueError('Invalid staff role or workflow mode')
    if any(type(data.get(k)) is not bool for k in KEYS[2:]):raise ValueError('Invalid completion requirements')
    return {k:data[k] for k in KEYS}

def policies(m):
    if has_request_context() and getattr(g,'staff_policy_request',None) is request._get_current_object() and hasattr(g,'staff_procedure_policies'):return g.staff_procedure_policies
    values={}
    for row in m.AuditLog.query.filter_by(action=ACTION,entity='procedure').order_by(m.AuditLog.id).all():
        try:
            data=json.loads(row.details);values[int(row.entity_id)]={**validate(data['after']),'version':row.id,'configured':True}
        except (ValueError,TypeError,KeyError):
            # A malformed configured policy never restores unrestricted access.
            try:values[int(row.entity_id)]={'owner':'INVALID','mode':'TASKS','require_images':True,'version':row.id,'configured':True,'invalid':True}
            except (ValueError,TypeError):pass
    if has_request_context():
        g.staff_procedure_policies=values;g.staff_policy_request=request._get_current_object()
    return values

def recommendation(m,p):
    rule=m.quality_rule_for(SimpleNamespace(modality=p.modality,procedure=p.name))
    ecg=str(p.modality or '').upper() in ('ECG','EKG') or str(p.code or '').upper() in ('ECG','EKG')
    no_images=bool(rule and not rule.require_pacs_study and not rule.min_images and not rule.required_series)
    return dict(owner='NURSING' if ecg or str(p.modality or '').upper()=='US' else 'TECHNICIAN',mode='EXAM',
                require_images=not(ecg or no_images),require_history=bool(rule and rule.require_history),
                require_attachments=bool(rule and rule.require_attachments),require_consumables=False)

def current(m,order):
    configured=policies(m).get(getattr(order,'procedure_id',None)) if getattr(order,'procedure_id',None) else None
    if configured:return dict(configured)
    # Existing unconfigured protocols keep their legacy access until explicitly configured.
    return dict(owner='BOTH',mode='EXAM',require_images=True,require_history=False,require_attachments=False,
                require_consumables=False,version=0,configured=False)

def policy(m,order):
    if not getattr(order,'procedure_id',None):return current(m,order)
    row=m.AuditLog.query.filter_by(action=SNAPSHOT,entity='order',entity_id=str(order.id)).order_by(m.AuditLog.id.desc()).first()
    if row:
        try:return {**validate(json.loads(row.details)), 'version':json.loads(row.details).get('version',0),'configured':json.loads(row.details).get('configured',False),'frozen':True}
        except (ValueError,TypeError,KeyError):return {'invalid':True,'owner':'INVALID','mode':'TASKS','require_images':True,'configured':True}
    return current(m,order)

def freeze(m,order):
    if m.AuditLog.query.filter_by(action=SNAPSHOT,entity='order',entity_id=str(order.id)).first():return
    data=current(m,order)
    if data.get('invalid'):abort(409)
    m.audit(SNAPSHOT,'order',order.id,json.dumps(data,sort_keys=True))
    m.db.session.flush()

def filter_worklist(m,q,key):
    blocked=[pid for pid,p in policies(m).items() if p.get('owner') not in (key,'BOTH')]
    snapshots={}
    for row in m.AuditLog.query.filter_by(action=SNAPSHOT,entity='order').order_by(m.AuditLog.id).all():
        try:snapshots[int(row.entity_id)]=validate(json.loads(row.details))['owner']
        except (ValueError,TypeError,KeyError):
            try:snapshots[int(row.entity_id)]='INVALID'
            except (ValueError,TypeError):pass
    allow=[oid for oid,owner in snapshots.items() if owner in (key,'BOTH')]
    deny=[oid for oid,owner in snapshots.items() if owner not in (key,'BOTH')]
    if blocked:q=q.filter(or_(m.Order.procedure_id.is_(None),~m.Order.procedure_id.in_(blocked),m.Order.id.in_(allow)))
    if deny:q=q.filter(~m.Order.id.in_(deny))
    return q


def scoped(m,order,owner=None):
    u=m.current_user()
    if not u or not u.active:abort(403)
    from clinical_scope import allowed
    if not allowed(m,u,order):abort(403)
    if not m.has_perm('*') and (not u.branch_id or order.branch_id!=u.branch_id):abort(403)
    role=owner or (u.role.code.upper() if u.role else '')
    p=policy(m,order)
    if p.get('invalid') or (role in ('TECHNICIAN','NURSING') and p['owner'] not in (role,'BOTH')):abort(403)
    return p

def requirements(m,order,p=None):
    p=p or policy(m,order);blockers=[]
    if p.get('invalid'):return {'allowed':False,'reason':'Invalid procedure policy','blockers':['INVALID_POLICY']}
    if p.get('require_history') and not m.ClinicalNote.query.filter_by(order_id=order.id).first():blockers.append('HISTORY_OR_NOTE_REQUIRED')
    if p.get('require_attachments') and not m.Attachment.query.filter_by(order_id=order.id).first():blockers.append('CASE_ATTACHMENT_REQUIRED')
    if p.get('require_consumables'):
        confirmed=m.NursingConsumableEntry.query.filter_by(order_id=order.id,confirmed=True).first()
        usage=m.OrderConsumableUsage.query.filter_by(order_id=order.id).first()
        zero=m.AuditLog.query.filter_by(action='NURSING_CONSUMABLES_CONFIRMED',entity='order',entity_id=str(order.id)).first()
        if not (confirmed or usage or zero):blockers.append('CONSUMABLES_CONFIRMATION_REQUIRED')
    return {'allowed':not blockers,'reason':'; '.join(blockers),'blockers':blockers}

def lock_policy(m,procedure_id):
    if m.db.engine.dialect.name=='postgresql':m.db.session.execute(m.db.text("SELECT pg_advisory_xact_lock(hashtext(:key))"),{'key':'STAFF_POLICY:'+str(procedure_id)})
    if has_request_context():g.pop('staff_procedure_policies',None)

def save(m,procedure,data,reason,version):
    data=validate(data)
    if not 5<=len(reason)<=300:raise ValueError('A documented reason is required')
    lock_policy(m,procedure.id)
    if has_request_context():g.pop('staff_procedure_policies',None)
    previous=policies(m).get(procedure.id)
    if int(version or 0)!=int(previous['version'] if previous else 0):abort(409)
    if previous and previous.get('invalid'):raise ValueError('Review the invalid policy audit before changing it')
    # Freeze started/finished acquisitions before changing settings; do not silently reclassify them.
    for order in m.Order.query.filter_by(procedure_id=procedure.id).filter(or_(m.Order.exam_started_at.isnot(None),m.Order.exam_status.in_(['IN_PROGRESS','EXAM_COMPLETED','REPORTING']))).with_for_update().all():freeze(m,order)
    m.audit(ACTION,'procedure',procedure.id,json.dumps({'after':data,'before':previous,'reason':reason},sort_keys=True))
    m.db.session.flush()
    if has_request_context():g.pop('staff_procedure_policies',None)

def register(m):
    def tokens():
        session.setdefault('staff_policy_csrf',secrets.token_urlsafe(32))
        return {'staff_exam_policy':lambda order:policy(m,order),'staff_exam_requirements':lambda order:requirements(m,order),'staff_policy_csrf':session['staff_policy_csrf']}
    m.app.context_processor(tokens)

    @m.app.before_request
    def role_guard():
        user=m.current_user()
        if not user or not getattr(user,'role',None) or user.role.code.upper() not in ('TECHNICIAN','NURSING'):return
        values=request.view_args or {};oid=values.get('order_id') or request.values.get('order_id',type=int)
        if not oid and values.get('attachment_id'):
            attachment=m.db.session.get(m.Attachment,values['attachment_id'])
            if attachment:oid=attachment.order_id
        if oid:
            order=m.db.session.get(m.Order,oid)
            if order:scoped(m,order)

    @m.app.route('/admin/procedures/<int:procedure_id>/staff-workflow',methods=['GET','POST'])
    @m.require_perm('procedures.view')
    def procedure_staff_workflow(procedure_id):
        if not (m.has_perm('*') or m.has_perm('workflow.override')):abort(403)
        procedure=m.Procedure.query.get_or_404(procedure_id)
        session.setdefault('staff_policy_csrf',secrets.token_urlsafe(32))
        stored=policies(m).get(procedure.id);error=''
        if request.method=='POST':
            if not secrets.compare_digest(session['staff_policy_csrf'],request.form.get('csrf_token','')):abort(403)
            data={'owner':request.form.get('owner'),'mode':request.form.get('mode'),**{k:request.form.get(k)=='1' for k in KEYS[2:]}}
            try:save(m,procedure,data,(request.form.get('reason') or '').strip(),request.form.get('version'));m.db.session.commit()
            except ValueError as exc:m.db.session.rollback();error=str(exc)
            else:return redirect(url_for('procedure_staff_workflow',procedure_id=procedure.id))
        return render_template('procedure_staff_workflow.html',procedure=procedure,policy=stored or recommendation(m,procedure),version=stored['version'] if stored else 0,csrf=session['staff_policy_csrf'],error=error),400 if error else 200

    @m.app.post('/nursing/<int:order_id>/exam-status')
    @m.require_perm('nursing.worklist')
    def nursing_exam_status(order_id):
        if not secrets.compare_digest(session.get('staff_policy_csrf','!'),request.form.get('csrf_token','')):abort(403)
        preview=m.Order.query.get_or_404(order_id)
        lock_policy(m,preview.procedure_id)
        order=m.Order.query.filter_by(id=order_id).populate_existing().with_for_update().first_or_404()
        from technician_queue import mutable_return
        mutable_return(m,order)
        p=scoped(m,order,'NURSING')
        if p['mode']!='EXAM':abort(409)
        role=m.current_user().role.code.upper()
        if role not in ('NURSING','SUPER_ADMIN','SUPERVISOR'):abort(403)
        target=(request.form.get('status') or '').upper()
        if target not in ('IN_PROGRESS','EXAM_COMPLETED'):abort(400)
        # Use the same acquisition engine, never a report-editing permission.
        decision,previous=m._apply_exam_transition(order,target,'SERVICE')
        if not decision.allowed:
            m.flash_exam_transition_blocked(order,decision,previous,target)
            return redirect(url_for('nursing_case',order_id=order.id))
        m.audit('NURSING_EXAM_STATUS','order',order.id,previous+'->'+target)
        m.db.session.commit()
        if target=='EXAM_COMPLETED' and p['require_images']:
            try:m.coordinate_post_exam_assignment(order,created_by=m.current_user().id,trigger='END_EXAM')
            except Exception:
                m.db.session.rollback()
                m.app.logger.warning('Nursing post-exam assignment requires retry order=%s',order.id)
        return redirect(url_for('nursing_worklist'))
