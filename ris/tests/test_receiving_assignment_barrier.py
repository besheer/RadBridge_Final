import json
from uuid import uuid4
from datetime import datetime,timedelta
from unittest.mock import Mock
import pytest
from test_case_assignment_service import _doctor,_order,_assign,clean_assignment_rows
from case_assignment_service import CaseAssignmentServiceError,accept_offer_atomically
import app as m

@pytest.fixture
def receiving_case(app_ctx):
    tag=uuid4().hex
    doctor=_doctor('receiving-doctor-'+tag)
    order=_order('SYN-RECEIVING-'+tag)
    order.exam_status='EXAM_COMPLETED';order.pacs_status='RECEIVING';order.pacs_image_count=50
    row=m.CaseReadiness(order_id=order.id,status='READY',score=100,image_count=50,details_json='{"blockers":[]}',checked_at=datetime.utcnow())
    m.db.session.add(row);m.db.session.flush()
    return order,doctor,row

@pytest.mark.parametrize('kind',['MANUAL','AUTO_OFFER','OPEN_POOL','DIRECT_ASSIGN','AUTO'])
def test_atomic_assignment_cannot_bypass_receiving(receiving_case,kind):
    o,d,row=receiving_case
    with pytest.raises(CaseAssignmentServiceError) as caught:_assign(o,d,assignment_type=kind)
    assert caught.value.code=='PACS_RECEIVING'
    assert o.assigned_doctor_id is None
    assert m.CaseAssignment.query.filter_by(order_id=o.id).count()==0
    assert row.status=='READY' # Reading the barrier did not mutate cached evidence.

def test_pending_offer_is_not_accepted_after_reception_resumes(receiving_case):
    o,d,row=receiving_case
    offer=m.AssignmentOffer(order_id=o.id,doctor_user_id=d.id,status='PENDING',expires_at=datetime.utcnow()+timedelta(minutes=10))
    m.db.session.add(offer);m.db.session.flush()
    with pytest.raises(CaseAssignmentServiceError) as caught:
        accept_offer_atomically(db=m.db,Order=m.Order,User=m.User,CaseAssignment=m.CaseAssignment,Report=m.Report,AssignmentOffer=m.AssignmentOffer,offer_id=offer.id,actor_user_id=d.id)
    assert caught.value.code=='PACS_RECEIVING'
    assert offer.status=='PENDING' and o.assigned_doctor_id is None

def test_readiness_decision_blocks_stale_ready_without_pacs_or_strategy_bypass(receiving_case,monkeypatch):
    o,d,row=receiving_case
    monkeypatch.setattr(m,'evaluate_case_readiness',lambda *a:pytest.fail('Known reception must block without external I/O'))
    monkeypatch.setattr(m,'assignment_strategy_for_order',lambda *a:pytest.fail('ALLOW strategy must not bypass reception'))
    result=m.assignment_readiness_decision(o)
    assert not result['allowed'] and result['action']=='BLOCK' and 'PACS_RECEIVING' in result['blockers']
    assert result['readiness'].status=='BLOCKED' and row.status=='READY'
    assert 'PACS_RECEIVING' in json.loads(result['readiness'].details_json)['blockers']

def test_readiness_recheck_persists_block_even_with_sufficient_images(receiving_case,monkeypatch):
    o,d,row=receiving_case
    monkeypatch.setattr(m,'quality_rule_for',lambda order:None)
    monkeypatch.setattr(m,'_order_history_present',lambda order:True)
    monkeypatch.setattr(m,'_order_attachment_count',lambda order:1)
    import exam_type_policy
    monkeypatch.setattr(exam_type_policy,'evidence_exam_match',lambda *a:{'allowed':True,'status':'MATCHED'})
    refreshed=m.evaluate_case_readiness(o,pacs_evidence=(50,{'synthetic':True},'',[]))
    assert refreshed.status=='BLOCKED' and refreshed.incomplete_images and refreshed.score==0
    assert 'PACS_RECEIVING' in json.loads(refreshed.details_json)['blockers']

def test_existing_pending_offer_not_returned_as_assignable_while_receiving(receiving_case):
    o,d,row=receiving_case
    offer=m.AssignmentOffer(order_id=o.id,doctor_user_id=d.id,status='PENDING',expires_at=datetime.utcnow()+timedelta(minutes=10))
    m.db.session.add(offer);m.db.session.flush()
    returned,reason=m.offer_next_doctor(o)
    assert returned is None and reason=='PACS_RECEIVING'
    assert offer.status=='PENDING' and o.assigned_doctor_id is None

def test_barrier_releases_only_its_own_block_after_reception_completes(receiving_case,monkeypatch):
    o,d,row=receiving_case;o.pacs_status='IMAGES_COMPLETE'
    import exam_type_policy
    monkeypatch.setattr(exam_type_policy,'cached_exam_gate',lambda *a:(True,'MATCHED'))
    monkeypatch.setattr(m,'assignment_strategy_for_order',lambda order:None)
    assert m.assignment_readiness_decision(o,refresh_stale=False)['allowed']
    row.status='BLOCKED';row.missing_history=True
    assert not m.assignment_readiness_decision(o,refresh_stale=False)['allowed']
