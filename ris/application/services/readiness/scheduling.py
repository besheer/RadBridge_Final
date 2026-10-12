"""Readiness refresh and bounded scheduling over explicit dependencies."""
import hashlib
import json
from domain.readiness_schedule import CLOSED, eligible, interval


def refresh(*, repository, evaluate, audit_actor, order, actor=None):
    old = repository.readiness(order.id)
    previous = old.status if old else 'NOT_CHECKED'
    row = evaluate(order)
    details = json.loads(row.details_json or '{}')
    if details.get('pacs_error'):
        row.status = 'BLOCKED'; row.missing_pacs = True; row.score = 0
        error = str(details['pacs_error']).lower()
        reason = ('PACS_NOT_LINKED' if 'no authoritative pacs study link' in error else
                  ('PACS_IDENTITY_MISMATCH' if 'mismatch' in error else 'PACS_UNAVAILABLE'))
        details['blockers'] = sorted(set(details.get('blockers', []) + [reason]))
        row.details_json = json.dumps(details, ensure_ascii=False)
        row.facts_sha256 = hashlib.sha256(row.details_json.encode()).hexdigest()
    if actor or previous != row.status:
        payload = json.dumps(dict(old_status=previous, new_status=row.status,
                                  automatic=actor is None, blockers=details.get('blockers', [])))
        if actor:
            audit_actor(actor, 'CASE_READINESS_RECHECKED', 'order', order.id, payload)
        else:
            repository.record_automatic_audit(order.id, payload)
    return row


def run_due(*, repository, config, refresh_order, clock, monotonic, now=None, budget_seconds=15):
    if not config['enabled']:
        return dict(enabled=False, checked=0, errors=0)
    now = now or clock()
    start = monotonic(); checked = errors = 0
    lease = repository.acquire_run_lock()
    if not lease.acquired:
        return dict(enabled=True, checked=0, errors=0, busy=True)
    try:
        ids = repository.candidate_ids()
        for oid in ids:
            if checked + errors >= config['batch_limit'] or monotonic() - start >= budget_seconds:
                break
            order = repository.lock_order(oid)
            if not order:
                continue
            report = repository.lock_report(oid)
            if report is None and repository.report_exists(oid):
                repository.rollback(); continue
            if (report and str(report.status or '').upper() in CLOSED) or not eligible(order):
                repository.rollback(); continue
            row = repository.readiness(oid)
            if row and row.checked_at and (now-row.checked_at).total_seconds() < interval(config, order.modality):
                repository.rollback(); continue
            try:
                refresh_order(order); repository.commit(); checked += 1
            except Exception:
                repository.rollback(); errors += 1
        return dict(enabled=True, checked=checked, errors=errors)
    finally:
        lease.release()
