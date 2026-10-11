import subprocess
import sys
from datetime import datetime, timedelta
from types import SimpleNamespace as Row

import pytest

from application.services.assignment.visit_assignment import VisitAssignmentService, VisitPolicies


class Repository:
    def __init__(self):
        self.visit = Row(id='visit', patient_id=1, branch_id=2, assignment_mode='AUTO', registration_open=False)
        self.rows = [Row(id=i, patient_id=1, branch_id=2, assignment_visit_id='visit', assigned_doctor_id=None,
                         modality=modality, status='IMAGES_RECEIVED', exam_status='EXAM_COMPLETED',
                         pacs_status='IMAGES_COMPLETE', report=None) for i, modality in ((1, 'CT'), (2, 'MR'))]
        self.sources = [('INTERNAL', None), ('INTERNAL', None)]
        self.operations = []

    def find_visit(self, visit_id): return self.visit
    def lock_visit(self, visit): self.operations.append('visit-lock')
    def visit_orders(self, visit_id, lock): return self.rows
    def source_of(self, order_id): return self.sources[order_id - 1]
    def get_order(self, order_id): return self.rows[order_id - 1]
    def lock_doctor(self, doctor_id): return Row(id=doctor_id)
    def doctor_profile(self, doctor_id): return Row(modalities='CT,MR', branches='2')
    def lock_report(self, order): return None
    def open_booking(self, visit_id): return None
    def flush(self): self.operations.append('flush')


def test_group_boundaries_reject_another_patient_branch_or_source_before_mutation():
    for field, value in [('patient_id', 99), ('branch_id', 99)]:
        repo = Repository()
        setattr(repo.rows[1], field, value)
        with pytest.raises(ValueError, match='VISIT_PATIENT_BRANCH_MISMATCH'):
            VisitAssignmentService(repo, None).group_members(repo.rows[0], lock=True)
        assert repo.operations == ['visit-lock']
    repo = Repository()
    repo.sources[1] = ('EXTERNAL', 44)
    with pytest.raises(ValueError, match='VISIT_SOURCE_CENTER_MISMATCH'):
        VisitAssignmentService(repo, None).group_members(repo.rows[0], lock=True)
    assert 'flush' not in repo.operations


def test_group_assignment_uses_supplied_policy_and_unifies_member_deadlines():
    repo = Repository()
    results = []
    now = datetime(2026, 1, 1)
    def assign(**values):
        order = repo.get_order(values['order_id'])
        result = Row(order=order, assignment=Row(assigned_at=now,
                     start_deadline_at=now + timedelta(minutes=order.id * 10), start_timeout_seconds=0))
        results.append(result)
        return result
    policies = VisitPolicies(lambda oid: False, lambda order: {'allowed': True},
                            lambda doctor: 0, lambda doctor: 20, lambda o, d: None,
                            assign, frozenset({'AUTO_OFFER'}))
    result = VisitAssignmentService(repo, policies).assign_visit_atomically(
        order_id=1, doctor_user_id=7, assignment_type='AUTO_OFFER')
    assert result.order.id == 1 and len(results) == 2
    assert {r.assignment.start_timeout_seconds for r in results} == {1200}
    assert len({r.assignment.start_deadline_at for r in results}) == 1
    assert repo.operations[-1] == 'flush'


def test_visit_service_imports_without_runtime_database_or_web():
    code = '''
import sys
import application.services.assignment.visit_assignment
assert not any(x in sys.modules for x in ('app', 'flask', 'sqlalchemy', 'application.legacy_runtime'))
'''
    subprocess.run([sys.executable, '-c', code], check=True)
