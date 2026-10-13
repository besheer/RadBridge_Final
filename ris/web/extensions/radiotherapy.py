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
from application.services.clinical import rt_support_workflow as _support
from application.services.clinical.rt_read_queries import RTReadQueries
from infrastructure.adapters.clinical.rt_read_repository import SqlAlchemyRTReadRepository
from infrastructure.adapters.clinical.rt_support_repository import SqlAlchemyRTSupportRepository
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
    def read_queries():
        return RTReadQueries(SqlAlchemyRTReadRepository(db.session,Course,Plan,Fraction,PetLink,Note,
            Consumable,m.Order,m.Patient,m.Device,m.Branch))
    def repository():return SqlAlchemyRTCourseRepository(db.session,m.Order,Course,PetLink)
    def session_repository():return SqlAlchemyRTSessionRepository(db.session,Course,Plan,Fraction,m.Device)
    def support_repository():return SqlAlchemyRTSupportRepository(db.session,Course,Plan,Fraction,m.Device,Note,Consumable)
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
    def device_scope(d):
        from clinical_scope import read
        if not read_queries().device_allowed(read(m,actor()),d):abort(403)
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
                          'INVALID_SESSION_STATUS':400,'COURSE_STATE_CONFLICT':409,
                          'INVALID_NOTE_KIND':400,'NOTE_FRACTION_MISMATCH':409,'CONSUMABLE_STATE_CONFLICT':409}
                abort(statuses.get(exc.code,500))
            except ValueError as exc:return invalid(exc)
            except IntegrityError:
                db.session.rollback();abort(409)
        return wrapped

    @m.app.get('/radiotherapy')
    @m.require_perm('rt.view')
    def rt_worklist():
        from clinical_scope import read
        u=actor()
        rows=read_queries().worklist(global_access=m.has_perm('*'),branch_id=u.branch_id,
            scope=read(m,u),search=request.args.get('q'))
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
        from clinical_scope import read
        try:data=read_queries().detail(course_id=course_id,authorize_course=course_scope,scope_provider=lambda:read(m,actor()))
        except RTWorkflowError as exc:
            if exc.code=='COURSE_NOT_FOUND':abort(404)
            raise
        return render_template('radiotherapy_course.html',**data,completion_token=secrets.token_urlsafe(24))

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
        c=_support.change_state(repository=support_repository(),policies=session_policies(),
            course_id=course_id,expected_version=request.form.get('version',''),
            target=request.form.get('status'),reason=request.form.get('reason'))
        return done(c)

    @m.app.post('/radiotherapy/<int:course_id>/notes')
    @m.require_perm('rt.notes')
    @safe
    def rt_add_note(course_id):
        c,n=_support.add_note(repository=support_repository(),policies=session_policies(),
            course_id=course_id,kind=request.form.get('kind'),body=request.form.get('body'),
            fraction_id=request.form.get('fraction_id',type=int))
        return done(c)

    @m.app.post('/radiotherapy/fractions/<int:fraction_id>/consumables')
    @m.require_perm('rt.consumables')
    @safe
    def rt_add_consumable(fraction_id):
        c,item=_support.add_consumable(repository=support_repository(),policies=session_policies(),
            fraction_id=fraction_id,name=request.form.get('name'),quantity=request.form.get('quantity'),
            unit=request.form.get('unit'))
        return done(c)
