"""Previewed, scoped bulk manual assignments through the existing visit service."""
import hashlib
import json
import uuid
import secrets
import hmac
from datetime import datetime, timedelta
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from sqlalchemy import or_

LIMIT=50

MESSAGES={
 'SCOPE':('الحالة خارج نطاق الفرع','Case is outside your branch'),
 'LOCKED':('الحالة أو التقرير معتمد أو مغلق','Case or report is locked'),
 'READING':('بدأ الطبيب قراءة الحالة أو كتابة التقرير','Reading or report writing has started'),
 'RETURNED':('الحالة معادة وتحتاج استكمالًا','Case was returned for correction'),
 'CORRECTION':('يوجد طلب تصحيح مفتوح','An active correction request exists'),
 'IMAGES':('الفحص أو الصور لم يكتمل','Examination or images are incomplete'),
 'MATCH':('لم تُعتمد مطابقة هوية الصور','PACS identity match is not verified'),
 'READINESS':('جاهزية الحالة غير مستوفاة أو تحتاج فحصًا حديثًا','Readiness is blocked or needs a recent check'),
 'VISIT':('تسجيل الزيارة لم يُغلق أو توجد حجوزات لم تتحول لأوامر شغل','Visit registration or work-order conversion is incomplete'),
 'PROFILE':('ملف الطبيب أو توافره غير مستوفٍ','Doctor assignment profile or availability is missing'),
 'QUALIFICATION':('الطبيب غير مؤهل لكل فحوص الزيارة أو الفرع','Doctor does not cover all examinations or the branch'),
 'SPECIAL':('الحالة تتطلب طبيبًا مؤهلًا بسياسة الحالات الخاصة','Special-case doctor policy is not satisfied'),
 'CAPACITY':('اختيار هذه الزيارة سيتجاوز سعة الطبيب','This visit would exceed the doctor capacity'),
 'STALE':('تغيرت البيانات منذ المعاينة؛ أعد المعاينة قبل التأكيد','Data changed since preview; preview again before confirming'),
 'TOKEN':('انتهت صلاحية المعاينة أو لم تعد صالحة','Preview expired or is invalid'),
 'REPLAY':('تم تنفيذ هذا الإسناد بالفعل','This assignment batch was already completed'),
 'FAILED':('لم يُنفّذ الإسناد؛ أعد المعاينة وراجع الشروط','Nothing was assigned; preview again and review the conditions'),
}


class BulkError(Exception):
    def __init__(self,code):self.code=code;super().__init__(code)


def label(m,code):
    return MESSAGES.get(code,MESSAGES['FAILED'])[0 if m.current_ui_language()=='ar' else 1]


def actor(m):
    u=m.current_user()
    if not u or not u.active:
        m.abort(403)
    role=u.role.code if u.role else ''
    if role not in ('SUPER_ADMIN','ADMIN','CASE_COORDINATOR','BRANCH_MANAGER') or not (
        m.has_perm('assignment.manage') or m.has_perm('reports.coordinate')):
        m.abort(403)
    if not m.has_perm('*') and not u.branch_id:
        m.abort(403)
    return u


def in_scope(m,u,o):
    return bool(m.has_perm('*') or (u.branch_id and u.branch_id==o.branch_id))


def groups(m,u,ids,lock=False):
    from assignment_visit_grouping import group_members
    result=[];seen=set()
    for oid in sorted(set(ids)):
        order=m.db.session.get(m.Order,oid)
        if not order or not in_scope(m,u,order):m.abort(403)
        members=group_members(order)
        if any(not in_scope(m,u,o) for o in members):m.abort(403)
        key=tuple(sorted(o.id for o in members))
        if key in seen:continue
        if len(seen)>LIMIT or sum(len(g) for g in result)+len(members)>200:raise BulkError('FAILED')
        seen.add(key);result.append(sorted(members,key=lambda o:o.id))
    result.sort(key=lambda g:g[0].id)
    if lock:
        for group in result:
            locked=group_members(group[0],lock=True)
            if sorted(o.id for o in locked)!=[o.id for o in group]:raise BulkError('STALE')
            m.Order.query.filter(m.Order.id.in_([o.id for o in group])).order_by(m.Order.id).populate_existing().with_for_update().all()
            if any(not in_scope(m,u,o) for o in group):m.abort(403)
    return result


