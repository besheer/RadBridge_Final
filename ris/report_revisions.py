"""Audited FINAL correction requests with isolated revision content and versions.

The original Report, ReportVersion and Order never become editable. The shared
report writer receives an in-memory order adapter, so its summary status writes
cannot alter the clinical order. Revision artifacts have a separate root.
"""
import hashlib
import json
import secrets
import hmac
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

from flask import request, render_template, redirect, url_for, flash,session
from sqlalchemy import UniqueConstraint
from sqlalchemy import or_

CLINICAL_ROLES={'RADIOLOGIST','DOCTOR','CONSULTANT','RADIOLOGY_CONSULTANT'}
COORDINATOR_ROLES={'SUPER_ADMIN','ADMIN','CASE_COORDINATOR','BRANCH_MANAGER'}
ACTIVE={'REQUESTED','DRAFT','VERIFIED'}

class RevisionError(ValueError):
    def __init__(self,code):self.code=code;super().__init__(code)

MESSAGES={
 'REASON':('اكتب سببًا واضحًا من 10 إلى 2000 حرف.','Enter a clear reason of 10–2000 characters.'),
 'FINAL_ONLY':('التصحيح متاح للتقارير المعتمدة فقط.','Corrections require a FINAL report.'),
 'ACTIVE':('يوجد طلب تصحيح أو تصحيح قيد العمل لهذه الحالة.','An active correction already exists for this case.'),
 'STALE':('تغير التقرير المرجعي؛ أعد مراجعة الطلب.','The reference report changed; review the request again.'),
 'DOCTOR':('اختر طبيبًا نشطًا ومؤهلًا للفحص والفرع.','Choose an active doctor qualified for the examination and branch.'),
 'STATE':('تغيرت حالة الطلب أو نُفذ الإجراء بالفعل.','The request state changed or the action was already completed.'),
 'DOCUMENT':('الوثيقة المعتمدة غير متاحة أو لا تطابق هويّة الحالة.','The FINAL document is unavailable or does not match the case identity.'),
}

def text(m,code):
    pair=MESSAGES.get(code,(code,code))
    return pair[0 if m.current_ui_language()=='ar' else 1]

def csrf(m):
    expected=session.get('report_revision_csrf','')
    supplied=request.headers.get('X-Report-Revision-CSRF') or request.form.get('revision_csrf') or ''
    if not expected or not supplied or not hmac.compare_digest(expected,str(supplied)):m.abort(403)

