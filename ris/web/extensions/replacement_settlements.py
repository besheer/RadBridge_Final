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

from domain.finance.settlement_policy import CENT, LIMIT, SettlementError, money, fingerprint, rule_share as _rule_share
from application.services.finance import settlement_workflow as _workflow
from infrastructure.adapters.finance.settlement_repository import SqlAlchemySettlementRepository

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


def _repository(m):
    return SqlAlchemySettlementRepository(m.db.session,m.Order,m.User,m.ReportRevision,
        m.ReplacementSettlement,m.FinancialEntry,m.PerformingDoctorShareRule)

def _policies(m):
    from report_revisions import latest as latest_version
    return _workflow.SettlementPolicies(
        actor=lambda order,manage:actor(m,order,manage=manage),
        original_doctor=m.performing_doctor_for_order,
        rule_share=lambda order,doctor_id:rule_share(m,order,doctor_id),
        final_version=lambda revision:latest_version(m,revision), audit=m.audit_as_user,
    )

def rule_share(m,order,doctor_id):
    # Preserve evidence acquisition order: invalid/missing rules fail before
    # querying discounts, just as the original financial workflow did.
    def discounts():
        yield from m.approved_order_discounts(order)
    return _rule_share(order,_repository(m).share_rules(doctor_id),discounts())

def plan(m,revision,original_amount,reason,payments_verified,paid_amount,payment_note=''):
    return _workflow.plan(_repository(m),_policies(m),revision,original_amount,reason,payments_verified,paid_amount,payment_note)

def signer(m):
    return URLSafeTimedSerializer(m.app.config['SECRET_KEY'], salt='replacement-settlement-preview-v1')


def preview(m, revision, original_amount, reason, payments_verified, paid_amount, payment_note=''):
    data = plan(m, revision, original_amount, reason, payments_verified, paid_amount, payment_note)
    token = signer(m).dumps({'data': data, 'sha256': fingerprint(data)})
    return data, token


def confirm(m,token):
    try:claims=signer(m).loads(token,max_age=600)
    except (BadSignature,SignatureExpired):raise SettlementError('STALE_PREVIEW')
    return _workflow.confirm(_repository(m),_policies(m),claims)

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
