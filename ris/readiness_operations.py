"""Audited readiness scheduling and branch-scoped operational views."""
import hashlib,hmac,json,secrets,time
from datetime import datetime,timedelta
from flask import abort,flash,redirect,render_template,request,session,url_for

DEFAULTS={'enabled':False,'interval_seconds':300,'XRAY':120,'CT':300,'MR':300,'batch_limit':10}
CLOSED={'FINAL','VERIFIED','CANCELLED'}

def validate_settings(values):
    result={'enabled':values.get('enabled') in (True,'1')}
    for key in ('interval_seconds','XRAY','CT','MR','batch_limit'):
        try:value=int(str(values.get(key,DEFAULTS[key])))
        except (ValueError,TypeError):raise ValueError('Enter whole numbers for intervals and batch size.') from None
        low,high=(1,20) if key=='batch_limit' else (60,3600)
        if not low<=value<=high:raise ValueError(f'{key}: choose a value between {low} and {high}.')
        result[key]=value
    return result

def settings(m):
    row=m.StudioTemplate.query.filter_by(template_type='READINESS_AUTOCHECK',status='PUBLISHED',branch_id=None).order_by(m.StudioTemplate.id.desc()).first()
    if not row:return dict(DEFAULTS),None
    try:return validate_settings(json.loads(row.layout_json)),row
    except (ValueError,TypeError):raise ValueError('Readiness scheduling configuration is invalid. Automatic checks are paused.') from None

def interval(config,modality):
    modality=str(modality or '').upper()
    if modality in ('DX','CR','XRAY'):modality='XRAY'
    return config.get(modality,config['interval_seconds'])

def eligible(order):
    report=getattr(order,'report',None)
    return (str(order.status or '').upper() not in CLOSED and (not report or str(report.status or '').upper() not in CLOSED)
            and (str(getattr(order,'exam_status','') or '').upper() in ('EXAM_COMPLETED','REPORTING')
                 or str(order.status or '').upper() in ('IMAGES_RECEIVED','EXAM_COMPLETED','REPORTING')))

def can_recheck(m):
    return any(m.has_perm(p) for p in ('*','assignment.manage','orders.status','nursing.worklist','reports.edit'))

def csrf():
    token=session.setdefault('readiness_csrf',secrets.token_urlsafe(32))
    if request.method=='POST' and not hmac.compare_digest(str(request.form.get('csrf_token') or ''),token):abort(400)
    return token

def refresh(m,order,actor=None):
    old=m.CaseReadiness.query.filter_by(order_id=order.id).first()
    previous=old.status if old else 'NOT_CHECKED'
    row=m.evaluate_case_readiness(order)
    details=json.loads(row.details_json or '{}')
    if details.get('pacs_error'):
        # Failed PACS evidence must never make a case ready.
        row.status='BLOCKED';row.missing_pacs=True;row.score=0
        error=str(details['pacs_error']).lower()
        reason='PACS_NOT_LINKED' if 'no authoritative pacs study link' in error else ('PACS_IDENTITY_MISMATCH' if 'mismatch' in error else 'PACS_UNAVAILABLE')
        details['blockers']=sorted(set(details.get('blockers',[])+[reason]))
        row.details_json=json.dumps(details,ensure_ascii=False)
        row.facts_sha256=hashlib.sha256(row.details_json.encode()).hexdigest()
    if actor or previous!=row.status:
        payload=json.dumps({'old_status':previous,'new_status':row.status,'automatic':actor is None,'blockers':details.get('blockers',[])})
        if actor:m.audit_as_user(actor,'CASE_READINESS_RECHECKED','order',order.id,payload)
        else:m.db.session.add(m.AuditLog(action='CASE_READINESS_AUTO_RECHECKED',entity='order',entity_id=str(order.id),username='readiness-maintenance',details=payload))
    return row

