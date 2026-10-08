"""VERIFIED/FINAL state, attribution, paging and branch privacy boundaries."""
import json
from datetime import datetime
from types import SimpleNamespace as NS
import pytest
from test_physician_final_counts import final_counts
import physician_report_workload as w


@pytest.fixture
def workload(final_counts):
    f=final_counts;m=f.m
    f.orders[0].report = m.Report.query.filter_by(order_id=f.orders[0].id).one()
    f.orders[0].report.verified_at=datetime(2038,1,15)
    o=m.Order(accession=f.orders[0].accession+'V',patient_id=f.orders[0].patient_id,
        branch_id=f.branches[0].id,assigned_doctor_id=f.docs[0].id,modality='MR',procedure='Synthetic verified',
        status='REPORTING',scheduled=datetime(2030,1,1))
    m.db.session.add(o);m.db.session.flush()
    report=m.Report(order_id=o.id,status='VERIFIED',verified_at=datetime(2038,2,11))
    m.db.session.add(report);m.db.session.flush()
    revisions=m.ReportRevision.query.filter_by(order_id=f.orders[0].id).order_by(m.ReportRevision.id).all()
    revisions[0].status='VERIFIED';revisions[0].verified_at=datetime(2038,2,13);revisions[0].finalized_at=None
    m.db.session.flush()
    yield NS(**vars(f),verified_order=o,verified_report=report,revisions=revisions)


def snapshot(c,**kwargs):
    return w.snapshot(c.m,datetime(2038,2,1),datetime(2038,3,1),**kwargs)


def test_current_status_counts_final_once_and_separates_revisions(workload):
    c=workload;r=snapshot(c)
    assert r['totals']==dict(verified=1,final=1,correction_verified=1,correction_final=1)
    assert r['total_details']==4
    assert len([row for row in r['details'] if row['order_id']==c.orders[0].id and row['kind']=='ORIGINAL'])==1
    assert c.docs[1] in r['doctors']
    assert next(row for row in r['summary'] if row['doctor_id']==c.docs[1].id)['correction_cases']==1


@pytest.mark.parametrize('status,expected',[('VERIFIED',2),('FINAL',2),('ALL',4)])
def test_status_filter_keeps_summary_and_detail_consistent(workload,status,expected):
    r=snapshot(workload,status=status)
    assert r['total_details']==expected
    if status!='ALL':assert all(row['status']==status for row in r['details'])
    assert sum(r['totals'].values())==r['total_details']


def test_verification_timestamp_not_appointment_or_version_date(workload):
    c=workload
    assert w.snapshot(c.m,datetime(2030,1,1),datetime(2030,2,1))['total_details']==0
    r=w.snapshot(c.m,datetime(2038,2,11),datetime(2038,2,12))
    assert r['totals']['verified']==1 and r['total_details']==1
    assert r['details'][0]['order_id']==c.verified_order.id
    assert w.snapshot(c.m,datetime(2038,1,15),datetime(2038,1,16))['total_details']==0


def test_unknown_dates_and_drafts_are_excluded(workload):
    c=workload;c.verified_report.verified_at=None;c.revisions[0].status='DRAFT'
    c.m.db.session.flush()
    assert snapshot(c)['totals']==dict(verified=0,final=1,correction_verified=0,correction_final=1)


def test_final_requires_both_original_summaries_final(workload):
    c=workload;c.orders[0].status='REPORTING';c.m.db.session.flush()
    assert snapshot(c)['totals']['final']==0
    assert snapshot(c)['totals']['correction_final']==1


def test_physician_filter_uses_original_and_correction_owners(workload):
    c=workload;r=snapshot(c,doctor_id=c.docs[1].id)
    assert r['total_details']==2 and r['totals']['verified']==r['totals']['final']==0
    assert all(row['doctor_id']==c.docs[1].id for row in r['details'])
    assert snapshot(c,doctor_id=999999)['total_details']==0


def test_branch_scope_hides_case_details_and_physician_choices(workload):
    c=workload;c.orders[1].assigned_doctor_id=c.actor.id;c.m.db.session.flush()
    assert c.actor not in snapshot(c)['doctors']
    from werkzeug.exceptions import Forbidden
    with pytest.raises(Forbidden):snapshot(c,branch_id=c.branches[1].id)
    assert all(row['branch_id']==c.branches[0].id for row in snapshot(c)['details'])
    c.actor.role=c.m.Role.query.filter_by(code='SUPER_ADMIN').one()
    assert snapshot(c)['total_details']==5
    assert snapshot(c,branch_id=c.branches[1].id)['total_details']==1


