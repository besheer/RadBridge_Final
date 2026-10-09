import json
from datetime import datetime, timedelta
import pytest
import app as m
import assignment_distribution as d
from case_assignment_service import assign_case_atomically, CaseAssignmentServiceError


@pytest.fixture(autouse=True)
def isolated(app_ctx, monkeypatch):
    monkeypatch.setattr(m.db.session,'commit',m.db.session.flush)
    yield
    m.db.session.rollback()
    m.db.session.remove()


def doctor(name, role='RADIOLOGIST'):
    r=m.Role.query.filter_by(code=role).first()
    if not r:
        r=m.Role(code=role,name=role,permissions_json='[]');m.db.session.add(r);m.db.session.flush()
    u=m.User(username=name,full_name=name,password_hash='test',role=r,active=True)
    m.db.session.add(u);m.db.session.flush();return u


def order(name, modality='CT'):
    p=m.Patient(patient_id=name,name='CODEX-UAT DISTRIBUTION')
    m.db.session.add(p);m.db.session.flush()
    o=m.Order(accession=name,patient_id=p.id,modality=modality,procedure='Synthetic',scheduled=datetime.utcnow(),status='IMAGES_RECEIVED',priority='ROUTINE',pacs_image_count=10)
    m.db.session.add(o);m.db.session.flush();return o


def assign(o,u,kind='AUTO_OFFER',now=None):
    return assign_case_atomically(db=m.db,Order=m.Order,User=m.User,CaseAssignment=m.CaseAssignment,Report=m.Report,AssignmentOffer=m.AssignmentOffer,order_id=o.id,doctor_user_id=u.id,assignment_type=kind,now=now).assignment


def save_policy(**values):
    p=d.policy_snapshot();p.update(values)
    row=m.AssignmentDistributionPolicy(id=1,selection_mode=p['selection_mode'],max_active_cases=p['max_active_cases'],reclaim_enabled=p['reclaim_enabled'],urgent_percent=p['urgent_percent'],stat_percent=p['stat_percent'],rules_json=json.dumps(p['rules']),version_no=1)
    m.db.session.add(row);m.db.session.flush();return row


@pytest.mark.parametrize('modality,images,priority,expected',[('DX',1,'ROUTINE',300),('CT',100,'ROUTINE',600),('CT',500,'ROUTINE',900),('MR',200,'ROUTINE',1200),('MR',200,'URGENT',600),('CT',100,'STAT',150)])
def test_modality_image_priority_deadline(modality,images,priority,expected):
    assert d.start_timeout_seconds(d.policy_snapshot(),modality,priority,images)==expected


def test_priority_specific_rule_and_snapshot_are_preserved():
    p=save_policy(rules=d.DEFAULT_RULES+[dict(modality='CT',priority='STAT',min_images=0,minutes=3)])
    u=doctor('dist-snapshot');o=order('DIST-SNAPSHOT');o.priority='STAT'
    a=assign(o,u)
    assert a.start_timeout_seconds==180
    old=a.start_deadline_at
    p.rules_json=json.dumps([dict(modality='*',priority='*',min_images=0,minutes=60)])
    m.db.session.flush()
    assert a.start_deadline_at==old and json.loads(a.distribution_snapshot_json)['rules'][-1]['minutes']==3


def test_manual_never_has_deadline_and_same_owner_manual_override_is_protected():
    u=doctor('dist-manual');o=order('DIST-MANUAL');a=assign(o,u)
    assert a.start_deadline_at is not None
    assign(o,u,'MANUAL')
    assert a.assignment_type=='MANUAL' and a.start_deadline_at is None


def test_capacity_enforced_atomically_and_terminal_cases_excluded():
    save_policy(max_active_cases=1)
    u=doctor('dist-cap');o=order('DIST-CAP1');assign(o,u)
    other=order('DIST-CAP2')
    with pytest.raises(CaseAssignmentServiceError,match='CAPACITY_REACHED'): assign(other,u)
    o.status='FINAL';m.db.session.flush()
    assign(other,u)
    assert d.active_case_count(u.id)==1


def test_pending_offer_reserves_capacity():
    save_policy(max_active_cases=1)
    u=doctor('dist-reserve');o=order('DIST-RESERVE')
    m.db.session.add(m.AssignmentOffer(order_id=o.id,doctor_user_id=u.id,status='PENDING',offered_at=datetime.utcnow(),expires_at=datetime.utcnow()+timedelta(minutes=5)))
    m.db.session.flush()
    assert d.rank_candidates([(u,True,0,100)])==[]


@pytest.mark.parametrize('mode',['LEAST_ACTIVE','ROUND_ROBIN','LONGEST_WAITING'])
def test_fair_order_uses_last_turn(mode):
    save_policy(selection_mode=mode)
    first=doctor('dist-fair-a');second=doctor('dist-fair-b')
    o=order('DIST-FAIR')
    m.db.session.add(m.AssignmentOffer(order_id=o.id,doctor_user_id=first.id,status='REJECTED',offered_at=datetime.utcnow(),expires_at=datetime.utcnow()))
    m.db.session.flush()
    assert d.rank_candidates([(first,True,0,100),(second,True,0,100)])[0].id==second.id


