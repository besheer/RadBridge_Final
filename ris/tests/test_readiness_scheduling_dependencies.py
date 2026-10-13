import json
from datetime import datetime, timedelta
from types import SimpleNamespace as Row
import pytest
from application.services.readiness import scheduling as service
from domain.readiness_schedule import DEFAULTS


NOW = datetime(2026,1,1)


class Repository:
    def __init__(self):
        self.calls = []
        self.orders = [Row(id=1,status='IMAGES_RECEIVED',exam_status='EXAM_COMPLETED',modality='CT',report=None)]
        self.report = Row(status='UNREPORTED'); self.exists = True
        self.evidence = None
        self.lease = Row(acquired=True,release=lambda: self.calls.append('release'))
    def acquire_run_lock(self): self.calls.append('lease'); return self.lease
    def candidate_ids(self): self.calls.append('candidates'); return [r.id for r in self.orders]
    def lock_order(self, oid): self.calls.append('order'); return next(o for o in self.orders if o.id==oid)
    def lock_report(self, oid): self.calls.append('report'); return self.report
    def report_exists(self, oid): self.calls.append('exists'); return self.exists
    def readiness(self, oid): self.calls.append('readiness'); return self.evidence
    def commit(self): self.calls.append('commit')
    def rollback(self): self.calls.append('rollback')
    def record_automatic_audit(self, oid, payload): self.calls.append(('audit',oid,json.loads(payload)))


def run(repo, **values):
    args = dict(repository=repo,config=dict(DEFAULTS,enabled=True),refresh_order=lambda order:repo.calls.append('refresh'),
                clock=lambda:NOW,monotonic=lambda:0)
    args.update(values)
    return service.run_due(**args)


def test_paused_does_not_acquire_lock_or_read_clock():
    repo=Repository()
    assert run(repo,config=dict(DEFAULTS),clock=lambda:pytest.fail('clock')) == dict(enabled=False,checked=0,errors=0)
    assert repo.calls == []


def test_busy_does_not_retrieve_or_mutate():
    repo=Repository(); repo.lease.acquired=False
    assert run(repo) == dict(enabled=True,checked=0,errors=0,busy=True)
    assert repo.calls == ['lease']


@pytest.mark.parametrize('status', ['FINAL','VERIFIED'])
def test_terminal_report_rollback_without_refresh(status):
    repo=Repository(); repo.report.status=status
    assert run(repo)['checked']==0
    assert repo.calls == ['lease','candidates','order','report','rollback','release']


def test_contended_report_is_not_treated_as_missing():
    repo=Repository(); repo.report=None
    assert run(repo)['checked']==0
    assert repo.calls == ['lease','candidates','order','report','exists','rollback','release']


def test_interval_rolls_back_and_success_commits_before_releasing_lock():
    repo=Repository(); repo.evidence=Row(checked_at=NOW-timedelta(seconds=10))
    assert run(repo)['checked']==0
    assert 'refresh' not in repo.calls and repo.calls[-2:]==['rollback','release']
    repo.evidence.checked_at=NOW-timedelta(seconds=301); repo.calls=[]
    assert run(repo)['checked']==1
    assert repo.calls[-3:]==['refresh','commit','release']


def test_failed_refresh_rolls_back_counts_against_batch_and_releases():
    repo=Repository(); repo.orders.append(Row(id=2,status='IMAGES_RECEIVED',exam_status='EXAM_COMPLETED',modality='CT',report=None))
    def fail(order): raise RuntimeError('synthetic provider failure')
    assert run(repo,config=dict(DEFAULTS,enabled=True,batch_limit=1),refresh_order=fail)==dict(enabled=True,checked=0,errors=1)
    assert repo.calls.count('order')==1
    assert repo.calls[-2:]==['rollback','release']


def test_candidate_failure_still_releases_global_lock():
    repo=Repository()
    def fail(): raise RuntimeError('synthetic query failure')
    repo.candidate_ids=fail
    with pytest.raises(RuntimeError,match='synthetic query failure'):run(repo)
    assert repo.calls==['lease','release']


def test_elapsed_budget_stops_before_order_lock():
    repo=Repository(); ticks=iter([0,20])
    assert run(repo,monotonic=lambda:next(ticks))['checked']==0
    assert repo.calls==['lease','candidates','release']


@pytest.mark.parametrize('error,blocker', [('Unavailable','PACS_UNAVAILABLE'),('Identity mismatch','PACS_IDENTITY_MISMATCH'),('No authoritative PACS study link','PACS_NOT_LINKED')])
def test_failed_pacs_evidence_is_blocked_hashed_and_audited(error,blocker):
    repo=Repository(); order=repo.orders[0]
    row=Row(status='READY',score=100,missing_pacs=False,details_json=json.dumps(dict(pacs_error=error,blockers=[])))
    result=service.refresh(repository=repo,evaluate=lambda order:row,audit_actor=lambda *args:pytest.fail('actor audit'),order=order)
    assert result.status=='BLOCKED' and result.missing_pacs and result.score==0
    assert json.loads(result.details_json)['blockers']==[blocker]
    assert len(result.facts_sha256)==64
    assert repo.calls[-1][2]['new_status']=='BLOCKED'


def test_unchanged_automatic_refresh_has_no_duplicate_audit():
    repo=Repository(); repo.evidence=Row(status='BLOCKED')
    row=Row(status='BLOCKED',details_json='{}')
    service.refresh(repository=repo,evaluate=lambda order:row,audit_actor=None,order=repo.orders[0])
    assert repo.calls==['readiness']