def member_blocker(m,o):
    report=m.Report.query.filter_by(order_id=o.id).first()
    if (o.status or '').upper() in ('FINAL','CANCELLED') or (report and (
        (report.status or '').upper() in ('VERIFIED','FINAL','LOCKED') or report.verified_at or report.finalized_at)):
        return 'LOCKED'
    edit_lease=m.ReportEditLease.query.filter_by(order_id=o.id).filter(m.ReportEditLease.expires_at>datetime.utcnow()).first()
    if edit_lease:return 'READING'
    active=m.CaseAssignment.query.filter_by(order_id=o.id,active=True).all()
    if any(a.reading_started_at for a in active) or (report and (
        (report.status or '').upper() not in ('','UNREPORTED') or report.findings or report.impression or report.docx_path or report.source_path)):
        return 'READING'
    if m.case_return_is_open(o.id):return 'RETURNED'
    if m.CorrectionRequest.query.filter_by(order_id=o.id).filter(m.CorrectionRequest.status.in_(('NEW','UNDER_REVIEW','NEED_INFO','APPROVED'))).first():return 'CORRECTION'
    if o.exam_status!='EXAM_COMPLETED' or o.pacs_status!='IMAGES_COMPLETE' or not o.pacs_study_id or not o.pacs_image_count:return 'IMAGES'
    if not m.pacs_demographic_gate(o)[0]:return 'MATCH'
    row=m.CaseReadiness.query.filter_by(order_id=o.id).first()
    if not row or not row.checked_at or (datetime.utcnow()-row.checked_at).total_seconds()>300:
        return 'READINESS'
    if row.incomplete_images or row.missing_series or row.missing_pacs:return 'IMAGES'
    if not m.returned_documents_ready(m,o,{'reason':''}):return 'READINESS'
    if not m.assignment_readiness_decision(o,refresh_stale=False)['allowed']:return 'READINESS'
    return None


def group_blocker(m,members,doctor):
    for o in members:
        blocker=member_blocker(m,o)
        if blocker:return blocker
    root=members[0]
    if root.assignment_visit_id:
        visit=m.AssignmentVisit.query.filter_by(id=root.assignment_visit_id).first()
        if not visit or visit.registration_open or m.Appointment.query.filter_by(assignment_visit_id=visit.id).filter(
            m.Appointment.order_id.is_(None),m.Appointment.status.notin_(['CANCELLED','NO_SHOW'])).first():return 'VISIT'
    profile=m.DoctorAssignmentProfile.query.filter_by(user_id=doctor.id).first()
    if not profile or not profile.available:return 'PROFILE'
    modalities={s.strip().upper() for s in (profile.modalities or '').split(',') if s.strip()}
    branches={s.strip() for s in (profile.branches or '').split(',') if s.strip()}
    if any((modalities and o.modality.upper() not in modalities) or (branches and str(o.branch_id) not in branches) for o in members):return 'QUALIFICATION'
    from assignment_distribution import validate_special_doctor
    try:
        for o in members:validate_special_doctor(o,doctor)
    except Exception:return 'SPECIAL'
    return None


def plan(m,selected,doctor):
    from assignment_distribution import active_case_count,case_capacity
    from assignment_visit_grouping import group_members
    active=active_case_count(doctor.id);capacity=case_capacity(doctor.id)
    reserved=set()
    offers=m.AssignmentOffer.query.filter_by(doctor_user_id=doctor.id,status='PENDING').filter(m.AssignmentOffer.expires_at>datetime.utcnow()).all()
    for offer in offers:
        reserved.update(o.id for o in group_members(offer.order) if o.assigned_doctor_id!=doctor.id)
    accepted=[];blocked=[];delta=0;accepted_ids=set()
    for members in selected:
        reason=group_blocker(m,members,doctor)
        extra=sum(o.assigned_doctor_id!=doctor.id for o in members)
        ids={o.id for o in members}
        if not reason and active+delta+extra+len(reserved-accepted_ids-ids)>capacity:reason='CAPACITY'
        if reason:blocked.append({'members':members,'reason':reason})
        else:
            accepted.append(members);delta+=extra;accepted_ids.update(ids)
    return {'accepted':accepted,'blocked':blocked,'active':active,'capacity':capacity,'added':delta,'reserved':len(reserved-accepted_ids)}


