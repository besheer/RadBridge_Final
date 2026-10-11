"""Manual records of externally approved RT plans and sessions; no machine control."""
import hashlib,json,secrets
from datetime import datetime,date,timezone
from decimal import Decimal,InvalidOperation
from zoneinfo import ZoneInfo
from flask import abort,request,session,redirect,url_for,render_template,flash
from sqlalchemy.exc import IntegrityError

PERMISSIONS=('rt.view','rt.course.create','rt.plan.record','rt.pet.link','rt.schedule','rt.session.start','rt.session.record','rt.notes','rt.consumables')
DEFAULT_ROLE_GRANTS={'TECHNICIAN':['rt.view','rt.session.start','rt.session.record','rt.notes','rt.consumables'],'NURSING':['rt.view','rt.notes','rt.consumables'],'CASE_COORDINATOR':['rt.view','rt.course.create','rt.pet.link','rt.schedule','rt.notes'],'BRANCH_MANAGER':['rt.view'],'RADIOTHERAPY_PHYSICIAN':['dashboard.view','patients.view','orders.view','attachments.view','rt.view','rt.course.create','rt.plan.record','rt.pet.link','rt.schedule','rt.notes']}
TABLES=('rt_course','rt_plan_version','rt_fraction','rt_pet_link','rt_note','rt_consumable')

def amount(value):
    try:d=Decimal(str(value))
    except InvalidOperation:raise ValueError('Invalid dose or quantity / قيمة غير صحيحة')
    if not d.is_finite() or d<=0 or d>=Decimal('1000000000000') or d.as_tuple().exponent < -6:raise ValueError('Use a positive decimal with at most six decimal places / قيمة موجبة بحد أقصى 6 خانات عشرية')
    return d

def text(value,minimum=1,maximum=300):
    value=str(value or '').strip()
    if not minimum<=len(value)<=maximum:raise ValueError('Required text is missing or too long / البيانات المطلوبة ناقصة أو طويلة')
    return value

def local_time(value):
    try:dt=datetime.fromisoformat(value)
    except (ValueError,TypeError):raise ValueError('Invalid scheduled date / موعد غير صحيح')
    if dt.tzinfo is None:
        zone=ZoneInfo('Africa/Cairo')
        if dt.replace(tzinfo=zone,fold=0).utcoffset()!=dt.replace(tzinfo=zone,fold=1).utcoffset():raise ValueError('Specify an unambiguous scheduled time / وقت غير واضح بسبب تغيير الساعة')
        dt=dt.replace(tzinfo=zone)
    return dt.astimezone(timezone.utc).replace(tzinfo=None)

