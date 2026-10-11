"""Approved FINAL replacement allocations; cash disbursements remain immutable.

A finance operator previews and confirms a payable adjustment, not a cash
recovery/payment. Legacy entitlements and payout references require explicit
verification because the old application has no immutable case-payable ledger.
"""
import hashlib
import hmac
import json
import secrets
from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from types import SimpleNamespace

from flask import request, session
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from sqlalchemy import event

CENT = Decimal('0.01')
LIMIT = Decimal('9999999999.99')


class SettlementError(ValueError):
    pass


MESSAGES = {
    'FINAL_REPLACEMENT_ONLY': ('التسوية متاحة للاستبدال المعتمد FINAL فقط.', 'Only a FINAL REPLACEMENT can be settled.'),
    'MISSING_RULE': ('لا توجد قاعدة مستحقات مطابقة؛ أضف قاعدة صريحة أولًا.', 'No matching share rule; configure an explicit rule first.'),
    'AMBIGUOUS_RULE': ('توجد قواعد متساوية الأولوية؛ راجعها قبل التسوية.', 'Equally specific share rules exist; resolve them before settlement.'),
    'INVALID_MONEY': ('قيمة مالية غير صالحة.', 'Invalid monetary value.'),
    'INVALID_RULE': ('قاعدة المستحقات غير صالحة.', 'Invalid share rule.'),
    'ORIGINAL_DOCTOR_UNKNOWN': ('الطبيب صاحب المستحق الأصلي غير محدد؛ راجع الطبيب المنفذ المسجل في الحالة قبل التسوية.', 'Original entitlement physician is unknown; verify the case’s registered performing physician first.'),
    'PREVIOUS_REPLACEMENT_UNSETTLED': ('سوِّ الاستبدال السابق أولًا.', 'Settle the earlier replacement first.'),
    'NO_PHYSICIAN_CHANGE': ('الطبيب لم يتغير؛ لا يلزم نقل المستحق.', 'The physician is unchanged; no entitlement transfer is needed.'),
    'REASON_REQUIRED': ('اكتب سببًا واضحًا من 10 إلى 2000 حرف.', 'Enter a reason of 10–2000 characters.'),
    'PAYMENTS_NOT_VERIFIED': ('أكد مراجعة كل قيود الصرف، بما فيها الصرف غير المرتبط برقم الحالة.', 'Verify all payout records, including entries without case references.'),
    'STALE_PREVIEW': ('تغيرت البيانات أو انتهت المعاينة؛ راجعها مجددًا.', 'Data changed or preview expired; preview again.'),
    'CSRF': ('طلب غير صالح؛ أعد فتح الصفحة.', 'Invalid request; reopen the page.'),
}


def money(value):
    try:
        result = Decimal(str(value))
        if not result.is_finite() or result < 0 or result > LIMIT:
            raise ValueError()
        return result.quantize(CENT, rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError, TypeError):
        raise SettlementError('INVALID_MONEY')


def models(m):
    from infrastructure.models.settlement import ReplacementSettlement
    if not getattr(ReplacementSettlement, '_radbridge_immutable_guards', False):
        def immutable(*args):
            raise SettlementError('SETTLEMENT_HISTORY_IMMUTABLE')
        event.listen(ReplacementSettlement, 'before_update', immutable)
        event.listen(ReplacementSettlement, 'before_delete', immutable)
        ReplacementSettlement._radbridge_immutable_guards = True
    m.ReplacementSettlement = ReplacementSettlement


def latest(m, order_id):
    return m.ReplacementSettlement.query.filter_by(order_id=order_id).order_by(m.ReplacementSettlement.revision_no.desc()).first()


def effective_share(m, order):
    row = latest(m, order.id)
    if not row:
        return None
    doctor = m.db.session.get(m.User, row.new_doctor_id)
    frozen = json.loads(row.snapshot_json)['new_rule']
    rule = SimpleNamespace(**frozen)
    return float(row.new_amount), rule, doctor


def actor(m, order=None, manage=False):
    u = m.current_user()
    permission = 'finance.doctor_share.manage' if manage else 'finance.doctor_share.view'
    if not u or not u.active or not m.has_perm(permission):
        m.abort(403)
    if not m.has_perm('*'):
        if not u.branch_id or (order is not None and u.branch_id != order.branch_id):
            m.abort(403)
    return u


