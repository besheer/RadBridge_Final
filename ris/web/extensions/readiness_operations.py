"""Audited readiness scheduling and branch-scoped operational views."""
import hashlib,hmac,json,secrets,time
from datetime import datetime,timedelta
from flask import abort,flash,redirect,render_template,request,session,url_for

from domain.readiness_schedule import DEFAULTS, CLOSED, validate_settings, interval, eligible
from application.services.readiness import scheduling as _scheduling
from infrastructure.adapters.readiness.schedule_repository import SqlAlchemyReadinessScheduleRepository


def settings(m):
    row=m.StudioTemplate.query.filter_by(template_type='READINESS_AUTOCHECK',status='PUBLISHED',branch_id=None).order_by(m.StudioTemplate.id.desc()).first()
    if not row:return dict(DEFAULTS),None
    try:return validate_settings(json.loads(row.layout_json)),row
    except (ValueError,TypeError):raise ValueError('Readiness scheduling configuration is invalid. Automatic checks are paused.') from None



def can_recheck(m):
    return any(m.has_perm(p) for p in ('*','assignment.manage','orders.status','nursing.worklist','reports.edit'))

def csrf():
    token=session.setdefault('readiness_csrf',secrets.token_urlsafe(32))
    if request.method=='POST' and not hmac.compare_digest(str(request.form.get('csrf_token') or ''),token):abort(400)
    return token

def _repository(m):
    return SqlAlchemyReadinessScheduleRepository(m.db.session, lambda: m.db.engine,
        m.Order, m.Report, m.CaseReadiness, m.AuditLog)


def refresh(m,order,actor=None):
    return _scheduling.refresh(repository=_repository(m),evaluate=m.evaluate_case_readiness,
        audit_actor=m.audit_as_user,order=order,actor=actor)

def run_due(m,now=None,budget_seconds=15):
    config,profile=settings(m)
    return _scheduling.run_due(repository=_repository(m),config=config,
        refresh_order=lambda order: refresh(m,order),clock=datetime.utcnow,
        monotonic=time.monotonic,now=now,budget_seconds=budget_seconds)

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
            from reception_readiness import receiving, view
            row=view(order,m.CaseReadiness.query.filter_by(order_id=order.id).first());status='BLOCKED' if receiving(order) else (row.status if row else 'NOT_CHECKED')
            counts[status]=counts.get(status,0)+1
            if state and status!=state:continue
            try:blockers=json.loads(row.details_json or '{}').get('blockers',[]) if row else []
            except ValueError:blockers=['EVIDENCE_UNAVAILABLE']
            if receiving(order):blockers=sorted(set(blockers+['PACS_RECEIVING']))
            due=(row.checked_at+timedelta(seconds=interval(config,order.modality))) if row and row.checked_at else now
            rows.append({'order':order,'readiness':row,'effective_status':status,'delay':m.case_delay_snapshot(order),'blockers':blockers,'eligible':eligible(order),'due':due,'overdue':due<=now})
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
