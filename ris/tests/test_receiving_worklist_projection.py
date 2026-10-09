import json
from uuid import uuid4
import pytest
import app as m
from test_report_template_routes import isolated,client
from test_assignment_distribution import order
from test_assignment_visit_grouping import group,assign_group,doctor
from case_assignment_service import CaseAssignmentServiceError

def test_receiving_member_prevents_partial_visit_assignment(isolated):
    members=group('SYN-RECEIVING-VISIT-'+uuid4().hex)
    u=doctor('receiving-visit-'+uuid4().hex)
    members[-1].pacs_status='RECEIVING';m.db.session.flush()
    with pytest.raises(CaseAssignmentServiceError,match='PACS_RECEIVING'):
        assign_group(members,u,kind='MANUAL')
    assert all(o.assigned_doctor_id is None for o in members)
    assert m.CaseAssignment.query.filter(m.CaseAssignment.order_id.in_([o.id for o in members])).count()==0

@pytest.mark.parametrize('lang',['en','ar'])
@pytest.mark.parametrize('cached',[False,True])
def test_dashboard_filters_receiving_as_blocked_without_writing(isolated,lang,cached):
    c,u=client()
    o=order('SYN-RECEIVING-DASHBOARD-'+uuid4().hex)
    o.pacs_status='RECEIVING';m.db.session.flush()
    row=None
    if cached:
        row=m.CaseReadiness(order_id=o.id,status='READY',score=100,details_json='{"blockers":[]}')
        m.db.session.add(row);m.db.session.flush()
    with c.session_transaction() as s:s['lang']=lang
    result=c.get('/operations/case-readiness?status=BLOCKED')
    assert result.status_code==200 and o.accession.encode() in result.data and b'PACS_RECEIVING' in result.data
    assert o.accession.encode() not in c.get('/operations/case-readiness?status=READY').data
    assert row.status=='READY' if cached else m.CaseReadiness.query.filter_by(order_id=o.id).first() is None

@pytest.mark.parametrize('cached',[False,True])
def test_unassigned_snapshot_cannot_show_ready_during_reception(isolated,cached):
    o=order('SYN-RECEIVING-UNASSIGNED-'+uuid4().hex);o.pacs_status='RECEIVING'
    row=m.CaseReadiness(order_id=o.id,status='READY',score=100,details_json='{"blockers":[]}') if cached else None
    if row:m.db.session.add(row)
    m.db.session.flush()
    snapshot=m.unassigned_case_snapshot(o,row,[])
    assert snapshot['readiness_status']=='BLOCKED' and not snapshot['assignable']
    assert 'PACS_RECEIVING' in [item['code'] for item in snapshot['flags']]
    assert row.status=='READY' if cached else m.CaseReadiness.query.filter_by(order_id=o.id).first() is None
