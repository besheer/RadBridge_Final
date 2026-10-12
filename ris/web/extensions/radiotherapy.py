from infrastructure.models.radiotherapy import RTCourse, RTPlanVersion, RTFraction, RTPetLink, RTNote, RTConsumable
"""Manual records of externally approved RT plans and sessions; no machine control."""
import hashlib,json,secrets
from datetime import datetime,date,timezone
from decimal import Decimal,InvalidOperation
from domain.clinical.rt_validation import amount, text, local_time
from domain.clinical.rt_course_policy import RTWorkflowError
from application.services.clinical import rt_course_workflow as _courses
from application.services.clinical import rt_plan_workflow as _plans
from application.services.clinical import rt_session_workflow as _sessions
from infrastructure.adapters.clinical.rt_session_repository import SqlAlchemyRTSessionRepository
from infrastructure.adapters.clinical.rt_plan_repository import SqlAlchemyRTPlanRepository
from infrastructure.adapters.clinical.rt_course_repository import SqlAlchemyRTCourseRepository
from zoneinfo import ZoneInfo
from flask import abort,request,session,redirect,url_for,render_template,flash
from sqlalchemy.exc import IntegrityError

PERMISSIONS=('rt.view','rt.course.create','rt.plan.record','rt.pet.link','rt.schedule','rt.session.start','rt.session.record','rt.notes','rt.consumables')
DEFAULT_ROLE_GRANTS={'TECHNICIAN':['rt.view','rt.session.start','rt.session.record','rt.notes','rt.consumables'],'NURSING':['rt.view','rt.notes','rt.consumables'],'CASE_COORDINATOR':['rt.view','rt.course.create','rt.pet.link','rt.schedule','rt.notes'],'BRANCH_MANAGER':['rt.view'],'RADIOTHERAPY_PHYSICIAN':['dashboard.view','patients.view','orders.view','attachments.view','rt.view','rt.course.create','rt.plan.record','rt.pet.link','rt.schedule','rt.notes']}
TABLES=('rt_course','rt_plan_version','rt_fraction','rt_pet_link','rt_note','rt_consumable')




