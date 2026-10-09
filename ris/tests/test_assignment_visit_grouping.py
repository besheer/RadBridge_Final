import json
from datetime import datetime,timedelta
import pytest
import app as m
import assignment_distribution as d
import assignment_visit_grouping as v
from case_assignment_service import CaseAssignmentServiceError,accept_offer_atomically
from test_assignment_distribution import doctor,order,save_policy,assign


@pytest.fixture(autouse=True)
def isolated(app_ctx,monkeypatch):
    monkeypatch.setattr(m.db.session,'commit',m.db.session.flush)
    yield
    m.db.session.rollback();m.db.session.remove()


def group(prefix='GROUP'):
    first=order(prefix+'-MR','MR')
    vid=v.create_visit(first.patient_id,first.branch_id,first.scheduled)
    members=[first]
    for modality in ['CT','DX']:
        o=m.Order(accession=prefix+'-'+modality,patient_id=first.patient_id,modality=modality,procedure='Synthetic '+modality,scheduled=first.scheduled,status='IMAGES_RECEIVED',priority='ROUTINE',pacs_image_count=10)
        m.db.session.add(o);members.append(o)
    for o in members:
        o.assignment_visit_id=vid;o.exam_status='EXAM_COMPLETED';o.pacs_status='IMAGES_COMPLETE'
    m.db.session.flush();return members


def assign_group(members,u,kind='AUTO_OFFER',now=None):
    return v.assign_visit_atomically(db=m.db,Order=m.Order,User=m.User,CaseAssignment=m.CaseAssignment,Report=m.Report,AssignmentOffer=m.AssignmentOffer,order_id=members[0].id,doctor_user_id=u.id,assignment_type=kind,now=now)


def ready(monkeypatch):
    monkeypatch.setattr(m,'assignment_readiness_decision',lambda order:dict(allowed=True))


def test_single_offer_accepts_entire_visit_and_snapshots_longest_deadline(monkeypatch):
    ready(monkeypatch);members=group();u=doctor('visit-full')
    now=datetime.utcnow();offer=m.AssignmentOffer(order_id=members[0].id,doctor_user_id=u.id,status='PENDING',offered_at=now,expires_at=now+timedelta(minutes=5))
    m.db.session.add(offer);m.db.session.flush()
    result,offer=accept_offer_atomically(db=m.db,Order=m.Order,User=m.User,CaseAssignment=m.CaseAssignment,Report=m.Report,AssignmentOffer=m.AssignmentOffer,offer_id=offer.id,actor_user_id=u.id,now=now)
    assert all(o.assigned_doctor_id==u.id for o in members)
    assignments=m.CaseAssignment.query.filter_by(active=True).all()
    assert len(assignments)==3 and len({a.start_deadline_at for a in assignments})==1
    assert all(a.start_timeout_seconds==1200 for a in assignments)


def test_unqualified_for_one_exam_excluded_from_entire_visit(monkeypatch):
    ready(monkeypatch);members=group();mr=doctor('visit-mr-only');all_doctor=doctor('visit-all')
    m.db.session.add(m.DoctorAssignmentProfile(user_id=mr.id,modalities='MR',available=True,auto_assign=True,max_active_cases=20))
    m.db.session.flush()
    assert v.prefer_visit_doctor(members[0],[mr,all_doctor])==[all_doctor]
    with pytest.raises(CaseAssignmentServiceError,match='NOT_QUALIFIED_FOR_ALL'): assign_group(members,mr)
    assert all(o.assigned_doctor_id is None for o in members)


def test_capacity_must_cover_entire_group(monkeypatch):
    ready(monkeypatch);save_policy(max_active_cases=2);members=group();u=doctor('visit-cap')
    assert v.prefer_visit_doctor(members[0],[u])==[]
    with pytest.raises(CaseAssignmentServiceError,match='CAPACITY_REACHED'):assign_group(members,u)
    assert m.CaseAssignment.query.count()==0


def test_same_patient_different_visit_does_not_join():
    members=group();other=order('GROUP-OTHER');other.patient_id=members[0].patient_id
    other.assignment_visit_id=v.create_visit(other.patient_id,None,other.scheduled)
    m.db.session.flush()
    assert len(v.group_members(other))==1 and len(v.group_members(members[0]))==3


