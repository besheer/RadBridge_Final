"""Correction request/review state changes over independent injected ports."""
from types import SimpleNamespace as Row
from datetime import datetime
from pathlib import Path
import subprocess
import sys

import pytest

from application.services.reporting import revision_workflow as workflow
from domain.reporting.revision_policy import RevisionError


class Repository:
    def __init__(self):
        self.order = Row(id=1)
        self.row = Row(id=8, order_id=1, status='REQUESTED', doctor_id=None, requested_by=2,
                       reason='Synthetic correction reason', active_order_id=1)
        self.events, self.active, self.added = [], None, []

    def lock_order(self, order_id): self.events.append('order'); return self.order
    def lock_revision(self, revision_id): self.events.append('revision'); return self.row
    def active_revision(self, order_id): return self.active
    def latest_revision(self, order_id): return None
    def create_revision(self, **values): return Row(id=9, **values)
    def add(self, row): self.added.append(row)
    def flush(self): self.events.append('flush')
    def get_doctor(self, doctor_id): return Row(id=doctor_id)


def policies(repo, qualified=True):
    return workflow.RevisionPolicies(
        reference=lambda order:(Row(id=3), Row(id=4), 'synthetic.docx', 'original-sha', None, 'original-sha'),
        check_reference=lambda order,row:repo.events.append('reference'),
        eligible=lambda order,doctor:qualified,
        audit=lambda *args:repo.events.append('audit'),
        notify=lambda *args:repo.events.append('notify'),
        clock=lambda:datetime(2026,10,11),
    )


def test_request_uses_original_reference_and_flushes_before_audit():
    repo = Repository()
    row = workflow.request_revision(repo, policies(repo), repo.order, Row(id=2),
                                    'Synthetic correction reason', 'replacement')
    assert row.status == 'REQUESTED' and row.kind == 'REPLACEMENT'
    assert (row.original_report_id, row.original_version_id, row.original_sha256) == (3,4,'original-sha')
    assert repo.events == ['order','flush','audit','notify']
    assert vars(repo.order) == {'id':1}


def test_duplicate_request_does_not_create_or_audit():
    repo = Repository(); repo.active = repo.row
    with pytest.raises(RevisionError, match='ACTIVE'):
        workflow.request_revision(repo, policies(repo), repo.order, Row(id=2),
                                  'Synthetic correction reason', 'ADDENDUM')
    assert repo.added == [] and repo.events == ['order']


def test_approval_locks_order_then_revision_and_preserves_original_order():
    repo = Repository()
    row = workflow.review(repo, policies(repo), repo.row, Row(id=5), 'APPROVE',
                          'Synthetic approval reason', doctor_id=7)
    assert repo.events[:3] == ['order','revision','reference']
    assert row.status == 'DRAFT' and row.doctor_id == 7
    assert row.reviewed_at == datetime(2026,10,11)
    assert vars(repo.order) == {'id':1}


def test_unqualified_doctor_cannot_change_or_audit_revision():
    repo = Repository()
    with pytest.raises(RevisionError, match='DOCTOR'):
        workflow.review(repo, policies(repo, qualified=False), repo.row, Row(id=5),
                        'APPROVE', 'Synthetic approval reason', doctor_id=7)
    assert repo.row.status == 'REQUESTED' and repo.row.doctor_id is None
    assert 'audit' not in repo.events and 'notify' not in repo.events


def test_rejection_releases_active_request_and_repeat_is_denied():
    repo = Repository()
    workflow.review(repo, policies(repo), repo.row, Row(id=5), 'REJECT', 'Synthetic rejection reason')
    assert repo.row.status == 'REJECTED' and repo.row.active_order_id is None
    with pytest.raises(RevisionError, match='STATE'):
        workflow.review(repo, policies(repo), repo.row, Row(id=5), 'APPROVE', 'Synthetic approval reason', 7)


def test_workflow_import_has_no_framework_persistence_or_runtime():
    ris = str(Path(__file__).resolve().parents[1])
    code = "import sys; sys.path.insert(0,%r); import application.services.reporting.revision_workflow; assert not any(n == 'flask' or n == 'sqlalchemy' or n.startswith('infrastructure.') or n == 'application.legacy_runtime' for n in sys.modules)" % ris
    subprocess.run([sys.executable, '-c', code], check=True)