def rule_share(m, order, doctor_id):
    matches = []
    for r in m.PerformingDoctorShareRule.query.filter_by(doctor_user_id=doctor_id, active=True):
        if r.branch_id and r.branch_id != order.branch_id: continue
        if r.modality and r.modality != order.modality: continue
        if r.procedure_id and r.procedure_id != order.procedure_id: continue
        if r.contract_id and r.contract_id != order.contract_id: continue
        score = (8 if r.procedure_id else 0) + (4 if r.contract_id else 0) + (2 if r.modality else 0) + (1 if r.branch_id else 0)
        matches.append((score, r))
    if not matches: raise SettlementError('MISSING_RULE')
    best = max(score for score, _ in matches)
    winners = [r for score, r in matches if score == best]
    if len(winners) != 1: raise SettlementError('AMBIGUOUS_RULE')
    rule = winners[0]
    if rule.basis not in ('GROSS', 'CONTRACT', 'NET_AFTER_DISCOUNT') or rule.rule_type not in ('FIXED', 'PERCENT'):
        raise SettlementError('INVALID_RULE')
    try:
        value = Decimal(str(rule.value))
        if not value.is_finite() or value < 0 or value > LIMIT: raise ValueError()
    except (InvalidOperation, ValueError): raise SettlementError('INVALID_RULE')
    if rule.rule_type == 'PERCENT' and value > 100: raise SettlementError('INVALID_RULE')
    gross, contract = money(order.gross_price or 0), money(order.contract_price or order.gross_price or 0)
    patient_base = money(order.patient_share or order.contract_price or order.gross_price or 0)
    discounts = sum((money(d.amount) for d in m.approved_order_discounts(order)), Decimal('0'))
    net = max(Decimal('0'), patient_base - discounts)
    base = {'GROSS': gross, 'CONTRACT': contract, 'NET_AFTER_DISCOUNT': net}[rule.basis]
    amount = money(base * value / 100 if rule.rule_type == 'PERCENT' else value)
    frozen = {name: getattr(rule, name) for name in ('id', 'doctor_user_id', 'branch_id', 'modality', 'procedure_id', 'contract_id', 'rule_type', 'basis')}
    frozen.update(value=str(value), base=str(base), amount=str(amount))
    return amount, frozen


def plan(m, revision, original_amount, reason, payments_verified, paid_amount, payment_note=''):
    order = m.db.session.get(m.Order, revision.order_id)
    u = actor(m, order, manage=True)
    reason = str(reason or '').strip()
    if not 10 <= len(reason) <= 2000: raise SettlementError('REASON_REQUIRED')
    if not payments_verified: raise SettlementError('PAYMENTS_NOT_VERIFIED')
    if revision.kind != 'REPLACEMENT' or revision.status != 'FINAL' or not revision.finalized_at:
        raise SettlementError('FINAL_REPLACEMENT_ONLY')
    if not order or not order.branch_id: raise SettlementError('FINAL_REPLACEMENT_ONLY')
    current = latest(m, order.id)
    if current and current.revision_no >= revision.revision_no: raise SettlementError('STALE_PREVIEW')
    original = m.performing_doctor_for_order(order)
    # No invented attribution when the legacy financial owner is absent.
    owner = current.new_doctor_id if current else (original.id if original else None)
    if owner is None: raise SettlementError('ORIGINAL_DOCTOR_UNKNOWN')
    first_unsettled = m.ReportRevision.query.filter_by(order_id=order.id, kind='REPLACEMENT', status='FINAL').filter(
        m.ReportRevision.revision_no < revision.revision_no,
        m.ReportRevision.revision_no > (current.revision_no if current else 0),
        m.ReportRevision.doctor_id != owner,
    ).first()
    if first_unsettled: raise SettlementError('PREVIOUS_REPLACEMENT_UNSETTLED')
    if revision.doctor_id == owner: raise SettlementError('NO_PHYSICIAN_CHANGE')
    if not m.db.session.get(m.User, revision.doctor_id): raise SettlementError('FINAL_REPLACEMENT_ONLY')
    if current:
        old_amount = money(current.new_amount)
        old_rule = json.loads(current.snapshot_json)['new_rule']
    else:
        # Explicit finance confirmation of the legacy entitlement amount.
        old_amount = money(original_amount)
        old_rule = {'source': 'FINANCE_VERIFIED_LEGACY_AMOUNT', 'amount': str(old_amount)}
    new_amount, new_rule = rule_share(m, order, revision.doctor_id)
    payouts = m.FinancialEntry.query.filter_by(entry_type='DOCTOR_FEE', status='POSTED',
        user_id=owner, branch_id=order.branch_id, reference_no=order.accession).order_by(m.FinancialEntry.id).all()
    evidence = [{'id': p.id, 'amount': str(money(p.amount)), 'date': p.entry_date.isoformat(),
                 'method': p.payment_method, 'reference': p.reference_no} for p in payouts]
    paid = sum((money(p.amount) for p in payouts), Decimal('0'))
    verified_paid = money(paid_amount)
    payment_note = str(payment_note or '').strip()
    if verified_paid < paid or (verified_paid > paid and not 10 <= len(payment_note) <= 2000):
        raise SettlementError('PAYMENTS_NOT_VERIFIED')
    from report_revisions import latest as latest_version
    version = latest_version(m, revision)
    if not version or not version.finalized_at: raise SettlementError('FINAL_REPLACEMENT_ONLY')
    return dict(actor_id=u.id, revision_id=revision.id, revision_no=revision.revision_no,
        order_id=order.id, branch_id=order.branch_id, accession=order.accession,
        finalized_at=revision.finalized_at.isoformat(), final_version_id=version.id,
        final_sha256=version.sha256, previous_id=current.id if current else None,
        old_doctor_id=owner, new_doctor_id=revision.doctor_id,
        old_amount=str(old_amount), new_amount=str(new_amount), linked_paid_amount=str(paid),
        verified_paid_amount=str(verified_paid), payment_note=payment_note,
        recovery_adjustment=str(min(verified_paid, old_amount)),
        old_rule=old_rule, new_rule=new_rule, payouts=evidence, reason=reason,
        payments_verified=True, original_amount=str(old_amount),
        policy='FINAL_REPLACEMENT_NEW_DOCTOR_RULE_REVERSAL_V1')