def register(m):
    db=m.db
    m.ALL_PERMISSIONS.extend(p for p in PERMISSIONS if p not in m.ALL_PERMISSIONS)
    for code,extra in DEFAULT_ROLE_GRANTS.items():
        values=m.ROLE_PERMS.setdefault(code,[])
        values.extend(p for p in extra if p not in values)
    class RTCourse(db.Model):
        __tablename__='rt_course'
        id=db.Column(db.Integer,primary_key=True)
        primary_order_id=db.Column(db.Integer,db.ForeignKey('order.id'),nullable=False)
        patient_id=db.Column(db.Integer,db.ForeignKey('patient.id'),nullable=False)
        branch_id=db.Column(db.Integer,db.ForeignKey('branch.id'),nullable=False)
        reference=db.Column(db.String(100),unique=True,nullable=False)
        status=db.Column(db.String(20),nullable=False,default='DRAFT')
        version=db.Column(db.Integer,nullable=False,default=1)
        created_by=db.Column(db.Integer,db.ForeignKey('user.id'),nullable=False)
        created_at=db.Column(db.DateTime,nullable=False,default=datetime.utcnow)
        patient=db.relationship(m.Patient);order=db.relationship(m.Order);branch=db.relationship(m.Branch)
        __table_args__=(db.CheckConstraint("status IN ('DRAFT','ACTIVE','PAUSED','COMPLETED','CANCELLED')"),)
    class RTPlanVersion(db.Model):
        __tablename__='rt_plan_version'
        id=db.Column(db.Integer,primary_key=True)
        course_id=db.Column(db.Integer,db.ForeignKey('rt_course.id'),nullable=False)
        revision=db.Column(db.Integer,nullable=False)
        external_reference=db.Column(db.String(150),nullable=False)
        approved_by=db.Column(db.String(150),nullable=False)
        approved_on=db.Column(db.Date,nullable=False)
        attachment_id=db.Column(db.Integer,db.ForeignKey('attachment.id'))
        target=db.Column(db.Text,nullable=False)
        total_gy=db.Column(db.Numeric(18,6),nullable=False)
        fraction_gy=db.Column(db.Numeric(18,6),nullable=False)
        fractions=db.Column(db.Integer,nullable=False)
        status=db.Column(db.String(20),nullable=False,default='ACTIVE')
        reason=db.Column(db.Text,nullable=False)
        recorded_by=db.Column(db.Integer,db.ForeignKey('user.id'),nullable=False)
        recorded_at=db.Column(db.DateTime,nullable=False,default=datetime.utcnow)
        __table_args__=(db.UniqueConstraint('course_id','revision'),db.UniqueConstraint('id','course_id'),db.CheckConstraint('total_gy > 0 AND fraction_gy > 0 AND fractions > 0'),db.CheckConstraint("status IN ('ACTIVE','SUPERSEDED')"))
    class RTFraction(db.Model):
        __tablename__='rt_fraction'
        id=db.Column(db.Integer,primary_key=True)
        course_id=db.Column(db.Integer,db.ForeignKey('rt_course.id'),nullable=False)
        plan_id=db.Column(db.Integer,nullable=False)
        number=db.Column(db.Integer,nullable=False)
        attempt=db.Column(db.Integer,nullable=False,default=1)
        scheduled_at=db.Column(db.DateTime,nullable=False)
        device_id=db.Column(db.Integer,db.ForeignKey('device.id'),nullable=False)
        planned_gy=db.Column(db.Numeric(18,6),nullable=False)
        actual_gy=db.Column(db.Numeric(18,6))
        started_at=db.Column(db.DateTime);ended_at=db.Column(db.DateTime)
        status=db.Column(db.String(20),nullable=False,default='SCHEDULED')
        reason=db.Column(db.Text,default='')
        operator_id=db.Column(db.Integer,db.ForeignKey('user.id'))
        completion_key=db.Column(db.String(80));completion_hash=db.Column(db.String(64))
        delivery_reference=db.Column(db.String(150),default='')
        version=db.Column(db.Integer,nullable=False,default=1)
        device=db.relationship(m.Device)
        __table_args__=(db.UniqueConstraint('course_id','number','attempt'),db.ForeignKeyConstraint(['plan_id','course_id'],['rt_plan_version.id','rt_plan_version.course_id']),db.CheckConstraint("status IN ('SCHEDULED','STARTED','COMPLETED','NOT_GIVEN','CANCELLED')"),db.CheckConstraint('number > 0 AND planned_gy > 0 AND (actual_gy IS NULL OR actual_gy > 0)'),db.CheckConstraint("status != 'COMPLETED' OR (actual_gy IS NOT NULL AND started_at IS NOT NULL AND ended_at IS NOT NULL AND operator_id IS NOT NULL)"),db.CheckConstraint('ended_at IS NULL OR (started_at IS NOT NULL AND ended_at >= started_at)'))
    class RTPetLink(db.Model):
        __tablename__='rt_pet_link'
        id=db.Column(db.Integer,primary_key=True)
        course_id=db.Column(db.Integer,db.ForeignKey('rt_course.id'),nullable=False)
        order_id=db.Column(db.Integer,db.ForeignKey('order.id'),nullable=False)
        purpose=db.Column(db.String(30),nullable=False)
        reason=db.Column(db.Text,nullable=False)
        linked_by=db.Column(db.Integer,db.ForeignKey('user.id'),nullable=False)
        linked_at=db.Column(db.DateTime,nullable=False,default=datetime.utcnow)
        order=db.relationship(m.Order)
        __table_args__=(db.UniqueConstraint('course_id','order_id'),db.CheckConstraint("purpose IN ('BASELINE','PLANNING_REFERENCE','FOLLOW_UP','OTHER')"))
    class RTNote(db.Model):
        __tablename__='rt_note'
        id=db.Column(db.Integer,primary_key=True)
        course_id=db.Column(db.Integer,db.ForeignKey('rt_course.id'),nullable=False)
        fraction_id=db.Column(db.Integer,db.ForeignKey('rt_fraction.id'))
        kind=db.Column(db.String(20),nullable=False)
        body=db.Column(db.Text,nullable=False)
        recorded_by=db.Column(db.Integer,db.ForeignKey('user.id'),nullable=False)
        recorded_at=db.Column(db.DateTime,nullable=False,default=datetime.utcnow)
    class RTConsumable(db.Model):
        __tablename__='rt_consumable'
        id=db.Column(db.Integer,primary_key=True)
        fraction_id=db.Column(db.Integer,db.ForeignKey('rt_fraction.id'),nullable=False)
        name=db.Column(db.String(150),nullable=False)
        quantity=db.Column(db.Numeric(18,6),nullable=False)
        unit=db.Column(db.String(40),nullable=False)
        recorded_by=db.Column(db.Integer,db.ForeignKey('user.id'),nullable=False)
        recorded_at=db.Column(db.DateTime,nullable=False,default=datetime.utcnow)
        __table_args__=(db.CheckConstraint('quantity > 0'),)
    Course,Plan,Fraction,PetLink,Note,Consumable=RTCourse,RTPlanVersion,RTFraction,RTPetLink,RTNote,RTConsumable
    models=dict(Course=Course,Plan=Plan,Fraction=Fraction,PetLink=PetLink,Note=Note,Consumable=Consumable)
    m.rt_models=models

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
    def usable(c,row,completing=False):
        p=current_plan(c)
        if c.status not in (('ACTIVE','PAUSED') if completing else ('ACTIVE',)) or not p or p.id!=row.plan_id or row.number>p.fractions:abort(409)
        if str(row.device.operational_status or '').upper() not in ('ACTIVE',''):abort(409)
        return p
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
        order=m.Order.query.filter_by(accession=text(request.form.get('accession'),1,100)).first_or_404();clinical_order(order)
        if order.status=='CANCELLED':abort(409)
        c=Course(primary_order_id=order.id,patient_id=order.patient_id,branch_id=order.branch_id,reference=text(request.form.get('reference'),1,100),created_by=actor().id)
        db.session.add(c);db.session.flush();audited('COURSE_CREATED','rt_course',c,{'primary_order_id':order.id,'source':'MANUAL'})
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
        readonly_nurse();c=course(course_id,True);version(c)
        if c.status in ('COMPLETED','CANCELLED') or Fraction.query.filter_by(course_id=c.id,status='STARTED').first():abort(409)
        try:count=int(request.form.get('fractions',''));approved=date.fromisoformat(request.form.get('approved_on',''))
        except ValueError:raise ValueError('Invalid approval date or session count / تاريخ اعتماد أو عدد جلسات غير صحيح')
        if approved>datetime.now(ZoneInfo('Africa/Cairo')).date():raise ValueError('Approval date cannot be in the future / تاريخ الاعتماد لا يكون في المستقبل')
        if not 1<=count<=1000:raise ValueError('Invalid session count / عدد جلسات غير صحيح')
        last=Fraction.query.filter_by(course_id=c.id).filter(Fraction.status.in_(['STARTED','COMPLETED'])).order_by(Fraction.number.desc()).first()
        if last and count<last.number:abort(409)
        attachment_id=request.form.get('attachment_id',type=int)
        if attachment_id:
            a=m.Attachment.query.get_or_404(attachment_id)
            if a.patient_id!=c.patient_id or a.order_id!=c.primary_order_id:abort(409)
        prior=current_plan(c)
        next_revision=(db.session.query(db.func.max(Plan.revision)).filter_by(course_id=c.id).scalar() or 0)+1
        p=Plan(course_id=c.id,revision=next_revision,external_reference=text(request.form.get('external_reference'),1,150),approved_by=text(request.form.get('approved_by'),1,150),approved_on=approved,attachment_id=attachment_id,target=text(request.form.get('target'),1,1000),total_gy=amount(request.form.get('total_gy')),fraction_gy=amount(request.form.get('fraction_gy')),fractions=count,reason=text(request.form.get('reason'),5,1000),recorded_by=actor().id)
        if prior:prior.status='SUPERSEDED'
        db.session.add(p);db.session.flush();c.version+=1
        if c.status=='DRAFT':c.status='ACTIVE'
        audited('EXTERNAL_PLAN_RECORDED','rt_plan',p,{'source':'MANUAL','course_id':c.id,'prior_plan_id':prior.id if prior else None,'reference':p.external_reference,'approved_by':p.approved_by,'approved_on':p.approved_on,'total_gy':p.total_gy,'fraction_gy':p.fraction_gy,'fractions':p.fractions,'reason':p.reason})
        return done(c)

    @m.app.post('/radiotherapy/<int:course_id>/pet-links')
    @m.require_perm('rt.pet.link')
    @safe
    def rt_link_pet(course_id):
        c=course(course_id,True);version(c)
        if c.status in ('COMPLETED','CANCELLED'):abort(409)
        o=m.Order.query.filter_by(accession=text(request.form.get('accession'),1,100)).first_or_404();clinical_order(o)
        if o.patient_id!=c.patient_id or o.branch_id!=c.branch_id or str(o.modality or '').upper()!='PT' or o.status=='CANCELLED':abort(409)
        purpose=request.form.get('purpose')
        if purpose not in ('BASELINE','PLANNING_REFERENCE','FOLLOW_UP','OTHER'):abort(400)
        link=PetLink(course_id=c.id,order_id=o.id,purpose=purpose,reason=text(request.form.get('reason'),5,1000),linked_by=actor().id)
        db.session.add(link);db.session.flush();c.version+=1;audited('PET_LINKED','rt_pet_link',link,{'course_id':c.id,'order_id':o.id,'purpose':purpose,'reason':link.reason})
        return done(c)

    @m.app.post('/radiotherapy/<int:course_id>/fractions')
    @m.require_perm('rt.schedule')
    @safe
    def rt_schedule_fraction(course_id):
        c=course(course_id,True);version(c);p=current_plan(c)
        if c.status!='ACTIVE' or not p:abort(409)
        try:number=int(request.form.get('number',''))
        except ValueError:raise ValueError('Invalid session number / رقم جلسة غير صحيح')
        if not 1<=number<=p.fractions:abort(409)
        d=m.Device.query.get_or_404(request.form.get('device_id',type=int))
        if d.branch_id!=c.branch_id:abort(403)
        device_scope(d)
        if amount(request.form.get('planned_gy'))!=p.fraction_gy:abort(409)
        previous=Fraction.query.filter_by(course_id=c.id,number=number).order_by(Fraction.attempt.desc()).first()
        if previous and previous.status not in ('CANCELLED','NOT_GIVEN'):abort(409)
        retry_reason=text(request.form.get('reason'),5,1000) if previous else ''
        row=Fraction(course_id=c.id,plan_id=p.id,number=number,attempt=previous.attempt+1 if previous else 1,device_id=d.id,planned_gy=p.fraction_gy,scheduled_at=local_time(request.form.get('scheduled_at')))
        db.session.add(row);db.session.flush();c.version+=1;audited('FRACTION_SCHEDULED','rt_fraction',row,{'course_id':c.id,'plan_id':p.id,'number':number,'attempt':row.attempt,'previous_attempt_id':previous.id if previous else None,'retry_reason':retry_reason,'planned_gy':row.planned_gy,'device_id':d.id})
        return done(c)

    @m.app.post('/radiotherapy/fractions/<int:fraction_id>/reschedule')
    @m.require_perm('rt.schedule')
    @safe
    def rt_reschedule_fraction(fraction_id):
        c,row=fraction(fraction_id);version(row);p=current_plan(c)
        if c.status!='ACTIVE' or not p or row.status!='SCHEDULED' or row.number>p.fractions:abort(409)
        old={'plan_id':row.plan_id,'planned_gy':row.planned_gy,'scheduled_at':row.scheduled_at}
        reason=text(request.form.get('reason'),5,1000)
        if amount(request.form.get('planned_gy'))!=p.fraction_gy:abort(409)
        row.plan_id=p.id;row.planned_gy=p.fraction_gy;row.scheduled_at=local_time(request.form.get('scheduled_at'));row.version+=1
        audited('FRACTION_RESCHEDULED','rt_fraction',row,{'before':old,'after':{'plan_id':p.id,'planned_gy':row.planned_gy,'scheduled_at':row.scheduled_at},'reason':reason})
        return done(c)

    @m.app.post('/radiotherapy/fractions/<int:fraction_id>/start')
    @m.require_perm('rt.session.start')
    @safe
    def rt_start_fraction(fraction_id):
        readonly_nurse();c,row=fraction(fraction_id);version(row);usable(c,row)
        if row.status!='SCHEDULED':abort(409)
        row.status='STARTED';row.started_at=datetime.utcnow();row.operator_id=actor().id;row.version+=1
        audited('FRACTION_STARTED','rt_fraction',row,{'course_id':c.id,'plan_id':row.plan_id,'source':'MANUAL'})
        return done(c)

    @m.app.post('/radiotherapy/fractions/<int:fraction_id>/complete')
    @m.require_perm('rt.session.record')
    @safe
    def rt_complete_fraction(fraction_id):
        readonly_nurse();c,row=fraction(fraction_id)
        actual=amount(request.form.get('actual_gy'));reference=str(request.form.get('delivery_reference') or '').strip()
        if len(reference)>150:abort(400)
        key=text(request.form.get('idempotency_key'),16,80)
        variance_reason=str(request.form.get('dose_variance_reason') or '').strip()
        if len(variance_reason)>1000:abort(400)
        payload=hashlib.sha256(json.dumps([format(actual.normalize(),'f'),reference,variance_reason]).encode()).hexdigest()
        if row.status=='COMPLETED':
            if row.completion_key==key and row.completion_hash==payload:return redirect(url_for('rt_course_detail',course_id=c.id))
            abort(409)
        version(row);usable(c,row,True)
        if row.status!='STARTED':abort(409)
        if actual!=row.planned_gy:variance_reason=text(variance_reason,5,1000)
        row.reason=variance_reason
        row.actual_gy=actual;row.ended_at=datetime.utcnow();row.status='COMPLETED';row.operator_id=actor().id;row.delivery_reference=reference;row.completion_key=key;row.completion_hash=payload;row.version+=1
        audited('FRACTION_COMPLETED','rt_fraction',row,{'course_id':c.id,'plan_id':row.plan_id,'planned_gy':row.planned_gy,'actual_gy':actual,'dose_variance_reason':variance_reason,'source':'MANUAL','delivery_reference':reference})
        return done(c)

    @m.app.post('/radiotherapy/fractions/<int:fraction_id>/cancel')
    @m.require_perm('rt.schedule')
    @safe
    def rt_cancel_fraction(fraction_id):
        c,row=fraction(fraction_id);version(row)
        if row.status!='SCHEDULED':abort(409)
        status=request.form.get('status')
        if status not in ('CANCELLED','NOT_GIVEN'):abort(400)
        row.reason=text(request.form.get('reason'),5,1000);row.status=status;row.version+=1
        audited('FRACTION_NOT_DELIVERED','rt_fraction',row,{'status':status,'reason':row.reason})
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