def register(m):
    db=m.db
    m.ALL_PERMISSIONS.extend(p for p in PERMISSIONS if p not in m.ALL_PERMISSIONS)
    for code,extra in DEFAULT_ROLE_GRANTS.items():
        values=m.ROLE_PERMS.setdefault(code,[])
        values.extend(p for p in extra if p not in values)
    Course,Plan,Fraction,PetLink,Note,Consumable=RTCourse,RTPlanVersion,RTFraction,RTPetLink,RTNote,RTConsumable
    models=dict(Course=Course,Plan=Plan,Fraction=Fraction,PetLink=PetLink,Note=Note,Consumable=Consumable)
    m.rt_models=models
    def repository():return SqlAlchemyRTCourseRepository(db.session,m.Order,Course,PetLink)
    def session_repository():return SqlAlchemyRTSessionRepository(db.session,Course,Plan,Fraction,m.Device)
    def session_policies():
        return _sessions.SessionPolicies(authorize_actor=readonly_nurse,authorize_course=course_scope,
            authorize_device=device_scope,actor_id=lambda:actor().id,audit=audited,clock=datetime.utcnow)

    def actor():
        u=m.current_user()
        if not u or not u.active:abort(403)
        return u
    def clinical_order(order):
        u=actor()
        if order is None:abort(403)
        if not m.has_perm('*') and (not u.branch_id or u.branch_id!=order.branch_id):abort(403)
        from clinical_scope import allowed
        if not allowed(m,u,order):abort(403)
    def course_scope(c):
        clinical_order(c.order)
        if c.patient_id!=c.order.patient_id or c.branch_id!=c.order.branch_id:abort(409)
        return c
    def course(cid,lock=False):
        q=Course.query.filter_by(id=cid)
        if lock:q=q.populate_existing().with_for_update()
        return course_scope(q.first_or_404())
    def csrf():
        supplied=request.form.get('csrf_token','')
        if not session.get('rt_csrf') or not secrets.compare_digest(session['rt_csrf'],supplied):abort(403)
    def version(row):
        try:value=int(request.form.get('version',''))
        except ValueError:abort(400)
        if value!=row.version:abort(409)
    def audited(action,entity,row,details):m.audit('RT_'+action,entity,row.id,json.dumps(details,sort_keys=True,default=str))
    def done(c):db.session.commit();return redirect(url_for('rt_course_detail',course_id=c.id))
    def readonly_nurse():
        if actor().role and actor().role.code.upper()=='NURSING':abort(403)
    def fraction(fid):
        preview=Fraction.query.get_or_404(fid)
        c=course(preview.course_id,True)
        row=Fraction.query.filter_by(id=fid).populate_existing().with_for_update().first_or_404()
        d=row.device
        if not d or d.branch_id!=c.branch_id:abort(409)
        device_scope(d)
        return c,row
    def device_scope(d):
        from clinical_scope import predicate,read
        from sqlalchemy import literal,select
        scope=read(m,actor())
        if scope:
            cols=select(literal(d.modality).label('modality'),literal(d.id).label('device_id')).subquery().c
            if not db.session.execute(select(cols.device_id).where(predicate(m,scope,cols))).first():abort(403)
    def current_plan(c):return Plan.query.filter_by(course_id=c.id,status='ACTIVE').first()
    def context():
        session.setdefault('rt_csrf',secrets.token_urlsafe(32))
        return {'rt_csrf':session['rt_csrf'],'rt_time':lambda value:value.replace(tzinfo=timezone.utc).astimezone(ZoneInfo('Africa/Cairo')).strftime('%Y-%m-%d %H:%M') if value else '—'}
    m.app.context_processor(context)

    @m.app.before_request
    def errors_and_token():
        if request.endpoint and request.endpoint.startswith('rt_'):
            if request.method=='POST':csrf()
    def invalid(exc):
        db.session.rollback();flash(str(exc),'danger')
        if request.view_args and request.view_args.get('course_id'):return redirect(url_for('rt_course_detail',course_id=request.view_args['course_id']))
        return redirect(url_for('rt_worklist'))
    def safe(fn):
        from functools import wraps
        @wraps(fn)
        def wrapped(*args,**kwargs):
            try:return fn(*args,**kwargs)
            except RTWorkflowError as exc:
                statuses={'INVALID_COURSE_VERSION':400,'INVALID_PET_PURPOSE':400,
                          'ORDER_NOT_FOUND':404,'COURSE_NOT_FOUND':404,'ATTACHMENT_NOT_FOUND':404,
                          'STALE_COURSE_VERSION':409,'PET_LINK_IDENTITY_MISMATCH':409,
                          'ORDER_CANCELLED':409,'COURSE_TERMINAL':409,
                          'PLAN_EDIT_BLOCKED':409,'PLAN_ATTACHMENT_MISMATCH':409,
                          'FRACTION_NOT_FOUND':404,'DEVICE_NOT_FOUND':404,'DEVICE_BRANCH_DENIED':403,
                          'FRACTION_DEVICE_MISMATCH':409,'SESSION_STATE_CONFLICT':409,
                          'INVALID_COMPLETION_INPUT':400,'COMPLETION_REPLAY_CONFLICT':409,
                          'INVALID_SESSION_STATUS':400}
                abort(statuses.get(exc.code,500))
            except ValueError as exc:return invalid(exc)
            except IntegrityError:
                db.session.rollback();abort(409)
        return wrapped

    @m.app.get('/radiotherapy')
    @m.require_perm('rt.view')
    def rt_worklist():
        q=Course.query
        if not m.has_perm('*'):q=q.filter(Course.branch_id==actor().branch_id) if actor().branch_id else q.filter(db.false())
        from clinical_scope import read,predicate
        scope=read(m,actor())
        if scope:q=q.filter(Course.primary_order_id.in_(db.session.query(m.Order.id).filter(predicate(m,scope))))
        search=(request.args.get('q') or '').strip()
        if search:q=q.join(m.Patient,Course.patient_id==m.Patient.id).filter(db.or_(Course.reference.ilike('%'+search+'%'),m.Patient.patient_id==search))
        rows=q.order_by(Course.created_at.desc()).limit(100).all()
        return render_template('radiotherapy_list.html',courses=rows)

    @m.app.post('/radiotherapy/courses')
    @m.require_perm('rt.course.create')
    @safe
    def rt_create_course():
        c=_courses.create_course(repository=repository(),authorize_order=clinical_order,
            actor_id=lambda:actor().id,audit=audited,accession=request.form.get('accession'),
            reference=request.form.get('reference'))
        return done(c)

    @m.app.get('/radiotherapy/<int:course_id>')
    @m.require_perm('rt.view')
    def rt_course_detail(course_id):
        c=course(course_id);p=current_plan(c)
        devices=m.Device.query.filter_by(branch_id=c.branch_id).order_by(m.Device.name).all()
        from clinical_scope import read,predicate
        scope=read(m,actor())
        if scope:
            from sqlalchemy import literal,select
            devices=[d for d in devices if db.session.execute(select(literal(d.id)).where(predicate(m,scope,select(literal(d.modality).label('modality'),literal(d.id).label('device_id')).subquery().c))).first()]
        return render_template('radiotherapy_course.html',course=c,plan=p,plans=Plan.query.filter_by(course_id=c.id).order_by(Plan.revision.desc()).all(),fractions=Fraction.query.filter_by(course_id=c.id).filter(Fraction.device_id.in_([d.id for d in devices])).order_by(Fraction.number).all(),pet_links=PetLink.query.filter_by(course_id=c.id).all(),notes=Note.query.filter_by(course_id=c.id).filter(db.or_(Note.fraction_id.is_(None),Note.fraction_id.in_(db.session.query(Fraction.id).filter(Fraction.device_id.in_([d.id for d in devices]))))).order_by(Note.recorded_at.desc()).all(),consumables=Consumable.query.join(Fraction).filter(Fraction.course_id==c.id,Fraction.device_id.in_([d.id for d in devices])).all(),devices=devices,completion_token=secrets.token_urlsafe(24))

    @m.app.post('/radiotherapy/<int:course_id>/plans')
    @m.require_perm('rt.plan.record')
    @safe
    def rt_record_plan(course_id):
        fields=('fractions','approved_on','external_reference','approved_by','target','total_gy','fraction_gy','reason')
        c,p=_plans.record_plan(repository=SqlAlchemyRTPlanRepository(db.session,Course,Plan,Fraction,m.Attachment),
            authorize_actor=readonly_nurse,authorize_course=course_scope,actor_id=lambda:actor().id,
            audit=audited,today=lambda:datetime.now(ZoneInfo('Africa/Cairo')).date(),course_id=course_id,
            expected_version=request.form.get('version',''),values={key:request.form.get(key,'') for key in fields},
            attachment_id=request.form.get('attachment_id',type=int))
        return done(c)

    @m.app.post('/radiotherapy/<int:course_id>/pet-links')
    @m.require_perm('rt.pet.link')
    @safe
    def rt_link_pet(course_id):
        c,link=_courses.link_pet(repository=repository(),authorize_course=course_scope,
            authorize_order=clinical_order,actor_id=lambda:actor().id,audit=audited,
            course_id=course_id,expected_version=request.form.get('version',''),
            accession=request.form.get('accession'),purpose=request.form.get('purpose'),
            reason=request.form.get('reason'))
        return done(c)

    @m.app.post('/radiotherapy/<int:course_id>/fractions')
    @m.require_perm('rt.schedule')
    @safe
    def rt_schedule_fraction(course_id):
        fields=('number','planned_gy','reason','scheduled_at')
        c,row=_sessions.schedule(repository=session_repository(),policies=session_policies(),
            course_id=course_id,expected_version=request.form.get('version',''),
            values={key:request.form.get(key,'') for key in fields},device_id=request.form.get('device_id',type=int))
        return done(c)

    @m.app.post('/radiotherapy/fractions/<int:fraction_id>/reschedule')
    @m.require_perm('rt.schedule')
    @safe
    def rt_reschedule_fraction(fraction_id):
        fields=('planned_gy','reason','scheduled_at')
        c,row=_sessions.reschedule(repository=session_repository(),policies=session_policies(),
            fraction_id=fraction_id,expected_version=request.form.get('version',''),
            values={key:request.form.get(key,'') for key in fields})
        return done(c)

    @m.app.post('/radiotherapy/fractions/<int:fraction_id>/start')
    @m.require_perm('rt.session.start')
    @safe
    def rt_start_fraction(fraction_id):
        c,row=_sessions.start(repository=session_repository(),policies=session_policies(),
            fraction_id=fraction_id,expected_version=request.form.get('version',''))
        return done(c)

    @m.app.post('/radiotherapy/fractions/<int:fraction_id>/complete')
    @m.require_perm('rt.session.record')
    @safe
    def rt_complete_fraction(fraction_id):
        fields=('actual_gy','delivery_reference','idempotency_key','dose_variance_reason')
        c,row,accepted=_sessions.complete(repository=session_repository(),policies=session_policies(),
            fraction_id=fraction_id,expected_version=request.form.get('version',''),
            values={key:request.form.get(key,'') for key in fields})
        if not accepted:return redirect(url_for('rt_course_detail',course_id=c.id))
        return done(c)

    @m.app.post('/radiotherapy/fractions/<int:fraction_id>/cancel')
    @m.require_perm('rt.schedule')
    @safe
    def rt_cancel_fraction(fraction_id):
        c,row=_sessions.cancel(repository=session_repository(),policies=session_policies(),
            fraction_id=fraction_id,expected_version=request.form.get('version',''),
            status=request.form.get('status'),reason=request.form.get('reason'))
        return done(c)

    @m.app.post('/radiotherapy/<int:course_id>/state')
    @m.require_perm('rt.course.create')
    @safe
    def rt_course_state(course_id):
        c=course(course_id,True);version(c);target=request.form.get('status');reason=text(request.form.get('reason'),5,1000)
        allowed={'DRAFT':{'CANCELLED'},'ACTIVE':{'PAUSED','COMPLETED','CANCELLED'},'PAUSED':{'ACTIVE','CANCELLED'}}
        if target not in allowed.get(c.status,set()):abort(409)
        if target in ('CANCELLED','COMPLETED') and Fraction.query.filter_by(course_id=c.id,status='STARTED').first():abort(409)
        if target=='COMPLETED':
            p=current_plan(c)
            complete=Fraction.query.filter_by(course_id=c.id,status='COMPLETED').count()
            if not p or complete!=p.fractions:abort(409)
        previous=c.status;c.status=target;c.version+=1;audited('COURSE_STATE','rt_course',c,{'from':previous,'to':target,'reason':reason})
        return done(c)

    @m.app.post('/radiotherapy/<int:course_id>/notes')
    @m.require_perm('rt.notes')
    @safe
    def rt_add_note(course_id):
        c=course(course_id,True)
        if c.status in ('COMPLETED','CANCELLED'):abort(409)
        kind=request.form.get('kind')
        if kind not in ('PREPARATION','NURSING','TECHNICAL','CLINICAL'):abort(400)
        fid=request.form.get('fraction_id',type=int)
        if fid:
            row=Fraction.query.get_or_404(fid)
            if row.course_id!=c.id:abort(409)
            fraction(fid)
        n=Note(course_id=c.id,fraction_id=fid,kind=kind,body=text(request.form.get('body'),1,10000),recorded_by=actor().id)
        db.session.add(n);db.session.flush();audited('NOTE_ADDED','rt_note',n,{'course_id':c.id,'fraction_id':fid,'kind':kind})
        return done(c)

    @m.app.post('/radiotherapy/fractions/<int:fraction_id>/consumables')
    @m.require_perm('rt.consumables')
    @safe
    def rt_add_consumable(fraction_id):
        c,row=fraction(fraction_id)
        if c.status in ('COMPLETED','CANCELLED') or row.status in ('CANCELLED','NOT_GIVEN'):abort(409)
        item=Consumable(fraction_id=row.id,name=text(request.form.get('name'),1,150),quantity=amount(request.form.get('quantity')),unit=text(request.form.get('unit'),1,40),recorded_by=actor().id)
        db.session.add(item);db.session.flush();audited('CONSUMABLE_RECORDED','rt_consumable',item,{'course_id':c.id,'fraction_id':row.id,'name':item.name,'quantity':item.quantity,'unit':item.unit,'stock_posted':False})
        return done(c)