def digest(path):
    h=hashlib.sha256()
    with open(path,'rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
    return h.hexdigest()

def models(m):
    # Copy the current clinical summary/version column contract. This allows the
    # existing transactional writer and lifecycle core to be reused, while FK
    # and uniqueness boundaries are explicitly independent from original data.
    summary={c.name:c._copy() for c in m.Report.__table__.columns}
    summary['order_id'].unique=False
    db=m.db
    summary.update({
        '__tablename__':'report_revision',
        'original_report_id':db.Column(db.Integer,db.ForeignKey('report.id'),nullable=False,index=True),
        'original_version_id':db.Column(db.Integer,db.ForeignKey('report_version.id'),nullable=False),
        'original_sha256':db.Column(db.String(64),nullable=False),
        'base_revision_id':db.Column(db.Integer,db.ForeignKey('report_revision.id')),
        'base_sha256':db.Column(db.String(64),nullable=False),
        'revision_no':db.Column(db.Integer,nullable=False),
        'kind':db.Column(db.String(20),nullable=False),
        'reason':db.Column(db.Text,nullable=False),
        'requested_by':db.Column(db.Integer,db.ForeignKey('user.id'),nullable=False),
        'requested_at':db.Column(db.DateTime,nullable=False,default=datetime.utcnow),
        'reviewed_by':db.Column(db.Integer,db.ForeignKey('user.id')),
        'reviewed_at':db.Column(db.DateTime),
        'review_reason':db.Column(db.Text,default=''),
        'doctor_id':db.Column(db.Integer,db.ForeignKey('user.id')),
        'active_order_id':db.Column(db.Integer,db.ForeignKey('order.id'),unique=True),
        'lease_hash':db.Column(db.String(64),default=''),
        'lease_expires_at':db.Column(db.DateTime),
        'editor_key':db.Column(db.String(128),default=''),
        'working_path':db.Column(db.String(500)),
        'forcesave_nonce':db.Column(db.String(36),default=''),
        '__table_args__':(UniqueConstraint('order_id','revision_no',name='uq_report_revision_order_no'),),
    })
    Revision=type('ReportRevision',(db.Model,),summary)
    columns={c.name:c._copy() for c in m.ReportVersion.__table__.columns if c.name!='report_id'}
    columns.update({
        '__tablename__':'report_revision_version',
        'report_id':db.Column(db.Integer,db.ForeignKey('report_revision.id'),nullable=False,index=True),
        '__table_args__':(UniqueConstraint('report_id','version_no',name='uq_report_revision_version_no'),
                         UniqueConstraint('report_id','commit_id',name='uq_report_revision_commit')),
    })
    Version=type('ReportRevisionVersion',(db.Model,),columns)
    m.ReportRevision=Revision;m.ReportRevisionVersion=Version
    return Revision,Version

def in_scope(m,user,order):
    if not user or not user.active:return False
    if m.has_perm('*') or (user.branch_id and user.branch_id==order.branch_id):return True
    if user.role and user.role.code in CLINICAL_ROLES:
        profile=m.DoctorAssignmentProfile.query.filter_by(user_id=user.id).first()
        branches={s.strip() for s in (profile.branches or '').split(',') if s.strip()} if profile else set()
        return str(order.branch_id) in branches
    return False

def coordinator(m):
    user=m.current_user()
    role=user.role.code if user and user.role else ''
    if role not in COORDINATOR_ROLES or not (m.has_perm('reports.coordinate') or m.has_perm('assignment.manage')):
        m.abort(403)
    if not user.active or (not m.has_perm('*') and not user.branch_id):m.abort(403)
    return user

def doctor(m,order):
    user=m.current_user()
    role=user.role.code if user and user.role else ''
    if not in_scope(m,user,order) or role not in CLINICAL_ROLES|{'SUPER_ADMIN','ADMIN'}:
        m.abort(403)
    if not m.has_perm('reports.edit') or not m.doctor_case_access_allowed(user,order):m.abort(403)
    return user

def eligible(m,order,user):
    if not user or not user.active or not user.role or user.role.code not in CLINICAL_ROLES:return False
    permissions=user.role.permissions()
    if '*' not in permissions and not {'reports.view','reports.edit'}.issubset(permissions):return False
    # Keep existing clinical writer/verify/final role policy; approval never
    # grants report-writing rights to coordinators or bypasses clinical roles.
    try:
        for action in ('DRAFT','VERIFY','FINALIZE'):m.assert_role_allowed(user,action)
    except m.ReportEditControlError:return False
    profile=m.DoctorAssignmentProfile.query.filter_by(user_id=user.id).first()
    if not profile or not profile.available:return False
    modalities={s.strip().upper() for s in (profile.modalities or '').split(',') if s.strip()}
    branches={s.strip() for s in (profile.branches or '').split(',') if s.strip()}
    if modalities and (order.modality or '').upper() not in modalities:return False
    if branches:
        if str(order.branch_id) not in branches:return False
    elif user.branch_id!=order.branch_id:return False
    from assignment_distribution import validate_special_doctor
    try:validate_special_doctor(order,user)
    except Exception:return False
    return True

def qualified(m,order):
    users=m.User.query.join(m.Role).filter(m.User.active.is_(True),m.Role.code.in_(CLINICAL_ROLES)).order_by(m.User.full_name,m.User.username).all()
    return [u for u in users if eligible(m,order,u)]

def latest(m,revision):
    return m.ReportRevisionVersion.query.filter_by(report_id=revision.id).order_by(m.ReportRevisionVersion.version_no.desc()).first()

def final_document(m,order):
    """Select the newest approved correction, never a pending draft."""
    row=m.ReportRevision.query.filter_by(order_id=order.id,status='FINAL').order_by(m.ReportRevision.revision_no.desc()).first()
    if not row:return None
    report,original_version,_path,original_sha=original(m,order)
    version=latest(m,row)
    if (row.original_report_id!=report.id or row.original_version_id!=original_version.id
        or row.original_sha256!=original_sha or not version or not version.finalized_at):
        raise RevisionError('DOCUMENT')
    path=version.docx_path
    if (not path or not Path(path).is_file() or digest(path)!=version.sha256
        or m.validate_report_patient_file(order,path,'.docx').get('result')!='MATCH'):
        raise RevisionError('DOCUMENT')
    return {'path':path,'version_no':version.version_no,'status':'FINAL',
        'revision_id':row.id,'revision_no':row.revision_no,'kind':row.kind,'sha256':version.sha256}

def original(m,order):
    report=m.Report.query.filter_by(order_id=order.id).first()
    if not report or report.status!='FINAL':raise RevisionError('FINAL_ONLY')
    version=m.ReportVersion.query.filter_by(report_id=report.id).order_by(m.ReportVersion.version_no.desc()).first()
    if not version or not (version.finalized_at or (version.action or '').upper().endswith('FINAL')
        or (version.status or '').upper() in ('FINAL','FINALIZED')):raise RevisionError('FINAL_ONLY')
    path=(version.docx_path or version.source_path) if version else None
    if not path or Path(path).suffix.lower()!='.docx' or not Path(path).is_file():raise RevisionError('DOCUMENT')
    if m.validate_report_patient_file(order,path,'.docx').get('result')!='MATCH':raise RevisionError('DOCUMENT')
    sha=digest(path)
    if version.sha256 and version.sha256!=sha:raise RevisionError('DOCUMENT')
    return report,version,path,sha

def reference(m,order):
    report,version,path,sha=original(m,order)
    previous=m.ReportRevision.query.filter_by(order_id=order.id,status='FINAL').order_by(m.ReportRevision.revision_no.desc()).first()
    if previous:
        v=latest(m,previous)
        if not v or not v.finalized_at or not v.docx_path or not Path(v.docx_path).is_file():raise RevisionError('DOCUMENT')
        path=v.docx_path
        if digest(path)!=v.sha256:raise RevisionError('DOCUMENT')
        return report,version,path,sha,previous.id,v.sha256
    return report,version,path,sha,None,sha

def check_reference(m,order,revision):
    report,v,path,sha,base,base_sha=reference(m,order)
    if (report.id,v.id,sha,base,base_sha)!=(revision.original_report_id,revision.original_version_id,
        revision.original_sha256,revision.base_revision_id,revision.base_sha256):raise RevisionError('STALE')
    return path

def audit(m,user,action,revision,before,after):
    m.audit_as_user(user,action,'report_revision',revision.id,json.dumps({
        'order_id':revision.order_id,'original_report_id':revision.original_report_id,
        'original_version_id':revision.original_version_id,'revision_no':revision.revision_no,
        'kind':revision.kind,'reason':revision.reason,'before':before,'after':after},ensure_ascii=False,sort_keys=True))

def notify(m,order,event,title,body,role,user_id=None):
    # Internal RIS notification only. No external messaging connector is invoked.
    m.db.session.add(m.RISNotification(order_id=order.id,branch_id=order.branch_id,
        role_code=role,user_id=user_id,severity='INFO',event_type=event,title=title,body=body))

def request_revision(m,order,user,reason,kind):
    reason=(reason or '').strip();kind=(kind or '').upper()
    if not 10<=len(reason)<=2000 or kind not in ('ADDENDUM','REPLACEMENT'):raise RevisionError('REASON')
    m.Order.query.filter_by(id=order.id).with_for_update().populate_existing().one()
    report,v,path,sha,base,base_sha=reference(m,order)
    if m.ReportRevision.query.filter_by(active_order_id=order.id).first():raise RevisionError('ACTIVE')
    count=m.ReportRevision.query.filter_by(order_id=order.id).order_by(m.ReportRevision.revision_no.desc()).first()
    row=m.ReportRevision(order_id=order.id,original_report_id=report.id,original_version_id=v.id,
        original_sha256=sha,base_revision_id=base,base_sha256=base_sha,revision_no=(count.revision_no+1 if count else 1),
        status='REQUESTED',kind=kind,reason=reason,requested_by=user.id,active_order_id=order.id)
    m.db.session.add(row);m.db.session.flush()
    audit(m,user,'REPORT_REVISION_REQUESTED',row,{}, {'status':'REQUESTED'})
    notify(m,order,'REPORT_REVISION_REQUESTED','طلب تصحيح تقرير / Report correction request',reason,'CASE_COORDINATOR')
    return row

def review(m,row,user,action,reason,doctor_id=None):
    # Order then revision is the lock order used throughout this workflow.
    order=m.Order.query.filter_by(id=row.order_id).with_for_update().populate_existing().one()
    row=m.ReportRevision.query.filter_by(id=row.id).with_for_update().populate_existing().one()
    reason=(reason or '').strip()
    if row.status!='REQUESTED':raise RevisionError('STATE')
    if not 10<=len(reason)<=2000:raise RevisionError('REASON')
    if action not in ('APPROVE','REJECT'):raise RevisionError('STATE')
    before={'status':row.status,'doctor_id':row.doctor_id}
    if action=='APPROVE':
        check_reference(m,order,row)
        user_doctor=m.db.session.get(m.User,doctor_id)
        if not eligible(m,order,user_doctor):raise RevisionError('DOCTOR')
        row.doctor_id=user_doctor.id;row.status='DRAFT'
    else:row.status='REJECTED';row.active_order_id=None
    row.reviewed_by=user.id;row.reviewed_at=datetime.utcnow();row.review_reason=reason
    audit(m,user,'REPORT_REVISION_'+action,row,before,{'status':row.status,'doctor_id':row.doctor_id,'review_reason':reason})
    notify(m,order,'REPORT_REVISION_'+action,'مراجعة تصحيح التقرير / Report correction review',reason,'RADIOLOGIST',row.requested_by)
    if row.doctor_id and row.doctor_id!=row.requested_by:
        notify(m,order,'REPORT_REVISION_ASSIGNED','تصحيح تقرير مسند إليك / Assigned report correction',row.reason,'RADIOLOGIST',row.doctor_id)
    return row

def order_adapter(order,revision):
    # The shared writer updates order.status. This adapter is intentionally not
    # an ORM Order: original case status, assignment and finance remain intact.
    return SimpleNamespace(id=order.id,patient_id=order.patient_id,patient=order.patient,
        accession=order.accession,modality=order.modality,report=revision,status='REPORTING')

def register(m):
    models(m)
    def final_revision_document(order):
        try:return final_document(m,order)
        except RevisionError:m.abort(409,description='CORRECTION_DOCUMENT_UNAVAILABLE')
    m._rb_final_revision_document=final_revision_document
    @m.app.context_processor
    def report_revision_context():
        if request.path.startswith(('/case/','/report-revisions/','/coordinator/report-corrections')):
            if 'report_revision_csrf' not in session:session['report_revision_csrf']=secrets.token_urlsafe(32)
            return {'report_revision_csrf':session['report_revision_csrf']}
        return {}
    @m.app.route('/case/<int:order_id>/report-corrections',methods=['GET','POST'])
    @m.login_required
    def report_correction_case(order_id):
        order=m.Order.query.get_or_404(order_id)
        user=doctor(m,order)
        if request.method=='POST':
            csrf(m)
            try:
                request_revision(m,order,user,request.form.get('reason'),request.form.get('kind'))
                m.db.session.commit();flash('تم إرسال الطلب / Request submitted.','success')
                return redirect(url_for('report_correction_case',order_id=order.id))
            except RevisionError as exc:
                m.db.session.rollback();flash(text(m,exc.code),'warning')
                return render_template('report_correction_case.html',order=order,
                    revisions=m.ReportRevision.query.filter_by(order_id=order.id).order_by(m.ReportRevision.revision_no.desc()).all()),409
        return render_template('report_correction_case.html',order=order,
            revisions=m.ReportRevision.query.filter_by(order_id=order.id).order_by(m.ReportRevision.revision_no.desc()).all())

    @m.app.get('/coordinator/report-corrections')
    @m.login_required
    def coordinator_report_corrections():
        user=coordinator(m)
        q=m.ReportRevision.query.join(m.Order,m.ReportRevision.order_id==m.Order.id)
        if not m.has_perm('*'):q=q.filter(m.Order.branch_id==user.branch_id)
        rows=q.order_by(m.ReportRevision.requested_at.desc()).limit(300).all()
        orders={row.order_id:m.db.session.get(m.Order,row.order_id) for row in rows}
        return render_template('coordinator_report_corrections.html',revisions=rows,orders=orders,
            doctors={row.id:qualified(m,orders[row.order_id]) for row in rows if row.status=='REQUESTED'})

    @m.app.post('/coordinator/report-corrections/<int:revision_id>/review')
    @m.login_required
    def coordinator_report_correction_review(revision_id):
        csrf(m)
        user=coordinator(m);row=m.ReportRevision.query.get_or_404(revision_id)
        order=m.db.session.get(m.Order,row.order_id)
        if not in_scope(m,user,order):m.abort(403)
        try:
            review(m,row,user,request.form.get('action'),request.form.get('reason'),request.form.get('doctor_id',type=int))
            m.db.session.commit();flash('تمت مراجعة الطلب / Request reviewed.','success')
        except RevisionError as exc:
            m.db.session.rollback();flash(text(m,exc.code),'warning')
            return redirect(url_for('coordinator_report_corrections'),code=303)
        return redirect(url_for('coordinator_report_corrections'),code=303)

    @m.app.get('/doctor/report-corrections')
    @m.login_required
    def doctor_report_corrections():
        user=m.current_user()
        if not user or not user.active or not m.has_perm('reports.view') or not m.doctor_workspace_user(user):m.abort(403)
        rows=m.ReportRevision.query.filter(or_(m.ReportRevision.requested_by==user.id,m.ReportRevision.doctor_id==user.id)).order_by(m.ReportRevision.requested_at.desc()).limit(300).all()
        orders={row.order_id:m.db.session.get(m.Order,row.order_id) for row in rows}
        rows=[row for row in rows if in_scope(m,user,orders[row.order_id])]
        return render_template('doctor_report_corrections.html',revisions=rows,orders=orders)
