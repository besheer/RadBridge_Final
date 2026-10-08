import pytest
from datetime import datetime,timedelta
from types import SimpleNamespace
from unittest.mock import Mock
import workflow_engine as w

@pytest.mark.parametrize('state',['EXAM_COMPLETED','REPORTING',' reporting '])
def test_completed_acquisition_and_legacy_reporting(state):
    assert w.acquisition_completed(state)

@pytest.mark.parametrize('state',[None,'ORDERED','BOOKED','IN_PROGRESS','FINAL','VERIFIED','CANCELLED','UNKNOWN'])
def test_report_final_or_unknown_does_not_prove_acquisition(state):
    assert not w.acquisition_completed(state)

@pytest.fixture
def reception(app_ctx,monkeypatch):
    m=app_ctx
    monkeypatch.setattr(m.requests,'post',lambda *a,**k:SimpleNamespace(raise_for_status=lambda:None,json=lambda:[{'ID':'a'*40,'Statistics':{'CountInstances':1}}]))
    return m

@pytest.mark.parametrize('state',['EXAM_COMPLETED','REPORTING'])
@pytest.mark.parametrize('report_final',[False,True])
def test_stable_images_completed_after_reporting(reception,state,report_final):
    m=reception
    o=SimpleNamespace(accession='SYNTHETIC-ACQUISITION',exam_status=state,status='FINAL' if report_final else 'REPORTING',pacs_image_count=1,pacs_study_id='a'*40,pacs_last_change_at=datetime.utcnow()-timedelta(seconds=m.PACS_IMAGES_STABLE_SECONDS+20))
    result=m.pacs_lookup_order(o)
    assert result['status']=='IMAGES_COMPLETE' and o.pacs_status=='IMAGES_COMPLETE'
    assert o.exam_status==state and o.status==('FINAL' if report_final else 'REPORTING')

@pytest.mark.parametrize('state',['ORDERED','IN_PROGRESS','FINAL'])
def test_final_order_cannot_bypass_uncompleted_acquisition(reception,state):
    m=reception
    o=SimpleNamespace(accession='SYNTHETIC-ACQUISITION',exam_status=state,status='FINAL',pacs_image_count=1,pacs_study_id='a'*40,pacs_last_change_at=datetime.utcnow()-timedelta(days=2))
    assert m.pacs_lookup_order(o)['status']=='RECEIVING'

@pytest.mark.parametrize('change',['fresh','changed','missing_timestamp'])
def test_additional_images_or_missing_stability_evidence_still_receiving(reception,change):
    m=reception
    o=SimpleNamespace(accession='SYNTHETIC-ACQUISITION',exam_status='REPORTING',status='FINAL',pacs_image_count=0 if change=='changed' else 1,pacs_study_id='a'*40,pacs_last_change_at=None if change=='missing_timestamp' else datetime.utcnow()-timedelta(seconds=1 if change=='fresh' else m.PACS_IMAGES_STABLE_SECONDS+10))
    assert m.pacs_lookup_order(o)['status']=='RECEIVING'
    assert o.status=='FINAL'

def test_start_reporting_preserves_acquisition_and_completion_time(app_ctx,monkeypatch):
    m=app_ctx;now=datetime.utcnow()
    monkeypatch.setattr(m,'pacs_demographic_gate',lambda order:(True,'AUTO_SAFE'))
    audit=Mock();monkeypatch.setattr(m,'audit',audit)
    o=SimpleNamespace(id=999,exam_status='EXAM_COMPLETED',status='IMAGES_RECEIVED',exam_completed_at=now)
    decision,previous=m._apply_exam_transition(o,'REPORTING','RADIOLOGIST')
    assert decision.allowed and previous=='EXAM_COMPLETED'
    assert o.exam_status=='EXAM_COMPLETED' and o.status=='REPORTING' and o.exam_completed_at==now
    assert audit.call_args.args[0]=='ACQUISITION_PRESERVED_FOR_REPORTING'

@pytest.mark.parametrize('boundary',['wrong_role','uncompleted','final','identity'])
def test_start_reporting_keeps_existing_guards(app_ctx,monkeypatch,boundary):
    m=app_ctx
    monkeypatch.setattr(m,'pacs_demographic_gate',lambda order:(boundary!='identity','REVIEW'))
    audit=Mock();monkeypatch.setattr(m,'audit',audit)
    role='TECHNICIAN' if boundary=='wrong_role' else 'RADIOLOGIST'
    o=SimpleNamespace(id=999,exam_status='IN_PROGRESS' if boundary=='uncompleted' else 'EXAM_COMPLETED',status='FINAL' if boundary=='final' else 'IMAGES_RECEIVED')
    before=(o.exam_status,o.status)
    decision,previous=m._apply_exam_transition(o,'REPORTING',role)
    assert not decision.allowed and (o.exam_status,o.status)==before
    audit.assert_not_called()
