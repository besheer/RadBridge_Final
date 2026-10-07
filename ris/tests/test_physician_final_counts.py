"""Counts, period boundaries and access tests use isolated synthetic records."""
import json
from datetime import datetime
from types import SimpleNamespace as NS
from uuid import uuid4

import pytest
import physician_final_counts as counts


@pytest.fixture
def final_counts(app_ctx, monkeypatch):
    m = app_ctx
    key = 'CODEX-UAT-' + uuid4().hex[:10]
    branches = [m.Branch(code=key + str(i), name=key + str(i)) for i in range(2)]
    m.db.session.add_all(branches)
    m.db.session.flush()
    role = m.Role.query.filter_by(code='CASE_COORDINATOR').one()
    role.permissions_json = json.dumps(['reports.coordinate'])
    actor = m.User(username=key, full_name=key, password_hash='disabled',
                   role_id=role.id, branch_id=branches[0].id, active=True)
    docs = [m.User(username=key + 'D' + str(i), full_name=key + 'D' + str(i),
                   password_hash='disabled', active=(i == 0),
                   role_id=m.Role.query.filter_by(code='RADIOLOGIST').one().id) for i in range(2)]
    patient = m.Patient(patient_id=key, name='CODEX UAT COUNTS')
    m.db.session.add_all([actor, patient] + docs)
    m.db.session.flush()
    orders = []
    for i in range(2):
        o = m.Order(accession=key + 'CASE' + str(i), patient_id=patient.id,
                    modality='DX', procedure='CODEX UAT COUNTS',
                    branch_id=branches[i].id, assigned_doctor_id=docs[0].id,
                    status='FINAL', scheduled=datetime(2030, 1, 1))
        m.db.session.add(o)
        m.db.session.flush()
        r = m.Report(order_id=o.id, status='FINAL', finalized_at=datetime(2038, 2, 10))
        m.db.session.add(r)
        m.db.session.flush()
        for v in range(2):
            m.db.session.add(m.ReportVersion(report_id=r.id, accession=o.accession,
                version_no=v + 1, action='FINALIZE', status='VERIFIED',
                finalized_at=datetime(2038, 2, 10)))
        orders.append(o)
    m.db.session.flush()
    for i in range(2):
        r = m.Report.query.filter_by(order_id=orders[0].id).one()
        version = m.ReportVersion.query.filter_by(report_id=r.id).first()
        m.db.session.add(m.ReportRevision(order_id=orders[0].id,
            original_report_id=r.id, original_version_id=version.id,
            original_sha256='0' * 64, base_sha256='0' * 64, revision_no=i + 1,
            kind='REPLACEMENT', reason='CODEX UAT reason', requested_by=docs[0].id,
            doctor_id=docs[1].id, status='FINAL', finalized_at=datetime(2038, 2, 12)))
    m.db.session.flush()
    monkeypatch.setattr(m, 'current_user', lambda: actor)
    client = m.app.test_client()
    with m.app.test_request_context('/coordinator/physician-final-counts'):
        yield NS(m=m, actor=actor, docs=docs, branches=branches, orders=orders, client=client)
    m.db.session.rollback()
    m.db.session.remove()


def data(f, **kw):
    return counts.snapshot(f.m, datetime(2038, 2, 1), datetime(2038, 3, 1), **kw)


def test_versions_and_corrections_do_not_duplicate_original_cases(final_counts):
    f = final_counts
    result = data(f)
    assert result['total_originals'] == 1
    assert result['total_corrections'] == 2
    row = next(r for r in result['rows'] if r['doctor_id'] == f.docs[1].id)
    assert row['originals'] == 0 and row['correction_cases'] == 1 and row['corrections'] == 2
    assert f.docs[1] in result['doctors']  # inactive historical doctors remain visible


def test_period_uses_finalization_instead_of_appointment(final_counts):
    f = final_counts
    assert counts.snapshot(f.m, datetime(2030, 1, 1), datetime(2030, 2, 1))['rows'] == []
    result = counts.snapshot(f.m, datetime(2038, 2, 12), datetime(2038, 2, 13))
    assert result['total_originals'] == 0 and result['total_corrections'] == 2
    assert counts.snapshot(f.m, datetime(2038, 2, 11), datetime(2038, 2, 12))['total_corrections'] == 0


def test_cross_branch_filter_is_rejected(final_counts):
    from werkzeug.exceptions import Forbidden
    with pytest.raises(Forbidden):
        data(final_counts, branch_id=final_counts.branches[1].id)


@pytest.mark.parametrize('change', ['inactive', 'branchless', 'permission'])
def test_fail_closed_access(final_counts, change):
    f = final_counts
    if change == 'inactive': f.actor.active = False
    if change == 'branchless': f.actor.branch_id = None
    if change == 'permission': f.actor.role.permissions_json = '[]'
    from werkzeug.exceptions import Forbidden
    with pytest.raises(Forbidden): data(f)


def test_admin_scope_and_doctor_filter(final_counts):
    f = final_counts
    f.actor.role = f.m.Role.query.filter_by(code='SUPER_ADMIN').one()
    assert data(f)['total_originals'] == 2
    assert data(f, doctor_id=f.docs[1].id)['total_originals'] == 0
    assert data(f, doctor_id=f.docs[1].id)['total_corrections'] == 2
    assert data(f, branch_id=f.branches[1].id)['total_corrections'] == 0


def test_nonfinal_reports_and_revisions_are_excluded(final_counts):
    f = final_counts
    f.m.Report.query.filter_by(order_id=f.orders[0].id).one().status = 'DRAFT'
    f.m.ReportRevision.query.filter_by(order_id=f.orders[0].id).update({'status': 'DRAFT'})
    f.m.db.session.flush()
    assert data(f)['rows'] == []


@pytest.mark.parametrize('query', ['start=bad', 'end=9999-12-31', 'start=2038-03-01&end=2038-02-01', 'doctor_id=bad', 'branch_id=-1'])
def test_invalid_filters_return_400(final_counts, query):
    assert final_counts.client.get('/coordinator/physician-final-counts?' + query,
                                   base_url='https://localhost').status_code == 400


def test_route_renders_without_business_writes(final_counts, monkeypatch):
    f = final_counts
    def no_commit(): raise AssertionError('Read-only report committed data')
    monkeypatch.setattr(f.m.db.session, 'commit', no_commit)
    response = f.client.get('/coordinator/physician-final-counts?start=2038-02-01&end=2038-02-28', base_url='https://localhost')
    assert response.status_code == 200
    assert f.docs[0].full_name.encode() in response.data
    assert f.branches[1].name.encode() not in response.data
    assert f.orders[0].accession.encode() not in response.data  # aggregate only, no patient rows


def test_unauthenticated_redirects_to_login(final_counts, monkeypatch):
    monkeypatch.setattr(final_counts.m, 'current_user', lambda: None)
    response = final_counts.client.get('/coordinator/physician-final-counts', base_url='https://localhost')
    assert response.status_code == 302 and '/login' in response.location