def fingerprint(data):
    return hashlib.sha256(json.dumps(data, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def signer(m):
    return URLSafeTimedSerializer(m.app.config['SECRET_KEY'], salt='replacement-settlement-preview-v1')


def preview(m, revision, original_amount, reason, payments_verified, paid_amount, payment_note=''):
    data = plan(m, revision, original_amount, reason, payments_verified, paid_amount, payment_note)
    token = signer(m).dumps({'data': data, 'sha256': fingerprint(data)})
    return data, token


def confirm(m, token):
    try: claims = signer(m).loads(token, max_age=600)
    except (BadSignature, SignatureExpired): raise SettlementError('STALE_PREVIEW')
    data = claims['data']
    order = m.Order.query.filter_by(id=data['order_id']).with_for_update().populate_existing().first()
    u = actor(m, order, manage=True)
    if not order or u.id != data['actor_id'] or fingerprint(data) != claims['sha256']:
        raise SettlementError('STALE_PREVIEW')
    revision = m.ReportRevision.query.filter_by(id=data['revision_id']).with_for_update().populate_existing().first()
    if not revision or revision.order_id != order.id: raise SettlementError('STALE_PREVIEW')
    existing = m.ReplacementSettlement.query.filter_by(revision_id=revision.id).first()
    if existing:
        if existing.preview_sha256 != claims['sha256']: raise SettlementError('STALE_PREVIEW')
        return existing, True
    current = plan(m, revision, data['original_amount'], data['reason'], data['payments_verified'], data['verified_paid_amount'], data['payment_note'])
    if fingerprint(current) != claims['sha256']: raise SettlementError('STALE_PREVIEW')
    row = m.ReplacementSettlement(revision_id=revision.id, order_id=order.id,
        branch_id=order.branch_id, revision_no=revision.revision_no,
        previous_id=current['previous_id'], old_doctor_id=current['old_doctor_id'],
        new_doctor_id=current['new_doctor_id'], old_amount=money(current['old_amount']),
        new_amount=money(current['new_amount']), linked_paid_amount=money(current['linked_paid_amount']),
        verified_paid_amount=money(current['verified_paid_amount']),
        preview_sha256=claims['sha256'], snapshot_json=json.dumps(current, sort_keys=True),
        reason=current['reason'], created_by=u.id)
    m.db.session.add(row)
    m.db.session.flush()
    m.audit_as_user(u, 'REPLACEMENT_ENTITLEMENT_TRANSFER', 'replacement_settlement', row.id,
        json.dumps({'order_id':order.id,'revision_id':revision.id,'before':{
            'doctor_id':row.old_doctor_id,'entitlement':str(row.old_amount)},'after':{
            'doctor_id':row.new_doctor_id,'entitlement':str(row.new_amount)},
            'reversal':str(-row.old_amount),'original_payouts_preserved':True,
            'linked_paid':str(row.linked_paid_amount),'verified_paid':str(row.verified_paid_amount),
            'payment_note':current['payment_note'],'reason':row.reason}, sort_keys=True))
    return row, False


def csrf(m):
    saved = session.get('replacement_settlement_csrf', '')
    provided = request.form.get('csrf', '')
    if not saved or not provided or not hmac.compare_digest(saved, provided):
        raise SettlementError('CSRF')


def guard_case_payout(m, branch_id, doctor_id, accession):
    """A case-specific cash entry cannot pay the superseded entitlement owner."""
    order = m.Order.query.filter_by(accession=str(accession or '').strip()).first()
    if not order:
        return  # legacy aggregate payouts have no reliable case attribution
    u = m.current_user()
    if not u or not u.active or branch_id != order.branch_id:
        m.abort(403)
    if not m.has_perm('*') and u.branch_id != order.branch_id:
        m.abort(403)
    order = m.Order.query.filter_by(id=order.id).with_for_update().populate_existing().one()
    allocation = latest(m, order.id)
    original = m.performing_doctor_for_order(order)
    owner = allocation.new_doctor_id if allocation else (original.id if original else None)
    pending = m.ReportRevision.query.filter_by(order_id=order.id, kind='REPLACEMENT', status='FINAL').filter(
        m.ReportRevision.revision_no > (allocation.revision_no if allocation else 0),
        m.ReportRevision.doctor_id != owner,
    ).first()
    if pending:
        m.abort(409, description='FINAL_REPLACEMENT_AWAITING_SETTLEMENT')
    if allocation and doctor_id != owner:
        m.abort(409, description='CASE_ENTITLEMENT_BELONGS_TO_REPLACEMENT_PHYSICIAN')


def register(m):
    models(m)
    @m.app.route('/finance/replacement-settlements', methods=['GET', 'POST'])
    @m.login_required
    def replacement_settlements():
        u = actor(m, manage=request.method == 'POST')
        error, draft, token = None, None, None
        if request.method == 'POST':
            try:
                csrf(m)
                if request.form.get('action') == 'confirm':
                    row, retry = confirm(m, request.form.get('preview_token', ''))
                    m.db.session.commit()
                    m.flash('التسوية محفوظة؛ قيود الصرف الأصلية لم تتغير. / Settlement recorded; original payouts preserved.', 'success')
                    return m.redirect(m.url_for('replacement_settlements'), code=303)
                if request.form.get('action') != 'preview': raise SettlementError('STALE_PREVIEW')
                revision = m.ReportRevision.query.get_or_404(request.form.get('revision_id', type=int))
                draft, token = preview(m, revision, request.form.get('original_amount'), request.form.get('reason'), request.form.get('payments_verified') == '1', request.form.get('paid_amount'), request.form.get('payment_note'))
            except SettlementError as exc:
                m.db.session.rollback()
                labels = MESSAGES.get(str(exc), MESSAGES['STALE_PREVIEW'])
                error = labels[0 if m.current_ui_language() == 'ar' else 1]
        q = m.ReportRevision.query.join(m.Order, m.Order.id == m.ReportRevision.order_id).filter(
            m.ReportRevision.status == 'FINAL', m.ReportRevision.kind == 'REPLACEMENT')
        history = m.ReplacementSettlement.query
        if not m.has_perm('*'):
            q = q.filter(m.Order.branch_id == u.branch_id)
            history = history.filter_by(branch_id=u.branch_id)
        revisions = q.order_by(m.ReportRevision.finalized_at.desc(), m.ReportRevision.id.desc()).limit(200).all()
        booked = {r.revision_id: r for r in history.filter(m.ReplacementSettlement.revision_id.in_([r.id for r in revisions])).all()}
        orders = {o.id: o for o in m.Order.query.filter(m.Order.id.in_([r.order_id for r in revisions])).all()}
        ids = {r.doctor_id for r in revisions} | {r.old_doctor_id for r in booked.values()} | {r.new_doctor_id for r in booked.values()}
        if draft: ids.update((draft['old_doctor_id'], draft['new_doctor_id']))
        doctors = {d.id: d for d in m.User.query.filter(m.User.id.in_(ids)).all()}
        session.setdefault('replacement_settlement_csrf', secrets.token_urlsafe(32))
        return m.render_template('replacement_settlements.html', revisions=revisions, booked=booked,
            orders=orders, doctors=doctors, draft=draft, preview_token=token, error=error,
            csrf=session['replacement_settlement_csrf'], can_manage=m.has_perm('finance.doctor_share.manage'))
