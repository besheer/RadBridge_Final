"""Read projections over explicit evidence with no web or database runtime."""
from datetime import datetime, timedelta
from types import SimpleNamespace as Row
import pytest
from application.services.assignment.monitoring_queries import AssignmentMonitoring

NOW=datetime(2026,10,12,12)


class Repository:
    def __init__(self):self.orders=[];self.assignments=[];self.report_rows=[];self.offers=[];self.states=[];self.profile_rows=[];self.report_reads=[]
    def profiles(self):return self.profile_rows
    def presence(self):return self.states
    def active_assignments(self):return self.assignments
    def open_orders(self):return self.orders
    def reports(self,ids):self.report_reads.append(ids);return self.report_rows
    def pending_offers(self):return self.offers


def make_order(id,doctor=None,visit=None):return Row(id=id,assigned_doctor_id=doctor,assignment_visit_id=visit)
def make_assignment(order,doctor,kind='AUTO',started=None):
    return Row(order_id=order,doctor_user_id=doctor,assignment_type=kind,reading_started_at=started,start_deadline_at=NOW-timedelta(minutes=2))
def build(repo,reclaim=True):
    return AssignmentMonitoring(repo,doctors=lambda:[Row(id=7)],policy=lambda:{'reclaim_enabled':reclaim},
        capacity=lambda doctor,policy:3,auto_types={'AUTO'},clock=lambda:NOW)


def test_completed_report_and_orphan_offer_are_excluded_from_reservations():
    repo=Repository();repo.orders=[make_order(1,visit=99),make_order(2,visit=99),make_order(3)]
    repo.report_rows=[Row(order_id=3,status='FINAL')]
    repo.offers=[Row(order_id=1,doctor_user_id=7),Row(order_id=3,doctor_user_id=7),Row(order_id=100,doctor_user_id=7)]
    result=build(repo).snapshot()
    assert [case['order'].id for case in result['cases']]==[1,2]
    assert result['doctors'][0]['reserved']==2
    assert [offer.order_id for offer in result['offers']]==[1]
    assert all(case['linked'] and case['visit_count']==2 for case in result['waiting'])


def test_manual_started_and_stale_owner_have_no_reclaim_deadline():
    repo=Repository();repo.orders=[make_order(id,7) for id in (1,2,3,4)]
    repo.assignments=[make_assignment(1,7),make_assignment(2,7,kind='MANUAL'),
                      make_assignment(3,7,started=NOW),make_assignment(4,8)]
    before=[vars(row).copy() for row in repo.assignments]
    result=build(repo).snapshot()
    assert [case['order'].id for case in result['overdue']]==[1]
    assert result['cases'][0]['remaining']==-120
    assert all(case['deadline'] is None for case in result['cases'][1:])
    assert result['cases'][3]['assignment'] is None
    assert result['doctors'][0]['active']==4 and result['doctors'][0]['cap']==3
    assert [vars(row) for row in repo.assignments]==before


def test_disabled_reclaim_does_not_hide_deadline_but_disables_overdue_bucket():
    repo=Repository();repo.orders=[make_order(1,7)];repo.assignments=[make_assignment(1,7)]
    result=build(repo,reclaim=False).snapshot()
    assert result['cases'][0]['deadline'] and not result['overdue']


@pytest.mark.parametrize('state,age,online',[('AVAILABLE',5,True),('AVAILABLE',6,False),('OFFLINE',0,False)])
def test_presence_window_and_offline_state(state,age,online):
    repo=Repository();repo.states=[Row(user_id=7,state=state,last_seen_at=NOW-timedelta(minutes=age))]
    row=build(repo).snapshot()['doctors'][0]
    assert row['online'] is online and row['state']==state


def test_missing_presence_is_unknown_and_empty_orders_do_not_query_reports():
    repo=Repository();result=build(repo).snapshot()
    assert result['now']==NOW and repo.report_reads==[]
    assert result['doctors'][0]['state']=='UNKNOWN' and not result['doctors'][0]['online']
    assert repo.states==[] and repo.profile_rows==[]