def fingerprint(m,selected,doctor):
    from assignment_distribution import policy_snapshot
    facts=[]
    for members in selected:
        for o in members:
            report=m.Report.query.filter_by(order_id=o.id).first()
            readiness=m.CaseReadiness.query.filter_by(order_id=o.id).first()
            assignments=m.CaseAssignment.query.filter_by(order_id=o.id,active=True).order_by(m.CaseAssignment.id).all()
            edit_lease=m.ReportEditLease.query.filter_by(order_id=o.id).first()
            match=m.PacsStudyMatch.query.filter_by(order_id=o.id).order_by(m.PacsStudyMatch.id.desc()).first()
            facts.append({'order':o.id,'branch':o.branch_id,'patient':o.patient_id,'doctor':o.assigned_doctor_id,'visit':o.assignment_visit_id,
                'status':o.status,'exam':o.exam_status,'pacs':o.pacs_status,'study':o.pacs_study_id,'images':o.pacs_image_count,
                'report':[(getattr(report,k,None)) for k in ('status','updated_at','verified_at','finalized_at')] if report else None,
                'edit_lease':(edit_lease.user_id,edit_lease.expires_at,edit_lease.renewed_at) if edit_lease else None,
                'assignments':[(a.id,a.doctor_user_id,a.reading_started_at,a.assignment_type) for a in assignments],
                'readiness':(readiness.status,readiness.facts_sha256) if readiness else None,
                'match':(match.id,match.confidence,match.match_method) if match else None})
    profile=m.DoctorAssignmentProfile.query.filter_by(user_id=doctor.id).first()
    document={'facts':facts,'doctor':(doctor.id,doctor.active,doctor.role.code),
              'profile':(profile.available,profile.modalities,profile.branches,profile.max_active_cases) if profile else None,
              'policy':policy_snapshot()}
    return hashlib.sha256(json.dumps(document,sort_keys=True,default=str).encode()).hexdigest()


def serializer(m):return URLSafeTimedSerializer(m.app.config['SECRET_KEY'],salt='coordinator-bulk-manual-v1')


def execute(m,u,claims):
    if claims.get('actor')!=u.id:raise BulkError('TOKEN')
    selected=groups(m,u,claims['ids'],lock=True)
    order_ids=sorted(o.id for group in selected for o in group)
    m.Report.query.filter(m.Report.order_id.in_(order_ids)).order_by(m.Report.order_id).populate_existing().with_for_update().all()
    m.CaseAssignment.query.filter(m.CaseAssignment.order_id.in_(order_ids),m.CaseAssignment.active.is_(True)).order_by(m.CaseAssignment.order_id,m.CaseAssignment.id).populate_existing().with_for_update().all()
    m.ReportEditLease.query.filter(m.ReportEditLease.order_id.in_(order_ids)).order_by(m.ReportEditLease.order_id).populate_existing().with_for_update().all()
    doctor=m.User.query.filter_by(id=claims['doctor']).populate_existing().with_for_update().first()
    if not doctor or not doctor.active or doctor.role.code not in ('RADIOLOGIST','DOCTOR'):raise BulkError('PROFILE')
    if m.AuditLog.query.filter_by(action='BULK_MANUAL_ASSIGNMENT',entity='assignment_batch',entity_id=claims['batch']).first():raise BulkError('REPLAY')
    if fingerprint(m,selected,doctor)!=claims['fingerprint']:raise BulkError('STALE')
    current=plan(m,selected,doctor)
    if current['blocked']:raise BulkError('STALE')
    changed=[]
    for members in current['accepted']:
        before={o.id:set(a.doctor_user_id for a in m.CaseAssignment.query.filter_by(order_id=o.id,active=True).all())|({o.assigned_doctor_id} if o.assigned_doctor_id else set()) for o in members}
        m.manual_assign_order(members[0],doctor.id,assigned_by=u.id,notes=claims['note'],assignment_type='MANUAL')
        for o in members:
            changed.append(o.id)
            m.audit('BULK_MANUAL_ASSIGNMENT_MEMBER','order',o.id,
                f'batch={claims["batch"]}; previous_doctors={sorted(before[o.id])}; doctor={doctor.id}; visit={o.assignment_visit_id}; note={claims["note"]}')
            for previous in sorted(before[o.id]-{doctor.id}):
                notification(m,o,previous,'CASE_REASSIGNED_AWAY','تم نقل الحالة لطبيب آخر / Case reassigned',claims)
            if before[o.id]!={doctor.id}:
                notification(m,o,doctor.id,'CASE_MANUALLY_ASSIGNED','تم إسناد حالة لك / Case assigned to you',claims)
    m.audit('BULK_MANUAL_ASSIGNMENT','assignment_batch',claims['batch'],json.dumps({'orders':changed,'doctor':doctor.id,'actor':u.id,'note':claims['note']},sort_keys=True))
    m.db.session.commit()
    return len(changed)


