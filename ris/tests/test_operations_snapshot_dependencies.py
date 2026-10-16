from datetime import datetime, timedelta, timezone
from types import SimpleNamespace as Row
from application.services.readiness.operations_snapshot import build_case_operations_snapshot
from domain.readiness_checks import view


NOW=datetime(2026,1,1)


class Repository:
    def __init__(self):
        self.calls=[]
        self.rows=[Row(id=1,status='REPORTING',pacs_status='RECEIVING'),Row(id=2,status='FINAL',pacs_status='IMAGES_COMPLETE')]
    def orders(self,limit,branch_ids=None): self.calls.append(('orders',limit,branch_ids));return self.rows
    def reports(self,ids): return [Row(order_id=2,status='FINAL')]
    def readiness(self,ids): return [Row(order_id=1,status='READY',missing_pacs=False,missing_series=False,missing_history=False,incomplete_images=False)]
    def assignments(self,ids): return []
    def pending_offers(self,ids): return [Row(order_id=1)]
    def leases(self,order_ids=None): return [dict(order_id=1,expires_at=NOW.replace(tzinfo=timezone.utc)+timedelta(seconds=10)),dict(order_id=2,expires_at=NOW)]
    def inbox(self,state,limit,order_ids=None): self.calls.append((state,limit));return []
    def active_links(self,limit,order_ids=None): return []
    def strategies(self,branch_ids=None): return []
    def recent_escalations(self,order_ids=None): return []
    def recent_pacs_events(self,order_ids=None): return []


def test_receiving_projection_blocks_ready_and_terminal_case_has_no_attention():
    repo=Repository()
    result=build_case_operations_snapshot(repository=repo,readiness_view=view,clock=lambda:NOW,limit=5000)
    assert repo.calls==[('orders',1000,None),('REVIEW_REQUIRED',1000),('QUARANTINED',1000)]
    assert result['generated_at']==NOW
    assert result['metrics']['blocked_cases']==1 and result['metrics']['ready_cases']==0
    assert result['metrics']['expired_leases']==1 and result['metrics']['active_editors']==1
    assert result['cases'][0]['attention_reasons']==['READINESS_BLOCKED','INCOMPLETE_IMAGES','UNASSIGNED','PENDING_OFFER','ACTIVE_EDITOR']
    assert result['cases'][1]['attention_reasons']==[] and result['cases'][1]['terminal']
    assert repo.rows[0].pacs_status=='RECEIVING'


def test_explicit_now_does_not_read_clock_and_repositories_are_independent():
    repo=Repository(); other=Repository();other.rows=[]
    result=build_case_operations_snapshot(repository=other,readiness_view=view,clock=lambda:1/0,now=NOW)
    assert result['cases']==[] and result['metrics']['open_cases']==0
    assert repo.calls==[]
