"""Read-only current VERIFIED/FINAL original reports and separate corrections."""
from flask import request
from sqlalchemy import case, distinct, func, literal, or_, and_
from physician_final_counts import date_range, positive_filter

PAGE_SIZE = 50


def scope(m, branch_id):
    user = m.current_user()
    if not user or not user.active or not (m.has_perm('reports.coordinate') or m.has_perm('finance.doctor_share.view')):
        m.abort(403)
    if not m.has_perm('*'):
        if not user.branch_id or (branch_id and branch_id != user.branch_id):
            m.abort(403)
        return user.branch_id
    return branch_id


def report_rows(m, lower, upper, branch_id, status):
    def query(report, doctor, kind, revision_no):
        timestamp = case((report.status == 'VERIFIED', report.verified_at), else_=report.finalized_at)
        q = m.db.session.query(
            m.Order.id.label('order_id'), m.Order.accession.label('accession'),
            m.Patient.name.label('patient_name'), m.Order.modality.label('modality'),
            m.Order.procedure.label('procedure'), m.Order.branch_id.label('branch_id'),
            doctor.label('doctor_id'), report.id.label('report_id'), report.status.label('status'),
            timestamp.label('status_at'), kind.label('kind'), revision_no.label('revision_no'),
        ).select_from(report).join(m.Order, m.Order.id == report.order_id).outerjoin(m.Patient, m.Patient.id == m.Order.patient_id)
        q = q.filter(report.status.in_(['VERIFIED', 'FINAL']), timestamp >= lower, timestamp < upper)
        if report is m.Report:
            # VERIFIED lives on a REPORTING order; FINAL requires both summaries FINAL.
            q = q.filter(or_(report.status == 'VERIFIED', m.Order.status == 'FINAL'))
        if branch_id:
            q = q.filter(m.Order.branch_id == branch_id)
        if status != 'ALL':
            q = q.filter(report.status == status)
        return q
    original = query(m.Report, m.Order.assigned_doctor_id, literal('ORIGINAL'), literal(None))
    corrections = query(m.ReportRevision, m.ReportRevision.doctor_id, m.ReportRevision.kind, m.ReportRevision.revision_no)
    return original.union_all(corrections).subquery()


def snapshot(m, lower, upper, branch_id=None, doctor_id=None, status='ALL', page=1):
    branch_id = scope(m, branch_id)
    if status not in ('ALL', 'VERIFIED', 'FINAL') or not isinstance(page, int) or page < 1:
        m.abort(400)
    source = report_rows(m, lower, upper, branch_id, status)
    ids = [row[0] for row in m.db.session.query(source.c.doctor_id).filter(source.c.doctor_id.is_not(None)).distinct()]
    doctors = m.User.query.filter(m.User.id.in_(ids)).order_by(m.User.full_name, m.User.username).all()
    branches_q = m.Branch.query
    if branch_id:
        branches_q = branches_q.filter_by(id=branch_id)
    branches = branches_q.order_by(m.Branch.name).all()
    physician_names = {u.id:u.full_name or u.username for u in doctors}
    branch_names = {b.id:b.name for b in branches}
    filters = [source.c.doctor_id == doctor_id] if doctor_id else []
    def count(kind, state):
        condition = and_(source.c.kind == 'ORIGINAL' if kind == 'ORIGINAL' else source.c.kind != 'ORIGINAL', source.c.status == state)
        return func.sum(case((condition, 1), else_=0))
    grouped = m.db.session.query(source.c.doctor_id, source.c.branch_id,
        count('ORIGINAL', 'VERIFIED').label('verified'), count('ORIGINAL', 'FINAL').label('final'),
        count('CORRECTION', 'VERIFIED').label('correction_verified'), count('CORRECTION', 'FINAL').label('correction_final'),
        func.count(distinct(case((source.c.kind != 'ORIGINAL', source.c.order_id), else_=None))).label('correction_cases'),
    ).filter(*filters).group_by(source.c.doctor_id, source.c.branch_id)
    summary=[]
    for row in grouped:
        values = dict(row._mapping)
        values.update(doctor_name=physician_names.get(row.doctor_id), branch_name=branch_names.get(row.branch_id))
        summary.append(values)
    summary.sort(key=lambda row:(row['doctor_name'] or '',row['branch_name'] or ''))
    details_q = m.db.session.query(source).filter(*filters)
    total = details_q.count()
    pages = max(1, (total + PAGE_SIZE - 1)//PAGE_SIZE)
    if page > pages:
        m.abort(400)
    details=[]
    for row in details_q.order_by(source.c.status_at.desc(), source.c.order_id.desc(), source.c.kind, source.c.report_id.desc()).offset((page-1)*PAGE_SIZE).limit(PAGE_SIZE):
        values=dict(row._mapping)
        values.update(doctor_name=physician_names.get(row.doctor_id),branch_name=branch_names.get(row.branch_id))
        details.append(values)
    return dict(summary=summary,details=details,doctors=doctors,branches=branches,
        branch_id=branch_id,doctor_id=doctor_id,status=status,page=page,pages=pages,total_details=total,
        totals={key:sum(row[key] for row in summary) for key in ('verified','final','correction_verified','correction_final')},
        can_open_cases=m.has_perm('orders.view'))


def register(m):
    @m.app.get('/coordinator/physician-reports')
    @m.login_required
    def physician_report_workload():
        start,end,lower,upper=date_range(m)
        data=snapshot(m,lower,upper,positive_filter(m,'branch_id'),positive_filter(m,'doctor_id'),
            request.args.get('status','ALL'),positive_filter(m,'page') or 1)
        return m.render_template('physician_report_workload.html',start=start,end=end,**data)