def notification(m,order,user_id,event,title,claims):
    m.db.session.add(m.RISNotification(user_id=user_id,branch_id=order.branch_id,order_id=order.id,
        event_type=event,severity='INFO',title=title,status='NEW',
        body='سبب الإسناد / Assignment reason: '+claims['note']))


def register(m):
    @m.app.route('/coordinator/manual-assignment',methods=['GET','POST'])
    @m.login_required
    def coordinator_manual_assignment():
        u=actor(m)
        csrf_token=m.session.setdefault('coordinator_assignment_csrf',secrets.token_urlsafe(32))
        if m.request.method=='POST':
            supplied=m.request.form.get('assignment_csrf','')
            if not supplied or not hmac.compare_digest(csrf_token,str(supplied)):m.abort(403)
        preview=None;token=None;error=None;status=200
        doctors=m.User.query.join(m.Role).filter(m.User.active.is_(True),m.Role.code.in_(('RADIOLOGIST','DOCTOR'))).order_by(m.User.full_name,m.User.id).all()
        if m.request.method=='POST':
            try:
                if m.request.form.get('action')=='confirm':
                    if m.request.form.get('acknowledge')!='1':raise BulkError('TOKEN')
                    claims=serializer(m).loads(m.request.form.get('preview_token',''),max_age=600)
                    count=execute(m,u,claims)
                    m.flash((f'تم إسناد {count} فحصًا يدويًا.' if m.current_ui_language()=='ar' else f'{count} examinations assigned manually.'),'success')
                    return m.redirect(m.url_for('coordinator_manual_assignment'))
                raw=m.request.form.getlist('order_ids')
                if not raw or len(raw)>LIMIT:raise BulkError('FAILED')
                ids=sorted(set(int(value) for value in raw))
                note=(m.request.form.get('note') or '').strip()
                if not 5<=len(note)<=500:raise BulkError('FAILED')
                doctor_id=int(m.request.form.get('doctor_id','0'))
                doctor=next((d for d in doctors if d.id==doctor_id),None)
                if not doctor:raise BulkError('PROFILE')
                selected=groups(m,u,ids)
                preview=plan(m,selected,doctor)
                preview['doctor']=doctor;preview['note']=note
                if preview['accepted']:
                    accepted=preview['accepted']
                    token=serializer(m).dumps({'actor':u.id,'doctor':doctor.id,'ids':[g[0].id for g in accepted],
                        'fingerprint':fingerprint(m,accepted,doctor),'note':note,'batch':str(uuid.uuid4())})
            except (BadSignature,SignatureExpired):
                m.db.session.rollback();error='TOKEN';status=409
            except BulkError as exc:
                m.db.session.rollback();error=exc.code;status=409
            except (ValueError,TypeError,KeyError):
                m.db.session.rollback();error='FAILED';status=400
            except Exception as exc:
                from werkzeug.exceptions import HTTPException
                if isinstance(exc,HTTPException):raise
                m.db.session.rollback();m.app.logger.warning('Bulk assignment rejected: %s',getattr(exc,'code',type(exc).__name__))
                error='FAILED';status=409
        query=m.Order.query.join(m.Patient).filter(m.Order.status.notin_(['FINAL','CANCELLED']))
        if not m.has_perm('*'):query=query.filter(m.Order.branch_id==u.branch_id)
        view=m.request.args.get('view','unassigned')
        if view=='unassigned':query=query.filter(m.Order.assigned_doctor_id.is_(None))
        elif view=='assigned':query=query.filter(m.Order.assigned_doctor_id.is_not(None))
        elif view!='all':view='unassigned';query=query.filter(m.Order.assigned_doctor_id.is_(None))
        search=(m.request.args.get('q') or '').strip()
        if search:
            like='%'+search+'%';query=query.filter(or_(m.Patient.name.ilike(like),m.Patient.patient_id.ilike(like),m.Order.accession.ilike(like)))
        modality=(m.request.args.get('modality') or '').strip().upper()
        if modality:query=query.filter(m.Order.modality==modality)
        page=max(1,min(m.request.args.get('page',1,type=int),10000));total=query.count()
        rows=query.order_by(m.Order.scheduled,m.Order.id).offset((page-1)*LIMIT).limit(LIMIT).all()
        return m.render_template('coordinator_manual_assignment.html',orders=rows,doctors=doctors,
            preview=preview,preview_token=token,error=label(m,error) if error else None,
            labels=lambda code:label(m,code),blocks={o.id:member_blocker(m,o) for o in rows},
            view=view,page=page,total=total,limit=LIMIT,assignment_csrf=csrf_token),status
