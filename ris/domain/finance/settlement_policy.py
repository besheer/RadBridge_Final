"""Deterministic replacement entitlement amounts over explicit approved facts."""
import hashlib
import json
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

CENT = Decimal('0.01')
LIMIT = Decimal('9999999999.99')

class SettlementError(ValueError):
    pass


def money(value):
    try:
        result = Decimal(str(value))
        if not result.is_finite() or result < 0 or result > LIMIT:
            raise ValueError()
        return result.quantize(CENT, rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError, TypeError):
        raise SettlementError('INVALID_MONEY')


def rule_share(order, rules, discounts):
    matches = []
    for r in rules:
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
    discounts = sum((money(d.amount) for d in discounts), Decimal('0'))
    net = max(Decimal('0'), patient_base - discounts)
    base = {'GROSS': gross, 'CONTRACT': contract, 'NET_AFTER_DISCOUNT': net}[rule.basis]
    amount = money(base * value / 100 if rule.rule_type == 'PERCENT' else value)
    frozen = {name: getattr(rule, name) for name in ('id', 'doctor_user_id', 'branch_id', 'modality', 'procedure_id', 'contract_id', 'rule_type', 'basis')}
    frozen.update(value=str(value), base=str(base), amount=str(amount))
    return amount, frozen


def fingerprint(data):
    return hashlib.sha256(json.dumps(data, sort_keys=True, separators=(',', ':')).encode()).hexdigest()

