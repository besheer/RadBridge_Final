"""Replacement settlement planning/confirmation with explicit evidence ports."""
import json
from decimal import Decimal
from dataclasses import dataclass
from typing import Callable
from domain.finance.settlement_policy import SettlementError, money, fingerprint


@dataclass(frozen=True)
class SettlementPolicies:
    actor: Callable
    original_doctor: Callable
    rule_share: Callable
    final_version: Callable
    audit: Callable


def plan(repository, policies, revision, original_amount, reason, payments_verified, paid_amount, payment_note=''):
    order = repository.get_order(revision.order_id)
    u = policies.actor(order, manage=True)
    reason = str(reason or '').strip()
    if not 10 <= len(reason) <= 2000: raise SettlementError('REASON_REQUIRED')
    if not payments_verified: raise SettlementError('PAYMENTS_NOT_VERIFIED')
    if revision.kind != 'REPLACEMENT' or revision.status != 'FINAL' or not revision.finalized_at:
        raise SettlementError('FINAL_REPLACEMENT_ONLY')
    if not order or not order.branch_id: raise SettlementError('FINAL_REPLACEMENT_ONLY')
    current = repository.latest(order.id)
    if current and current.revision_no >= revision.revision_no: raise SettlementError('STALE_PREVIEW')
    original = policies.original_doctor(order)
    # No invented attribution when the legacy financial owner is absent.
    owner = current.new_doctor_id if current else (original.id if original else None)
    if owner is None: raise SettlementError('ORIGINAL_DOCTOR_UNKNOWN')
    first_unsettled = repository.earlier_unsettled(order.id, revision.revision_no, current.revision_no if current else 0, owner)
    if first_unsettled: raise SettlementError('PREVIOUS_REPLACEMENT_UNSETTLED')
    if revision.doctor_id == owner: raise SettlementError('NO_PHYSICIAN_CHANGE')
    if not repository.get_doctor(revision.doctor_id): raise SettlementError('FINAL_REPLACEMENT_ONLY')
    if current:
        old_amount = money(current.new_amount)
        old_rule = json.loads(current.snapshot_json)['new_rule']
    else:
        # Explicit finance confirmation of the legacy entitlement amount.
        old_amount = money(original_amount)
        old_rule = {'source': 'FINANCE_VERIFIED_LEGACY_AMOUNT', 'amount': str(old_amount)}
    new_amount, new_rule = policies.rule_share(order, revision.doctor_id)
    payouts = repository.payouts(owner, order.branch_id, order.accession)
    evidence = [{'id': p.id, 'amount': str(money(p.amount)), 'date': p.entry_date.isoformat(),
                 'method': p.payment_method, 'reference': p.reference_no} for p in payouts]
    paid = sum((money(p.amount) for p in payouts), Decimal('0'))
    verified_paid = money(paid_amount)
    payment_note = str(payment_note or '').strip()
    if verified_paid < paid or (verified_paid > paid and not 10 <= len(payment_note) <= 2000):
        raise SettlementError('PAYMENTS_NOT_VERIFIED')
    version = policies.final_version(revision)
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


def confirm(repository, policies, claims):
    data = claims['data']
    order = repository.lock_order(data['order_id'])
    u = policies.actor(order, manage=True)
    if not order or u.id != data['actor_id'] or fingerprint(data) != claims['sha256']:
        raise SettlementError('STALE_PREVIEW')
    revision = repository.lock_revision(data['revision_id'])
    if not revision or revision.order_id != order.id: raise SettlementError('STALE_PREVIEW')
    existing = repository.by_revision(revision.id)
    if existing:
        if existing.preview_sha256 != claims['sha256']: raise SettlementError('STALE_PREVIEW')
        return existing, True
    current = plan(repository, policies, revision, data['original_amount'], data['reason'], data['payments_verified'], data['verified_paid_amount'], data['payment_note'])
    if fingerprint(current) != claims['sha256']: raise SettlementError('STALE_PREVIEW')
    row = repository.create(revision_id=revision.id, order_id=order.id,
        branch_id=order.branch_id, revision_no=revision.revision_no,
        previous_id=current['previous_id'], old_doctor_id=current['old_doctor_id'],
        new_doctor_id=current['new_doctor_id'], old_amount=money(current['old_amount']),
        new_amount=money(current['new_amount']), linked_paid_amount=money(current['linked_paid_amount']),
        verified_paid_amount=money(current['verified_paid_amount']),
        preview_sha256=claims['sha256'], snapshot_json=json.dumps(current, sort_keys=True),
        reason=current['reason'], created_by=u.id)
    repository.add(row)
    repository.flush()
    policies.audit(u, 'REPLACEMENT_ENTITLEMENT_TRANSFER', 'replacement_settlement', row.id,
        json.dumps({'order_id':order.id,'revision_id':revision.id,'before':{
            'doctor_id':row.old_doctor_id,'entitlement':str(row.old_amount)},'after':{
            'doctor_id':row.new_doctor_id,'entitlement':str(row.new_amount)},
            'reversal':str(-row.old_amount),'original_payouts_preserved':True,
            'linked_paid':str(row.linked_paid_amount),'verified_paid':str(row.verified_paid_amount),
            'payment_note':current['payment_note'],'reason':row.reason}, sort_keys=True))
    return row, False

