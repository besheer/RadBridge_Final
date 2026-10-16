"""Authorized daily closing mutations over explicit transaction dependencies.

Caller commits or rolls back. Repository locks the branch before its closing
row, including first creation, and totals come from locked-context evidence.
"""
import json
from domain.finance.closing_policy import money
from application.services.finance.closing_totals import payment_totals


class ClosingLocked(ValueError):
    pass


FIELDS=('status','expected_cash','expected_card','expected_other',
        'counted_cash','counted_card','counted_other','difference','notes')


def save_closing(*, repository, authorize, audit, clock, branch_id, closing_date,
                 actor_user_id, action, counted, notes=''):
    authorize(branch_id)
    if action not in ('SAVE','CLOSE'):
        raise ValueError('Invalid closing action')
    repository.lock_branch(branch_id)
    row=repository.lock_closing(branch_id,closing_date)
    if row and row.status=='CLOSED':
        raise ClosingLocked('This day is closed and cannot be edited.')
    totals=payment_totals(repository=repository,branch_id=branch_id,closing_date=closing_date)
    counted={key:money(counted.get(key)) for key in totals}
    before={key:getattr(row,key) for key in FIELDS} if row else None
    if row is None:
        row=repository.create_closing(branch_id=branch_id,closing_date=closing_date,cashier_user_id=actor_user_id)
        repository.add(row)
    for key in totals:
        setattr(row,'expected_'+key.lower(),totals[key])
        setattr(row,'counted_'+key.lower(),float(counted[key]))
    row.difference=float(sum(counted.values())-sum(money(v) for v in totals.values()))
    row.notes=(notes or '').strip()
    row.status='CLOSED' if action=='CLOSE' else 'OPEN'
    if action=='CLOSE':
        row.closed_by=actor_user_id
        row.closed_at=clock()
    repository.flush()
    after={key:getattr(row,key) for key in FIELDS}
    audit('DAILY_CLOSING_'+action,'daily_closing',row.id,
          json.dumps(dict(branch_id=branch_id,date=closing_date.isoformat(),before=before,after=after),ensure_ascii=False))
    return row