def run_due(m,now=None,budget_seconds=15):
    config,profile=settings(m)
    if not config['enabled']:return {'enabled':False,'checked':0,'errors':0}
    now=now or datetime.utcnow();start=time.monotonic();checked=errors=0
    lock_connection=None
    if m.db.engine.dialect.name=='postgresql':
        lock_connection=m.db.engine.connect()
        locked=lock_connection.execute(m.db.text('SELECT pg_try_advisory_lock(20261004, 411)')).scalar()
        if not locked:
            lock_connection.close()
            return {'enabled':True,'checked':0,'errors':0,'busy':True}
    try:
        # Oldest evidence first, including cases that have never been checked.
        candidates=(m.Order.query.outerjoin(m.CaseReadiness,m.CaseReadiness.order_id==m.Order.id)
            .filter(m.Order.status.notin_(CLOSED),~m.Order.report.has(m.Report.status.in_(CLOSED)),m.db.or_(m.Order.exam_status.in_(['EXAM_COMPLETED','REPORTING']),m.Order.status.in_(['IMAGES_RECEIVED','EXAM_COMPLETED','REPORTING'])))
            .order_by(m.CaseReadiness.checked_at.asc().nullsfirst(),m.Order.id).limit(500).all())
        ids=[o.id for o in candidates]
        for oid in ids:
            if checked+errors>=config['batch_limit'] or time.monotonic()-start>=budget_seconds:break
            order=m.Order.query.filter_by(id=oid).with_for_update(skip_locked=True).first()
            if not order:continue
            # Respect the report lock used by finalization; don't change completed cases.
            report=m.Report.query.filter_by(order_id=oid).with_for_update(skip_locked=True).first()
            if report is None and m.Report.query.filter_by(order_id=oid).first():m.db.session.rollback();continue
            if (report and str(report.status or '').upper() in CLOSED) or not eligible(order):m.db.session.rollback();continue
            row=m.CaseReadiness.query.filter_by(order_id=oid).first()
            if row and row.checked_at and (now-row.checked_at).total_seconds()<interval(config,order.modality):
                m.db.session.rollback();continue
            try:
                refresh(m,order);m.db.session.commit();checked+=1
            except Exception:
                m.db.session.rollback();errors+=1
        return {'enabled':True,'checked':checked,'errors':errors}
    finally:
        if lock_connection:
            lock_connection.execute(m.db.text('SELECT pg_advisory_unlock(20261004, 411)'));lock_connection.close()

