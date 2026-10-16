from datetime import datetime, timedelta
import pytest
import app as m
from assignment_monitor import snapshot
from test_assignment_distribution import doctor, order, assign


@pytest.fixture(autouse=True)
def isolated(app_ctx, monkeypatch):
    monkeypatch.setattr(m.db.session, 'commit', m.db.session.flush)
    yield
    m.db.session.rollback(); m.db.session.remove()


def test_monitor_is_read_only_and_unknown_presence_is_offline():
    u = doctor('monitor-unknown')
    before = m.DoctorAvailabilityState.query.count()
    row = next(r for r in snapshot()['doctors'] if r['doctor'].id == u.id)
    assert not row['online'] and row['state'] == 'UNKNOWN'
    assert m.DoctorAvailabilityState.query.count() == before
    assert m.AssignmentDistributionPolicy.query.count() == 0


def test_monitor_manual_started_and_finished_cases():
    now = datetime.utcnow(); u = doctor('monitor-owned')
    manual = order('MONITOR-MANUAL'); assign(manual, u, 'MANUAL')
    late = order('MONITOR-LATE'); assign(late, u, now=now-timedelta(hours=1))
    started = order('MONITOR-STARTED'); a = assign(started, u, now=now-timedelta(hours=1)); a.reading_started_at = now
    done = order('MONITOR-DONE'); assign(done, u); done.status = 'FINAL'
    m.db.session.flush()
    result = snapshot(now); row = next(r for r in result['doctors'] if r['doctor'].id == u.id)
    assert row['active'] == 3
    assert [c['order'].id for c in result['overdue']] == [late.id]
    assert next(c for c in result['cases'] if c['order'].id == manual.id)['manual']
    assert next(c for c in result['cases'] if c['order'].id == started.id)['deadline'] is None


def test_linked_offer_reserves_every_examination():
    from test_assignment_visit_grouping import group
    u = doctor('monitor-group'); members = group('MONITOR-GROUP'); now = datetime.utcnow()
    m.db.session.add(m.AssignmentOffer(order_id=members[0].id, doctor_user_id=u.id,
        status='PENDING', offered_at=now, expires_at=now+timedelta(minutes=5)))
    m.db.session.flush()
    result = snapshot(now); row = next(r for r in result['doctors'] if r['doctor'].id == u.id)
    assert row['reserved'] == 3 and len(result['waiting']) == 3
    assert all(c['linked'] and c['visit_count'] == 3 for c in result['waiting'])


@pytest.mark.parametrize('path', ['/admin/assignment-monitor', '/coordinator/assignments'])
def test_monitor_requires_assignment_permission(path):
    u = doctor('monitor-denied')
    client = m.app.test_client()
    with client.session_transaction() as s: s['uid'] = u.id
    assert client.get(path).status_code == 403


@pytest.mark.parametrize('path', ['/admin/assignment-monitor', '/coordinator/assignments'])
def test_monitor_renders_for_authorized_admin(path, monkeypatch):
    u = doctor('monitor-admin', 'SUPER_ADMIN')
    monkeypatch.setattr('application.legacy_runtime.resolve_runtime',
                        lambda: pytest.fail('monitor route resolved the global runtime'))
    client = m.app.test_client()
    with client.session_transaction() as s: s['uid'] = u.id
    response = client.get(path)
    assert response.status_code == 200
    assert b'monitor-admin' in response.data


def test_report_coordinator_can_monitor_but_cannot_assign():
    import json
    branch = m.Branch(code='MONITOR-COORD', name='Monitor coordinator branch')
    m.db.session.add(branch); m.db.session.flush()
    u=doctor('monitor-readonly-coordinator','COORDINATOR')
    u.role.permissions_json=json.dumps(['reports.coordinate'])
    u.branch_id=branch.id
    waiting=order('MONITOR-READONLY');waiting.branch_id=branch.id;m.db.session.flush()
    client=m.app.test_client()
    with client.session_transaction() as s:s['uid']=u.id
    response=client.get('/coordinator/assignments')
    assert response.status_code==200
    assert b'MONITOR-READONLY' in response.data
    assert ('/orders/%s/assign' % waiting.id).encode() not in response.data
    assert client.get('/admin/assignment-monitor').status_code==403


@pytest.mark.parametrize(
    'path,permission',
    [('/admin/assignment-monitor', 'assignment.manage'),
     ('/coordinator/assignments', 'reports.coordinate')],
)
def test_branch_monitor_only_exposes_its_cases_and_doctors(path, permission):
    import json
    from uuid import uuid4

    suffix = uuid4().hex[:8]
    branch_a = m.Branch(code=f'MA{suffix}', name=f'Monitor branch A {suffix}')
    branch_b = m.Branch(code=f'MB{suffix}', name=f'Monitor branch B {suffix}')
    role = m.Role(
        code=f'MONITOR-{suffix}', name='Branch monitor',
        permissions_json=json.dumps([permission]),
    )
    m.db.session.add_all([branch_a, branch_b, role]); m.db.session.flush()
    coordinator = m.User(
        username=f'monitor-coordinator-{suffix}', full_name='Branch coordinator',
        password_hash='test', role=role, branch_id=branch_a.id, active=True,
    )
    doctor_a = doctor(f'monitor-doctor-a-{suffix}')
    doctor_b = doctor(f'monitor-doctor-b-{suffix}')
    doctor_a.branch_id = branch_a.id
    doctor_b.branch_id = branch_b.id
    m.db.session.add(coordinator)
    m.db.session.add_all([
        m.DoctorAssignmentProfile(user_id=doctor_a.id),
        m.DoctorAssignmentProfile(user_id=doctor_b.id),
        m.DoctorAvailabilityState(user_id=doctor_a.id, state='AVAILABLE'),
        m.DoctorAvailabilityState(user_id=doctor_b.id, state='AVAILABLE'),
    ])
    order_a = order(f'MONITOR-A-{suffix}'); order_a.branch_id = branch_a.id
    order_b = order(f'MONITOR-B-{suffix}'); order_b.branch_id = branch_b.id
    m.db.session.flush()
    assign(order_a, doctor_a)
    assign(order_b, doctor_b)

    client = m.app.test_client()
    with client.session_transaction() as state:
        state['uid'] = coordinator.id
    response = client.get(path)
    assert response.status_code == 200
    assert order_a.accession.encode() in response.data
    assert order_b.accession.encode() not in response.data
    assert doctor_a.username.encode() in response.data
    assert doctor_b.username.encode() not in response.data
