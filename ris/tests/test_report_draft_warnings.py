from datetime import datetime, timedelta
from types import SimpleNamespace as NS
import pytest
from flask import Flask, jsonify
from report_draft_warnings import build_warnings, register, snapshot

NOW=datetime(2026,10,7,12)
def row(**kw):
    return NS(**dict(status='READY',checked_at=NOW,**kw))
def codes(warnings):return [w['code'] for w in warnings]

def test_ready_has_no_warning():
    assert build_warnings(NS(exam_status='EXAM_COMPLETED'),row(),NOW)==[]

@pytest.mark.parametrize('status',['BOOKED','ORDERED','IN_PROGRESS',None])
def test_unfinished_does_not_block(status):
    warnings=build_warnings(NS(exam_status=status),None,NOW)
    assert codes(warnings)==['EXAM_NOT_COMPLETED','READINESS_NOT_CHECKED']
    assert all(w['blocking'] is False and w['message_ar'] and w['message_en'] for w in warnings)

@pytest.mark.parametrize('field,code',[
    ('missing_history','MISSING_HISTORY'),('missing_attachments','MISSING_ATTACHMENTS'),
    ('missing_pacs','MISSING_PACS'),('incomplete_images','INCOMPLETE_IMAGES'),
    ('missing_series','MISSING_SERIES')])
def test_missing_flag_is_specific(field,code):
    r=row(**{field:True});r.status='BLOCKED'
    assert codes(build_warnings(NS(exam_status='REPORTING'),r,NOW))==[code]

def test_stale_and_unknown_status():
    r=row();r.checked_at=NOW-timedelta(seconds=301);r.status='UNKNOWN'
    assert codes(build_warnings(NS(exam_status='REPORTING'),r,NOW))==['READINESS_STALE','READINESS_BLOCKED']

def test_snapshot_failure_stays_nonblocking():
    class Q:
        def filter_by(self,**kw):raise RuntimeError('unavailable')
    warnings=snapshot(NS(CaseReadiness=NS(query=Q())),NS(id=1))
    assert codes(warnings)==['READINESS_UNAVAILABLE']
    assert warnings[0]['blocking'] is False

ENDPOINTS=['api_ohif_report_draft','api_ohif_report_word_draft','api_ohif_onlyoffice_commit_draft','api_reporting_draft']
def harness(endpoint,status=200,ok=True):
    app=Flask(__name__)
    class Q:
        def filter_by(self,**kw):return self
        def first(self):return None
    order=NS(id=7,exam_status='IN_PROGRESS')
    class OQ(Q):
        def first(self):return order
    m=NS(app=app,CaseReadiness=NS(query=Q()),Order=NS(query=OQ()),
         db=NS(session=NS(get=lambda model,key:order)))
    register(m)
    def view(**kw):return jsonify(ok=ok,version_no=5,retry=True),status
    app.add_url_rule('/draft/<accession>' if endpoint=='api_reporting_draft' else '/draft/<int:order_id>',endpoint,view,methods=['GET','POST'])
    return app.test_client()

@pytest.mark.parametrize('endpoint',ENDPOINTS)
def test_success_enrichment_preserves_saved_version(endpoint):
    r=harness(endpoint).post('/draft/7')
    d=r.get_json()
    assert r.status_code==200 and d['ok'] and d['version_no']==5 and d['retry']
    assert codes(d['draft_warnings'])==['EXAM_NOT_COMPLETED','READINESS_NOT_CHECKED']
    assert r.headers['Cache-Control']=='no-store'

@pytest.mark.parametrize('status',[403,409,500])
def test_failed_save_not_changed(status):
    r=harness(ENDPOINTS[0],status,False).post('/draft/7')
    assert r.status_code==status and 'draft_warnings' not in r.get_json()

@pytest.mark.parametrize('endpoint',['verify','finalize'])
def test_other_lifecycle_not_changed(endpoint):
    assert 'draft_warnings' not in harness(endpoint).post('/draft/7').get_json()

def test_get_not_enriched():
    assert 'draft_warnings' not in harness(ENDPOINTS[0]).get('/draft/7').get_json()