def test_no_offer_until_all_examinations_ready(monkeypatch):
    ready(monkeypatch);members=group();members[2].exam_status='ORDERED';m.db.session.flush()
    assert v.visit_ready_for_offer(members[0])[1]=='VISIT_EXAMS_NOT_COMPLETE'


def test_final_member_blocks_whole_assignment(monkeypatch):
    ready(monkeypatch);members=group();u=doctor('visit-final')
    m.db.session.add(m.Report(order_id=members[2].id,status='FINAL'));m.db.session.flush()
    with pytest.raises(CaseAssignmentServiceError,match='REPORT_LOCKED'):assign_group(members,u)
    assert all(o.assigned_doctor_id is None for o in members)


def test_starting_one_exam_protects_entire_group(monkeypatch):
    ready(monkeypatch);members=group();u=doctor('visit-start');assign_group(members,u,now=datetime.utcnow()-timedelta(hours=1))
    assert d.mark_reading_started(members[1].id,u.id)
    assert all(a.reading_started_at for a in m.CaseAssignment.query.all())
    assert d.expire_unstarted_assignments()['withdrawn']==0


def test_saved_content_on_one_member_protects_entire_group(monkeypatch):
    ready(monkeypatch);members=group();u=doctor('visit-content');assign_group(members,u,now=datetime.utcnow()-timedelta(hours=1))
    m.db.session.add(m.Report(order_id=members[2].id,status='DRAFT',findings='CODEX-UAT work'));m.db.session.flush()
    assert d.expire_unstarted_assignments()['withdrawn']==0
    assert all(o.assigned_doctor_id==u.id for o in members)


def test_timeout_withdraws_entire_visit_and_offers_anchor_once(monkeypatch):
    ready(monkeypatch);members=group();u=doctor('visit-expired');assign_group(members,u,now=datetime.utcnow()-timedelta(hours=1))
    calls=[];monkeypatch.setattr(m,'offer_next_doctor',lambda order:calls.append(order.id))
    assert d.expire_unstarted_assignments()['withdrawn']==1
    assert all(o.assigned_doctor_id is None for o in members)
    assert calls==[members[0].id]
    assert m.AssignmentOffer.query.filter_by(status='START_TIMEOUT').count()==3


def test_special_pools_intersect_across_entire_group(monkeypatch):
    ready(monkeypatch);members=group();regular=doctor('visit-regular');special=doctor('visit-special')
    p=save_policy();p.special_rules_json=json.dumps([dict(code='FISTULA',label='Special technique',priority='*',procedure_pattern='Fistula',enabled=True,doctor_ids=[special.id])])
    members[1].procedure='Fistula Synthetic';m.db.session.flush()
    candidates=d.rank_candidates([(regular,True,0,100),(special,True,0,100)],order=members[0])
    assert candidates==[special]
    with pytest.raises(CaseAssignmentServiceError,match='SPECIAL_CASE'):assign_group(members,regular)


def test_emergency_priority_uses_configured_doctor_pool():
    regular=doctor('emergency-regular');special=doctor('emergency-special');o=order('EMERGENCY');o.priority='STAT'
    p=save_policy();p.special_rules_json=json.dumps([dict(code='EMERGENCY',label='Emergency',priority='STAT',procedure_pattern='',enabled=True,doctor_ids=[special.id])]);m.db.session.flush()
    assert d.rank_candidates([(regular,True,0,100),(special,True,0,100)],order=o)==[special]


def test_explicit_special_tag_with_disabled_rule_fails_closed():
    o=order('SPECIAL-TAG');o.assignment_special_code='FISTULA';m.db.session.flush()
    assert d.special_doctor_pool(o)==set()


def test_mismatched_patient_visit_fails_closed():
    members=group();other=order('OTHER-PATIENT');other.assignment_visit_id=members[0].assignment_visit_id;m.db.session.flush()
    with pytest.raises(ValueError,match='MISMATCH'):v.group_members(members[0])


def test_offer_group_metadata_is_explicit():
    members=group();summary=m.assignment_visit_summary(members[0])
    assert summary['linked_visit'] and summary['visit_exam_count']==3
    assert {x['modality'] for x in summary['visit_examinations']}=={'MR','CT','DX'}