@pytest.mark.parametrize('protection',['manual','started','version','findings','final','verified','lease','returned'])
def test_worker_protects_existing_work(monkeypatch,protection):
    u=doctor('dist-protect');o=order('DIST-PROTECT');a=assign(o,u,'MANUAL' if protection=='manual' else 'AUTO_OFFER',datetime.utcnow()-timedelta(hours=1))
    report=m.Report(order_id=o.id,status='UNREPORTED');m.db.session.add(report);m.db.session.flush()
    if protection=='started': assert d.mark_reading_started(o.id,u.id)
    if protection=='version': m.db.session.add(m.ReportVersion(report_id=report.id,accession=o.accession,version_no=1,action='DRAFT'))
    if protection=='findings': report.findings='Synthetic saved work'
    if protection in ('final','verified'): report.status=protection.upper()
    monkeypatch.setattr(m,'case_return_is_open',lambda oid: protection=='returned')
    import report_edit_control as leases
    monkeypatch.setattr(leases,'get_active_lease',lambda db,oid: object() if protection=='lease' else None)
    monkeypatch.setattr(m,'offer_next_doctor',lambda *args,**kwargs:pytest.fail('Protected case was offered'))
    m.db.session.flush();d.expire_unstarted_assignments()
    assert a.active and o.assigned_doctor_id==u.id


def test_worker_withdraws_only_unstarted_auto_and_excludes_previous_owner(monkeypatch):
    u=doctor('dist-expire');o=order('DIST-EXPIRE');a=assign(o,u,now=datetime.utcnow()-timedelta(hours=1))
    monkeypatch.setattr(m,'case_return_is_open',lambda oid:False)
    monkeypatch.setattr(m,'create_ris_notification',lambda *args:None)
    called=[]
    monkeypatch.setattr(m,'offer_next_doctor',lambda order:called.append(order.id))
    assert d.expire_unstarted_assignments()['withdrawn']==1
    assert not a.active and o.assigned_doctor_id is None and called==[o.id]
    assert m.AssignmentOffer.query.filter_by(order_id=o.id,doctor_user_id=u.id,status='START_TIMEOUT').count()==1
    assert m.AuditLog.query.filter_by(action='CASE_START_TIMEOUT',entity_id=str(o.id)).count()==1
    assert d.expire_unstarted_assignments()['withdrawn']==0


def test_global_off_switch_pauses_existing_deadlines(monkeypatch):
    u=doctor('dist-pause');o=order('DIST-PAUSE');a=assign(o,u,now=datetime.utcnow()-timedelta(hours=1))
    save_policy(reclaim_enabled=False)
    assert d.expire_unstarted_assignments()['withdrawn']==0 and a.active


@pytest.mark.parametrize('role',['RECEPTION','TECHNICIAN','NURSE','FINANCE','RADIOLOGIST','CASE_COORDINATOR'])
def test_settings_denied_to_non_admin_even_with_assignment_permission(monkeypatch,role):
    u=doctor('dist-role-'+role,role)
    monkeypatch.setattr(m,'current_user',lambda:u)
    monkeypatch.setattr(m,'has_perm',lambda *args:True)
    with m.app.test_client() as c:
        assert c.get('/admin/assignment-distribution').status_code==403


def test_admin_settings_validate_audit_and_reject_stale_form(monkeypatch):
    u=doctor('dist-admin','SUPER_ADMIN')
    monkeypatch.setattr(m,'current_user',lambda:u);monkeypatch.setattr(m,'has_perm',lambda *args:True)
    data=dict(version_no='0',selection_mode='ROUND_ROBIN',max_active_cases='5',urgent_percent='50',stat_percent='25',reclaim_enabled='1',rule_modality='*',rule_priority='*',rule_min_images='0',rule_minutes='10')
    with m.app.test_client() as c:
        assert c.post('/admin/assignment-distribution',data=data).status_code==302
        assert d.policy_snapshot()['selection_mode']=='ROUND_ROBIN'
        assert m.AuditLog.query.filter_by(action='ASSIGNMENT_DISTRIBUTION_SAVE').count()==1
        assert c.post('/admin/assignment-distribution',data=data).status_code==422
        data['version_no']='1';data['rule_minutes']='0'
        assert c.post('/admin/assignment-distribution',data=data).status_code==422


def test_start_reading_denies_other_doctor(monkeypatch):
    owner=doctor('dist-owner');other=doctor('dist-other');o=order('DIST-OWNER');assign(o,owner)
    monkeypatch.setattr(m,'current_user',lambda:other);monkeypatch.setattr(m,'has_perm',lambda *args:True)
    with m.app.test_client() as c:
        assert c.post(f'/doctor/cases/{o.id}/start-reading').status_code==403


def test_strategy_auto_summary_fits_database_column():
    assert len(m._strategy_change_summary({}, {key:'x'*200 for key in ('name','procedure_pattern','modality','assignment_mode')}))<=500
