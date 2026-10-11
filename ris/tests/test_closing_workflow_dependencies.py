import json
from datetime import date,datetime
from types import SimpleNamespace as Row
import pytest
from application.services.finance.closing_workflow import save_closing,ClosingLocked


class Repository:
    def __init__(self, row=None): self.row=row;self.calls=[]
    def lock_branch(self, id): self.calls.append('branch')
    def lock_closing(self, id, date): self.calls.append('closing');return self.row
    def receipts(self,*args): self.calls.append('receipts');return [Row(order_id=1,method='CASH',amount=10)]
    def refunds(self,*args): self.calls.append('refunds');return []
    def create_closing(self,**values): self.calls.append('create');return Row(id=3,**values)
    def add(self,row): self.calls.append('add')
    def flush(self): self.calls.append('flush')


def request(repo,**changes):
    values=dict(repository=repo,authorize=lambda branch:repo.calls.append('authorize'),
                audit=lambda *args:repo.calls.append(('audit',args)),clock=lambda:datetime(2026,1,1),
                branch_id=7,closing_date=date(2026,1,1),actor_user_id=2,action='CLOSE',
                counted=dict(CASH=9,CARD=0,OTHER=0),notes=' Synthetic ')
    values.update(changes);return values


def test_authorization_precedes_locks_and_all_persistence():
    repo=Repository()
    def deny(branch):raise PermissionError('synthetic denied')
    with pytest.raises(PermissionError):save_closing(**request(repo,authorize=deny))
    assert repo.calls==[]


def test_first_creation_serializes_branch_before_closing_and_audits_flushed_snapshot():
    repo=Repository()
    row=save_closing(**request(repo))
    assert repo.calls[:5]==['authorize','branch','closing','receipts','refunds']
    assert repo.calls[-2]=='flush' and repo.calls[-1][0]=='audit'
    assert row.status=='CLOSED' and row.closed_by==2 and row.closed_at==datetime(2026,1,1)
    assert row.expected_cash==10 and row.counted_cash==9 and row.difference==-1 and row.notes=='Synthetic'
    action,entity,id,payload=repo.calls[-1][1]
    assert (action,entity,id)==('DAILY_CLOSING_CLOSE','daily_closing',3)
    assert json.loads(payload)['before'] is None
    assert json.loads(payload)['after']['status']=='CLOSED'


def test_closed_day_blocks_before_counting_or_evidence_and_is_unchanged():
    row=Row(status='CLOSED',notes='Original')
    repo=Repository(row)
    with pytest.raises(ClosingLocked):save_closing(**request(repo,counted=dict(CASH='nan')))
    assert repo.calls==['authorize','branch','closing']
    assert row.__dict__==dict(status='CLOSED',notes='Original')


def test_invalid_count_does_not_create_closing_or_audit():
    repo=Repository()
    with pytest.raises(ValueError,match='Enter valid counted amounts'):
        save_closing(**request(repo,counted=dict(CASH='nan')))
    assert repo.calls==['authorize','branch','closing','receipts','refunds']


def test_invalid_action_never_queries():
    repo=Repository()
    with pytest.raises(ValueError,match='Invalid closing action'):save_closing(**request(repo,action='REOPEN'))
    assert repo.calls==['authorize']


def test_open_save_retains_row_and_records_original_values():
    row=Row(id=4,status='OPEN',expected_cash=2,expected_card=0,expected_other=0,
            counted_cash=2,counted_card=0,counted_other=0,difference=0,notes='Earlier')
    repo=Repository(row)
    assert save_closing(**request(repo,action='SAVE')) is row
    assert row.status=='OPEN' and not hasattr(row,'closed_at')
    assert 'create' not in repo.calls
    payload=json.loads(repo.calls[-1][1][3])
    assert payload['before']['expected_cash']==2 and payload['after']['expected_cash']==10


def test_failed_flush_does_not_issue_success_audit_and_leaves_rollback_to_caller():
    repo=Repository()
    def fail():raise RuntimeError('synthetic flush failure')
    repo.flush=fail
    with pytest.raises(RuntimeError,match='synthetic flush failure'):save_closing(**request(repo))
    assert not any(isinstance(c,tuple) and c[0]=='audit' for c in repo.calls)
