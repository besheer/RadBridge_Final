"""Branch-scoped closing and net receipt/refund movements; no automatic grants."""
from datetime import date, datetime, timedelta
from domain.finance.closing_policy import money
from application.services.finance import closing_totals as _closing_totals
from infrastructure.adapters.finance.closing_repository import SqlAlchemyClosingRepository
import json
from flask import abort, flash, redirect, request, url_for




def payment_totals(branch_id, closing_date):
    from application.legacy_runtime import resolve_runtime
    m = resolve_runtime()
    return _closing_totals.payment_totals(repository=SqlAlchemyClosingRepository(
        m.db.session,m.Order,m.Payment,m.PaymentRefund),branch_id=branch_id,closing_date=closing_date)


def closing_page():
    from application.legacy_runtime import resolve_runtime as _rb_runtime; m = _rb_runtime()
    user = m.current_user()
    if not user or not user.active:
        abort(403)
    can_edit = m.has_perm('cashier.workstation')
    if not (can_edit or m.has_perm('financial.view')):
        abort(403)
    if request.method == 'POST' and not can_edit:
        abort(403)
    role = user.role
    global_access = bool(role and (role.code == 'SUPER_ADMIN' or '*' in role.permissions()))
    values = request.form if request.method == 'POST' else request.args
    branch_id = values.get('branch_id', type=int)
    if not global_access:
        if not user.branch_id:
            abort(403)
        branch_id = branch_id or user.branch_id
        if branch_id != user.branch_id:
            abort(403)
    try:
        raw_date = values.get('date') or ''
        closing_date = datetime.strptime(raw_date, '%Y-%m-%d').date() if raw_date else date.today()
    except ValueError:
        abort(400)
    branches = m.Branch.query.filter_by(active=True)
    if not global_access:
        branches = branches.filter_by(id=user.branch_id)
    row = None
    if request.method == 'POST' and not branch_id:
        flash('Select a branch. / اختر الفرع.', 'danger')
        return redirect(url_for('daily_closing'))
    if branch_id:
        query = m.Branch.query.filter_by(id=branch_id, active=True)
        if request.method == 'POST':
            # Also serialize first-row creation, before a closing row exists.
            query = query.with_for_update()
        query.first_or_404()
        query = m.DailyClosing.query.filter_by(branch_id=branch_id, closing_date=closing_date)
        if request.method == 'POST':
            query = query.populate_existing().with_for_update()
        row = query.order_by(m.DailyClosing.id.desc()).first()
    closed = bool(row and row.status == 'CLOSED')
    if request.method == 'POST' and closed:
        flash('This day is closed and cannot be edited. / اليوم مُقفل ولا يمكن تعديله.', 'warning')
        return redirect(url_for('daily_closing', branch_id=branch_id, date=closing_date.isoformat()))
    totals = ({'CASH': row.expected_cash, 'CARD': row.expected_card, 'OTHER': row.expected_other}
              if closed else payment_totals(branch_id, closing_date) if branch_id else
              {'CASH': 0, 'CARD': 0, 'OTHER': 0})
    if request.method == 'POST':
        action = (values.get('action') or '').upper()
        if action not in ('SAVE', 'CLOSE'):
            abort(400)
        try:
            counted = {key: money(values.get('counted_' + key.lower())) for key in totals}
        except ValueError as exc:
            flash(str(exc), 'danger')
            return redirect(url_for('daily_closing', branch_id=branch_id, date=closing_date.isoformat()))
        fields = ('status', 'expected_cash', 'expected_card', 'expected_other',
                  'counted_cash', 'counted_card', 'counted_other', 'difference', 'notes')
        before = {key: getattr(row, key) for key in fields} if row else None
        if row is None:
            row = m.DailyClosing(branch_id=branch_id, closing_date=closing_date, cashier_user_id=user.id)
            m.db.session.add(row)
        for key in totals:
            setattr(row, 'expected_' + key.lower(), totals[key])
            setattr(row, 'counted_' + key.lower(), float(counted[key]))
        row.difference = float(sum(counted.values()) - sum(money(v) for v in totals.values()))
        row.notes = (values.get('notes') or '').strip()
        row.status = 'CLOSED' if action == 'CLOSE' else 'OPEN'
        if action == 'CLOSE':
            row.closed_by = user.id
            row.closed_at = datetime.utcnow()
        m.db.session.flush()
        after = {key: getattr(row, key) for key in fields}
        m.audit('DAILY_CLOSING_' + action, 'daily_closing', row.id,
                json.dumps({'branch_id': branch_id, 'date': closing_date.isoformat(),
                            'before': before, 'after': after}, ensure_ascii=False))
        m.db.session.commit()
        flash('Closing saved. / تم حفظ التقفيل.', 'success')
        return redirect(url_for('daily_closing', branch_id=branch_id, date=closing_date.isoformat()))
    return m.render_template('daily_closing.html', branches=branches.order_by(m.Branch.name).all(),
        branch_id=branch_id, closing_date=closing_date, totals=totals, row=row,
        can_edit=can_edit and not closed, closed=closed)
