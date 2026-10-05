import json
from datetime import datetime
from uuid import uuid4
from types import SimpleNamespace
import pytest
from exam_type_policy import cached_exam_gate,evidence_exam_match

@pytest.fixture
def acquisition(app_ctx,monkeypatch):
    m=app_ctx;key='TYPEUAT'+uuid4().hex[:8]
    patient=m.Patient(patient_id=key,name='CODEX UAT TYPE TEST')
    m.db.session.add(patient);m.db.session.flush()
    order=m.Order(patient_id=patient.id,accession=key,procedure='MRI Knee',modality='MR',scheduled=datetime.utcnow(),
        status='IN_PROGRESS',exam_status='IN_PROGRESS',pacs_status='RECEIVING',pacs_study_id=key,pacs_image_count=10)
    m.db.session.add(order);m.db.session.commit()
    rule=SimpleNamespace(id=None,min_images=1,warning_images=0,required_series='',require_pacs_study=True,require_history=False,require_attachments=False)
    evidence=(10,{'orthanc_study_id':key},'',[{'body_part':'CSPINE','modality':'MR','instance_count':10}])
    monkeypatch.setattr(m,'quality_rule_for',lambda o:rule)
    monkeypatch.setattr(m,'pacs_readiness_evidence',lambda o:evidence)
    monkeypatch.setattr(m,'pacs_demographic_gate',lambda o:(True,'AUTO_SAFE'))
    monkeypatch.setattr(m,'_order_history_present',lambda o:True)
    monkeypatch.setattr(m,'_order_attachment_count',lambda o:0)
    return SimpleNamespace(m=m,order=order,rule=rule,evidence=evidence)

def test_technician_completion_blocks_wrong_region_with_matching_identity(acquisition):
    f=acquisition
    result,_=f.m.technician_completion_evidence(f.order)
    assert not result['allowed'] and result['identity_verified']
    assert result['exam_type']['observed_regions']==['CSPINE']
    assert f.order.exam_status=='IN_PROGRESS'

def test_readiness_and_assignment_strategy_cannot_warn_past_mismatch(acquisition,monkeypatch):
    f=acquisition
    row=f.m.evaluate_case_readiness(f.order)
    assert row.status=='BLOCKED'
    # Hard guard runs before any permissive assignment strategy.
    monkeypatch.setattr(f.m,'assignment_strategy_for_order',lambda o:pytest.fail('Mismatch must precede strategy'))
    decision=f.m.assignment_readiness_decision(f.order)
    assert not decision['allowed'] and 'EXAM_METADATA_MISMATCH' in decision['blockers']

def test_matching_acquisition_is_ready(acquisition):
    f=acquisition;f.evidence[3][0]['body_part']='KNEE'
    row=f.m.evaluate_case_readiness(f.order)
    assert row.status=='READY'
    assert f.m.technician_completion_evidence(f.order)[0]['allowed']

def test_configured_recognized_exam_missing_region_requires_review(acquisition):
    f=acquisition;f.evidence[3][0]['body_part']=''
    result=f.m.technician_completion_evidence(f.order)[0]
    assert not result['allowed'] and result['exam_type']['status']=='REVIEW_REQUIRED'

def test_missing_policy_warns_but_never_authorizes_clear_conflict(acquisition,monkeypatch):
    f=acquisition;monkeypatch.setattr(f.m,'quality_rule_for',lambda o:None)
    assert not f.m.technician_completion_evidence(f.order)[0]['allowed']
    f.evidence[3][0]['body_part']=''
    result=f.m.technician_completion_evidence(f.order)[0]
    assert result['allowed'] and result['warning'] and result['exam_type']['status']=='REVIEW_REQUIRED'

def test_cached_inputs_changed_require_recheck(acquisition):
    f=acquisition;f.evidence[3][0]['body_part']='KNEE'
    row=f.m.evaluate_case_readiness(f.order)
    assert cached_exam_gate(f.order,row)[0]
    f.order.procedure='MRI Brain'
    assert cached_exam_gate(f.order,row)==(False,'EXAM_METADATA_RECHECK_REQUIRED')

def test_demographic_manual_confirmation_does_not_override_wrong_exam(acquisition,monkeypatch):
    f=acquisition;m=f.m
    m.evaluate_case_readiness(f.order)
    # Restore central gate after the fixture's identity stub.
    monkeypatch.undo()
    m.db.session.add(m.PacsStudyMatch(order_id=f.order.id,orthanc_study_id=f.order.pacs_study_id,
        confidence='CONFIRMED',match_method='MANUAL_CONFIRMED'))
    m.db.session.commit()
    assert m.pacs_demographic_gate(f.order)==(False,'EXAM_METADATA_MISMATCH')

def test_cached_bad_json_fails_closed(acquisition):
    f=acquisition
    assert cached_exam_gate(f.order,SimpleNamespace(details_json='{bad'))==(False,'EXAM_METADATA_RECHECK_REQUIRED')