def register(m):
    @m.require_perm('orders.view')
    def dashboard():
        from registration_policy import allowed_registration_branches
        allowed=allowed_registration_branches()
        config_error=''
        try:config,profile=settings(m)
        except ValueError as exc:config=dict(DEFAULTS);profile=None;config_error=str(exc)
        q=m.Order.query
        if allowed is not None:q=q.filter(m.Order.branch_id.in_(allowed))
        branch_id=request.args.get('branch_id',type=int)
        if branch_id:
            if allowed is not None and branch_id not in allowed:abort(403)
            q=q.filter_by(branch_id=branch_id)
        modality=(request.args.get('modality') or '').upper()[:30]
        if modality:q=q.filter(m.Order.modality.in_(['DX','CR','XRAY']) if modality=='XRAY' else m.Order.modality==modality)
        if request.args.get('active','1')=='1':q=q.filter(m.Order.status.notin_(CLOSED))
        rows=[];counts={key:0 for key in ('READY','WARNING','BLOCKED','NOT_CHECKED')}
        state=(request.args.get('status') or '').upper()
        now=datetime.utcnow()
        for order in q.order_by(m.Order.id.desc()).limit(300).all():
            row=m.CaseReadiness.query.filter_by(order_id=order.id).first();status=row.status if row else 'NOT_CHECKED'
            counts[status]=counts.get(status,0)+1
            if state and status!=state:continue
            try:blockers=json.loads(row.details_json or '{}').get('blockers',[]) if row else []
            except ValueError:blockers=['EVIDENCE_UNAVAILABLE']
            due=(row.checked_at+timedelta(seconds=interval(config,order.modality))) if row and row.checked_at else now
            rows.append({'order':order,'readiness':row,'delay':m.case_delay_snapshot(order),'blockers':blockers,'eligible':eligible(order),'due':due,'overdue':due<=now})
        bq=m.Branch.query.filter_by(active=True)
        if allowed is not None:bq=bq.filter(m.Branch.id.in_(allowed))
        return render_template('case_readiness_dashboard.html',rows=rows,counts=counts,config=config,profile=profile,config_error=config_error,
            can_manage=m.has_perm('users.manage'),can_recheck=can_recheck(m),readiness_csrf=csrf(),branches=bq.order_by(m.Branch.name).all(),
            branch_id=branch_id,modality=modality,state=state,active=request.args.get('active','1'),refresh_seconds=request.args.get('refresh',0,type=int) if request.args.get('refresh',0,type=int) in (0,30,60,120) else 0)
    m.app.view_functions['case_readiness_dashboard']=dashboard

    @m.app.post('/operations/case-readiness/settings')
    @m.require_perm('users.manage')
    def readiness_schedule_settings():
        csrf()
        try:config=validate_settings(request.form)
        except ValueError as exc:flash(str(exc),'danger');return redirect(url_for('case_readiness_dashboard'))
        if m.db.engine.dialect.name=='postgresql':m.db.session.execute(m.db.text('SELECT pg_advisory_xact_lock(20261004, 412)'))
        prior=m.StudioTemplate.query.filter_by(template_type='READINESS_AUTOCHECK',branch_id=None).order_by(m.StudioTemplate.id.desc()).first()
        row=m.StudioTemplate(template_type='READINESS_AUTOCHECK',name='Readiness automatic checks',scope='GLOBAL',version_no=(prior.version_no if prior else 0)+1,status='PUBLISHED',layout_json=json.dumps(config),created_by=m.current_user().id,published_at=datetime.utcnow())
        m.db.session.add(row);m.db.session.flush()
        m.db.session.add(m.StudioTemplateVersion(template_id=row.id,version_no=row.version_no,snapshot_json=row.layout_json,created_by=m.current_user().id))
        m.audit('READINESS_SCHEDULE_UPDATED','studio_template',row.id,json.dumps({'old':json.loads(prior.layout_json) if prior else DEFAULTS,'new':config,'version':row.version_no}))
        m.db.session.commit();flash('Automatic readiness settings saved. Assignment safety checks remain active.','success')
        return redirect(url_for('case_readiness_dashboard'))

    @m.require_perm('orders.view')
    def check(order_id):
        from registration_policy import require_registration_branch
        csrf()
        if not can_recheck(m):abort(403)
        order=m.Order.query.filter_by(id=order_id).with_for_update().first_or_404()
        require_registration_branch(order.branch_id)
        report=m.Report.query.filter_by(order_id=order_id).with_for_update().first()
        if order.status in CLOSED or (report and report.status in CLOSED):abort(409)
        row=refresh(m,order,m.current_user())
        for flag,event,title,role in [('incomplete_images','INCOMPLETE_IMAGES','Incomplete PACS images','TECHNICIAN'),('missing_history','MISSING_HISTORY','Clinical history missing','RECEPTION'),('missing_attachments','MISSING_ATTACHMENTS','Required attachment missing','RECEPTION')]:
            if getattr(row,flag) and not m.RISNotification.query.filter_by(order_id=order.id,event_type=event,status='NEW').first():
                m.db.session.add(m.RISNotification(order_id=order.id,branch_id=order.branch_id,severity='WARNING',event_type=event,title=title,body='Review current case readiness evidence.',role_code=role,status='NEW'))
        m.db.session.commit();flash('Readiness rechecked from current RIS and PACS evidence.','success')
        return redirect(url_for('case_readiness_dashboard'))
    m.app.view_functions['case_readiness_check']=check
