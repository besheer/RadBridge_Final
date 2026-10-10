import json,threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timedelta
from pathlib import Path
import app as m
import assignment_distribution as d
import assignment_visit_grouping as v
from case_assignment_service import assign_case_atomically,accept_offer_atomically
from report_edit_control import acquire_or_renew_lease,release_lease

with m.app.app_context():
    assert m.db.engine.url.database=='radbridge_assignment_uat_20261003'
    m.db.create_all()
    # Explicit migration must also be safe when applied twice to a complete schema.
    sql=(Path(__file__).resolve().parents[1] / 'migrations/sql/20261003_assignment_distribution.sql').read_text(encoding='utf-8')
    with m.db.engine.begin() as c:
        c.exec_driver_sql(sql);c.exec_driver_sql(sql)
    role=m.Role(code='RADIOLOGIST',name='Synthetic Doctor',permissions_json='["reports.view","reports.edit"]')
    adminrole=m.Role(code='SUPER_ADMIN',name='Synthetic Admin',permissions_json='["*"]')
    m.db.session.add_all([role,adminrole]);m.db.session.flush()
    doctors=[m.User(username='CODEX-UAT-PG-'+str(i),full_name='CODEX-UAT PG Doctor',password_hash='test',active=True,role=role) for i in range(2)]
    admin=m.User(username='CODEX-UAT-PG-ADMIN',full_name='CODEX-UAT Admin',password_hash='test',active=True,role=adminrole)
    p=m.Patient(patient_id='CODEX-UAT-PG',name='CODEX-UAT SYNTHETIC')
    m.db.session.add_all(doctors+[admin,p]);m.db.session.flush()
    p_id=p.id;doctor_ids=[u.id for u in doctors];admin_id=admin.id
    policy=m.AssignmentDistributionPolicy(id=1,selection_mode='LEAST_ACTIVE',max_active_cases=1,reclaim_enabled=True,urgent_percent=50,stat_percent=25,rules_json=json.dumps(d.DEFAULT_RULES),special_rules_json='[]',version_no=1)
    m.db.session.add(policy);m.db.session.commit()


def make_order(label,modality='CT',visit=None):
    o=m.Order(accession='CODEX-UAT-'+label,patient_id=p_id,modality=modality,procedure='Synthetic',scheduled=datetime.utcnow(),status='IMAGES_RECEIVED',exam_status='EXAM_COMPLETED',pacs_status='IMAGES_COMPLETE',priority='ROUTINE',pacs_image_count=10,assignment_visit_id=visit)
    m.db.session.add(o);m.db.session.flush();return o


def parallel(functions):
    barrier=threading.Barrier(len(functions))
    def execute(f):
        with m.app.app_context():
            barrier.wait(timeout=10)
            try:
                result=f();m.db.session.commit();return result
            except Exception as e:
                m.db.session.rollback();return getattr(e,'code',type(e).__name__)
            finally:m.db.session.remove()
    with ThreadPoolExecutor(max_workers=len(functions)) as pool:
        return list(pool.map(execute,functions))


def assign(oid,uid,kind='AUTO_OFFER',now=None):
    return assign_case_atomically(db=m.db,Order=m.Order,User=m.User,CaseAssignment=m.CaseAssignment,Report=m.Report,AssignmentOffer=m.AssignmentOffer,order_id=oid,doctor_user_id=uid,assignment_type=kind,now=now)


results={}
with m.app.app_context():
    o1=make_order('CAP1');o2=make_order('CAP2');ids=[o1.id,o2.id];m.db.session.commit()
cap=parallel([lambda oid=oid: (assign(oid,doctor_ids[0]),'ASSIGNED')[1] for oid in ids])
assert sorted(cap)==['ASSIGNED','ASSIGNMENT_DOCTOR_CAPACITY_REACHED'],cap
results['concurrent_capacity']=cap

with m.app.app_context():
    # Remove test capacity pressure by ending only these synthetic orders.
    for o in m.Order.query.all():o.status='FINAL'
    m.db.session.get(m.AssignmentDistributionPolicy,1).max_active_cases=10
    vid=v.create_visit(p_id,None,datetime.utcnow())
    members=[make_order('VISIT-'+mod,mod,vid) for mod in ('MR','CT','DX')]
    group_ids=[o.id for o in members]
    now=datetime.utcnow()
    offers=[m.AssignmentOffer(order_id=members[0].id,doctor_user_id=uid,status='PENDING',offered_at=now,expires_at=now+timedelta(minutes=5)) for uid in doctor_ids]
    m.db.session.add_all(offers);m.db.session.flush();offer_ids=[o.id for o in offers];m.db.session.commit()

