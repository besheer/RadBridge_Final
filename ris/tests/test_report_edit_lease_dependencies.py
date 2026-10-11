"""Lease ownership, lock ordering and explicit clock contracts."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace as Row
from pathlib import Path
import subprocess
import sys
import uuid

import pytest

from application.services.reporting import edit_lease_service as service
from domain.reporting.edit_policy import ReportEditLocked, ReportRoleDenied, FinalReportLocked, _token_hash
from infrastructure.adapters.reporting.edit_lease_repository import SqlAlchemyEditLeaseRepository

NOW = datetime(2026, 10, 11, tzinfo=timezone.utc)


class Repository:
    def __init__(self, owner=2, lease=None):
        self.owner, self.lease, self.events, self.writes = owner, lease, [], []

    def lock_order_owner(self, order_id): self.events.append('order'); return self.owner
    def lock_report(self, report_id): self.events.append('report')
    def read_locked_lease(self, order_id): self.events.append('lease'); return self.lease
    def read_lease(self, order_id): return self.lease
    def upsert(self, values): self.writes.append(values)


def request(repository):
    return dict(repository=repository, clock=lambda: NOW,
                group_members=lambda order, lock: repository.events.append('group'),
                mark_reading_started=lambda order_id, user_id: repository.events.append('started'),
                order=Row(id=1), report=Row(id=3, status='DRAFT'),
                user=Row(id=2, role=Row(code='RADIOLOGIST')), editor_type='ONLYOFFICE', lease_token='synthetic-token')


def test_lease_acquisition_uses_group_order_report_lease_lock_order():
    repo = Repository()
    lease = service.acquire_or_renew_lease(**request(repo))
    assert repo.events == ['group', 'order', 'report', 'lease', 'started']
    assert lease.expires_at == NOW + timedelta(seconds=120)
    assert repo.writes[0]['lease_token_hash'] == _token_hash('synthetic-token')
    assert 'synthetic-token' not in repo.writes[0].values()


def test_refreshed_assignment_denial_stops_before_report_or_lease_mutation():
    repo = Repository(owner=9)
    with pytest.raises(ReportRoleDenied, match='REPORT_CASE_NOT_ASSIGNED'):
        service.acquire_or_renew_lease(**request(repo))
    assert repo.events == ['group', 'order'] and repo.writes == []


def test_active_foreign_token_blocks_but_expired_lease_can_be_replaced():
    repo = Repository(lease=dict(user_id=2, lease_token_hash='another-token', expires_at=NOW+timedelta(seconds=1)))
    with pytest.raises(ReportEditLocked): service.acquire_or_renew_lease(**request(repo))
    assert repo.writes == []
    repo.lease['expires_at'] = NOW.replace(tzinfo=None) - timedelta(seconds=1)
    service.acquire_or_renew_lease(**request(repo))
    assert len(repo.writes) == 1


def test_final_denial_precedes_all_locks():
    repo = Repository()
    values = request(repo); values['report'].status = 'FINAL'
    with pytest.raises(FinalReportLocked): service.acquire_or_renew_lease(**values)
    assert repo.events == [] and repo.writes == []


def test_service_imports_without_storage_database_or_web():
    ris = str(Path(__file__).resolve().parents[1])
    code = "import sys; sys.path.insert(0,%r); import application.services.reporting.edit_lease_service; assert not any(n == 'flask' or n == 'sqlalchemy' or n.startswith('infrastructure.') or n == 'application.legacy_runtime' for n in sys.modules)" % ris
    subprocess.run([sys.executable, '-c', code], check=True)


def test_postgres_real_lease_lock_upsert_renewal_and_token_scoped_release(app_ctx):
    m = app_ctx
    if m.db.engine.dialect.name != 'postgresql':
        pytest.skip('real FOR UPDATE/upsert contract uses isolated PostgreSQL CI')
    key = 'SYNTHETIC-LEASE-' + uuid.uuid4().hex[:8]
    try:
        patient = m.Patient(patient_id=key, name='Synthetic Lease Patient')
        doctor = m.User(username=key, full_name='Synthetic Lease Doctor', active=True, password_hash='synthetic-only',
                        role=m.Role.query.filter_by(code='RADIOLOGIST').one())
        m.db.session.add_all([patient, doctor]); m.db.session.flush()
        order = m.Order(patient_id=patient.id, accession=key, modality='CT', procedure='Synthetic',
                        scheduled=NOW, assigned_doctor_id=doctor.id, status='REPORTING')
        m.db.session.add(order); m.db.session.flush()
        report = m.Report(order_id=order.id, status='DRAFT')
        m.db.session.add(report); m.db.session.flush()
        repo = SqlAlchemyEditLeaseRepository(m.db.session)
        values = dict(repository=repo, clock=lambda: NOW, group_members=lambda order, lock: None,
                      mark_reading_started=lambda order_id, user_id: None,
                      order=order, report=report, user=doctor, editor_type='ONLYOFFICE', lease_token='synthetic')
        service.acquire_or_renew_lease(**values)
        values['clock'] = lambda: NOW+timedelta(seconds=30)
        service.acquire_or_renew_lease(**values)
        lease = service.get_active_lease(repo, order.id, values['clock'])
        assert lease.user_id == doctor.id and lease.expires_at == NOW+timedelta(seconds=150)
        with pytest.raises(ReportEditLocked):
            service.acquire_or_renew_lease(**dict(values, lease_token='different'))
        assert service.release_lease(repository=repo, order_id=order.id, user_id=doctor.id, lease_token='wrong') == 0
        assert service.release_lease(repository=repo, order_id=order.id, user_id=doctor.id, lease_token='synthetic') == 1
        assert service.get_active_lease(repo, order.id, values['clock']) is None
    finally:
        m.db.session.rollback(); m.db.session.remove()