@pytest.mark.parametrize('change',['inactive','branchless','no_permission'])
def test_unauthorized_access_fails_closed(workload,change):
    c=workload
    if change=='inactive':c.actor.active=False
    if change=='branchless':c.actor.branch_id=None
    if change=='no_permission':c.actor.role.permissions_json='[]'
    from werkzeug.exceptions import Forbidden
    with pytest.raises(Forbidden):snapshot(c)


def test_finance_view_can_read_but_gets_no_case_link_permission(workload):
    c=workload;c.actor.role.permissions_json=json.dumps(['finance.doctor_share.view'])
    assert snapshot(c)['total_details']==4
    assert not snapshot(c)['can_open_cases']


def test_pages_are_complete_disjoint_and_deterministic(workload,monkeypatch):
    monkeypatch.setattr(w,'PAGE_SIZE',2)
    first=snapshot(workload,page=1);second=snapshot(workload,page=2)
    key=lambda row:(row['kind'],row['report_id'])
    assert first['pages']==2 and first['total_details']==4
    assert not {key(row) for row in first['details']} & {key(row) for row in second['details']}
    assert first['details']==snapshot(workload,page=1)['details']
    assert first['totals']==second['totals']


@pytest.mark.parametrize('query',['status=DRAFT','status=verified','page=0','page=-1','page=nope','page=9999','doctor_id=-1','branch_id=0','start=bad','start=2038-03-01&end=2038-02-01'])
def test_invalid_filters_rejected(workload,query):
    prefix='start=2038-02-01&end=2038-02-28&' if 'start=' not in query else ''
    assert workload.client.get('/coordinator/physician-reports?'+prefix+query).status_code==400


@pytest.mark.parametrize('language',['en','ar'])
def test_real_route_template_is_read_only_and_has_both_sections(workload,language,monkeypatch):
    c=workload;monkeypatch.setattr(c.m,'current_ui_language',lambda:language)
    before=(c.m.Order.query.count(),c.m.Report.query.count(),c.m.ReportRevision.query.count(),c.m.AuditLog.query.count(),c.m.FinancialEntry.query.count())
    response=c.client.get('/coordinator/physician-reports?start=2038-02-01&end=2038-02-28')
    assert response.status_code==200
    text=response.get_data(as_text=True)
    assert 'VERIFIED' in text and 'FINAL' in text and c.verified_order.accession in text
    assert c.orders[1].accession not in text
    assert ('Case report list' if language=='en' else 'قائمة تقارير الحالات') in text
    assert 'href="/orders/'+str(c.verified_order.id)+'"' not in text
    assert before==(c.m.Order.query.count(),c.m.Report.query.count(),c.m.ReportRevision.query.count(),c.m.AuditLog.query.count(),c.m.FinancialEntry.query.count())
    assert c.verified_report.status=='VERIFIED' and c.revisions[0].status=='VERIFIED'


def test_original_approver_does_not_change_reporting_attribution(workload):
    c=workload;c.verified_report.verified_by=c.docs[1].full_name;c.m.db.session.flush()
    original=next(r for r in snapshot(c)['details'] if r['order_id']==c.verified_order.id)
    assert original['doctor_id']==c.docs[0].id


def test_unassigned_owner_stays_explicit(workload):
    c=workload;c.verified_order.assigned_doctor_id=None;c.m.db.session.flush()
    assert any(row['doctor_id'] is None and row['verified']==1 for row in snapshot(c)['summary'])


def test_physician_choice_remains_when_selected_status_has_no_results(workload):
    c=workload;c.verified_report.status='DRAFT';c.revisions[0].status='DRAFT';c.m.db.session.flush()
    result=snapshot(c,status='VERIFIED',doctor_id=c.docs[0].id)
    assert result['total_details']==0 and c.docs[0] in result['doctors']
    html=c.client.get('/coordinator/physician-reports?start=2038-02-01&end=2038-02-28&status=VERIFIED&doctor_id='+str(c.docs[0].id)).get_data(as_text=True)
    assert 'value="'+str(c.docs[0].id)+'" selected' in html
    assert c.orders[1].accession not in html