m.assignment_readiness_decision=lambda order:dict(allowed=True)
def accept(offer_id,uid):
    accept_offer_atomically(db=m.db,Order=m.Order,User=m.User,CaseAssignment=m.CaseAssignment,Report=m.Report,AssignmentOffer=m.AssignmentOffer,offer_id=offer_id,actor_user_id=uid)
    return 'ACCEPTED'
accepted=parallel([lambda i=i:accept(offer_ids[i],doctor_ids[i]) for i in range(2)])
assert accepted.count('ACCEPTED')==1,accepted
with m.app.app_context():
    owners={m.db.session.get(m.Order,oid).assigned_doctor_id for oid in group_ids}
    assert len(owners)==1 and None not in owners
    owner=next(iter(owners));results['concurrent_group_acceptance']=accepted
    assignments=m.CaseAssignment.query.filter(m.CaseAssignment.order_id.in_(group_ids),m.CaseAssignment.active.is_(True)).all()
    assert len({a.start_deadline_at for a in assignments})==1
    for a in assignments:a.start_deadline_at=datetime.utcnow()-timedelta(minutes=1)
    report=m.Report(order_id=group_ids[1],status='UNREPORTED');m.db.session.add(report);m.db.session.commit()

# If start wins, all members stay owned. If timeout wins, none stay owned.
# Use a local next-offer stub to observe the atomic release without notifications
# escaping the isolated database.
m.offer_next_doctor=lambda order:m.db.session.commit()
def start():return 'STARTED' if d.mark_reading_started(group_ids[1],owner) else 'NO_LONGER_OWNED'
def expire():return d.expire_unstarted_assignments()
race=parallel([start,expire])
with m.app.app_context():
    owners=[m.db.session.get(m.Order,oid).assigned_doctor_id for oid in group_ids]
    assert owners==[owner]*3 or owners==[None]*3,owners
    if 'STARTED' in race: assert owners==[owner]*3
results['start_timeout_race_atomic']=True

# Real PostgreSQL editing lease protects the complete visit and stale owners fail.
with m.app.app_context():
    vid=v.create_visit(p_id,None,datetime.utcnow())
    members=[make_order('LEASE-'+mod,mod,vid) for mod in ('MR','CT','DX')]
    oid=members[0].id
    v.assign_visit_atomically(db=m.db,Order=m.Order,User=m.User,CaseAssignment=m.CaseAssignment,Report=m.Report,AssignmentOffer=m.AssignmentOffer,order_id=oid,doctor_user_id=doctor_ids[1],assignment_type='AUTO_OFFER',now=datetime.utcnow()-timedelta(hours=1))
    report=m.Report(order_id=oid,status='UNREPORTED');m.db.session.add(report);m.db.session.flush()
    u=m.db.session.get(m.User,doctor_ids[1])
    lease=acquire_or_renew_lease(db=m.db,order=members[0],report=report,user=u,editor_type='ONLYOFFICE',lease_token='CODEX-UAT-SYNTHETIC-LEASE')
    m.db.session.commit()
    assert all(a.reading_started_at for a in m.CaseAssignment.query.filter(m.CaseAssignment.order_id.in_([o.id for o in members])).all())
    release_lease(db=m.db,order_id=oid,user_id=u.id,lease_token='CODEX-UAT-SYNTHETIC-LEASE');m.db.session.commit()
    d.expire_unstarted_assignments()
    assert all(o.assigned_doctor_id==u.id for o in members)
    results['real_edit_lease_protects_visit_after_release']=True

with m.app.app_context(),m.app.test_request_context('/'):
    admin=m.db.session.get(m.User,admin_id)
    m.current_user=lambda:admin;m.has_perm=lambda *args:True
    with m.app.test_client() as client:
        assert client.get('/admin/assignment-distribution').status_code==200
        assert client.get('/admin/assignment-visits?order_id='+str(oid)).status_code==200
    results['admin_templates_and_uuid_lookup']=True

print(json.dumps(dict(result='PASS',**results)))
