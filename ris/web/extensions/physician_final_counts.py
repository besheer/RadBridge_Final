"""Read-only FINAL workload counts; correction work is never a second case fee."""
from datetime import date, datetime, timedelta

from flask import request
from sqlalchemy import func, distinct


def positive_filter(m, name):
    raw = request.args.get(name, '')
    if not raw:
        return None
    try:
        value = int(raw)
    except ValueError:
        m.abort(400)
    if value <= 0:
        m.abort(400)
    return value


def date_range(m):
    today = date.today()
    try:
        start = date.fromisoformat(request.args.get('start') or str(today - timedelta(days=29)))
        end = date.fromisoformat(request.args.get('end') or str(today))
        upper = datetime.combine(end + timedelta(days=1), datetime.min.time())
    except (ValueError, OverflowError):
        m.abort(400)
    if end < start:
        m.abort(400)
    return start, end, datetime.combine(start, datetime.min.time()), upper


def snapshot(m, start_dt, end_dt, branch_id=None, doctor_id=None):
    user = m.current_user()
    if not user or not user.active:
        m.abort(403)
    if not (m.has_perm('reports.coordinate') or m.has_perm('finance.doctor_share.view')):
        m.abort(403)
    if not m.has_perm('*'):
        if not user.branch_id or (branch_id and branch_id != user.branch_id):
            m.abort(403)
        branch_id = user.branch_id

    # FINAL original assignments are preserved by the correction/reassignment
    # services. Keep the original reporting physician distinct from the
    # correction physician and from the user who signs the final approval.
    original = m.db.session.query(
        m.Order.assigned_doctor_id, m.Order.branch_id,
        func.count(distinct(m.Order.id)),
    ).join(m.Report, m.Report.order_id == m.Order.id).filter(
        m.Report.status == 'FINAL', m.Order.status == 'FINAL',
        m.Report.finalized_at >= start_dt, m.Report.finalized_at < end_dt,
    )
    revision = m.db.session.query(
        m.ReportRevision.doctor_id, m.Order.branch_id,
        func.count(distinct(m.Order.id)), func.count(distinct(m.ReportRevision.id)),
    ).join(m.Order, m.Order.id == m.ReportRevision.order_id).filter(
        m.ReportRevision.status == 'FINAL',
        m.ReportRevision.finalized_at >= start_dt,
        m.ReportRevision.finalized_at < end_dt,
    )
    if branch_id:
        original = original.filter(m.Order.branch_id == branch_id)
        revision = revision.filter(m.Order.branch_id == branch_id)
    counts = {}
    for uid, bid, count in original.group_by(m.Order.assigned_doctor_id, m.Order.branch_id):
        counts[(uid, bid)] = {'originals': count, 'correction_cases': 0, 'corrections': 0}
    for uid, bid, cases, corrections in revision.group_by(m.ReportRevision.doctor_id, m.Order.branch_id):
        row = counts.setdefault((uid, bid), {'originals': 0, 'correction_cases': 0, 'corrections': 0})
        row.update(correction_cases=cases, corrections=corrections)
    # Filter lists disclose only physicians present in the permitted workload.
    ids = {uid for uid, _ in counts if uid is not None}
    users = {u.id: u for u in m.User.query.filter(m.User.id.in_(ids)).all()}
    branches = m.Branch.query
    if branch_id:
        branches = branches.filter(m.Branch.id == branch_id)
    branches = branches.order_by(m.Branch.name).all()
    branch_names = {b.id: b.name for b in branches}
    rows = []
    for (uid, bid), values in counts.items():
        if doctor_id is not None and uid != doctor_id:
            continue
        doctor = users.get(uid)
        rows.append(dict(values, doctor_id=uid, branch_id=bid,
                         doctor_name=(doctor.full_name or doctor.username) if doctor else None,
                         branch_name=branch_names.get(bid)))
    rows.sort(key=lambda r: (r['doctor_name'] or '', r['branch_name'] or ''))
    return dict(rows=rows, doctors=sorted(users.values(), key=lambda u: u.full_name or u.username),
                branches=branches, branch_id=branch_id, doctor_id=doctor_id,
                total_originals=sum(r['originals'] for r in rows),
                total_corrections=sum(r['corrections'] for r in rows))


def register(m):
    @m.app.get('/coordinator/physician-final-counts')
    @m.login_required
    def physician_final_counts():
        start, end, lower, upper = date_range(m)
        data = snapshot(m, lower, upper, positive_filter(m, 'branch_id'), positive_filter(m, 'doctor_id'))
        return m.render_template('physician_final_counts.html', start=start, end=end, **data)
