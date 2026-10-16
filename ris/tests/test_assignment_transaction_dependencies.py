"""Execute mutation contracts with supplied ports and no clinical runtime."""
import subprocess
import sys
from datetime import datetime
from types import SimpleNamespace as Row

import pytest

from application.services.assignment.assignment_transaction import (
    AssignmentPolicies, CaseAssignmentServiceError, assign_case_atomically, accept_offer_atomically,
)


class Repository:
    def __init__(self):
        self.order = Row(id=1, status='IMAGES_RECEIVED', pacs_status='IMAGES_COMPLETE',
                         assigned_doctor_id=None, assignment_visit_id=None)
        self.doctor = Row(id=2, active=True, role=Row(code='RADIOLOGIST'))
        self.report = None
        self.rows = []
        self.offers = [Row(id=7, order_id=1, doctor_user_id=2, status='PENDING',
                           expires_at=None, response_note=''),
                       Row(id=8, order_id=1, doctor_user_id=3, status='PENDING',
                           expires_at=None, response_note='')]
        self.operations = []

    def lock_order(self, order_id):
        self.operations.append('order')
        return self.order

    def lock_report(self, order):
        self.operations.append('report')
        return self.report

    def lock_doctor(self, doctor_id):
        self.operations.append('doctor')
        return self.doctor

    def active_assignments(self, order_id):
        return [a for a in self.rows if a.active]

    def pending_offers(self, order_id):
        return [o for o in self.offers if o.status == 'PENDING']

    def new_assignment(self, **values):
        result = Row(**values)
        self.rows.append(result)
        return result

    def offer_probe(self, offer_id):
        return next((o for o in self.offers if o.id == offer_id), None)

    def order_for_offer(self, offer):
        return self.order

    def lock_offer(self, offer_id):
        self.operations.append('offer')
        return self.offer_probe(offer_id)

    def flush(self):
        self.operations.append('flush')


def policies(validate=lambda o, d: None, allowed=lambda o: True):
    return AssignmentPolicies(validate, lambda *args: {}, allowed, frozenset({'AUTO_OFFER'}))


def test_core_imports_without_runtime_framework_or_persistence():
    code = '''
import sys
import application.services.assignment.assignment_transaction
assert not any(x in sys.modules for x in ('app', 'flask', 'sqlalchemy', 'application.legacy_runtime'))
'''
    subprocess.run([sys.executable, '-c', code], check=True)


def test_assignment_retry_is_idempotent_and_keeps_transaction_caller_owned():
    repo = Repository()
    result = assign_case_atomically(repository=repo, policies=policies(), order_id=1, doctor_user_id=2)
    again = assign_case_atomically(repository=repo, policies=policies(), order_id=1, doctor_user_id=2)
    assert result.assignment is again.assignment and again.idempotent
    assert len(repo.rows) == 1 and repo.order.assigned_doctor_id == 2
    assert all(o.status == 'CANCELLED' for o in repo.offers)
    assert repo.operations[:3] == ['order', 'report', 'doctor']


@pytest.mark.parametrize('barrier,code', [('FINAL', 'CASE_LIFECYCLE_LOCKED'),
                                          ('RECEIVING', 'PACS_RECEIVING'),
                                          ('VERIFIED', 'CASE_REPORT_LOCKED')])
def test_lifecycle_barriers_run_before_assignment_mutations(barrier, code):
    repo = Repository()
    if barrier == 'FINAL': repo.order.status = barrier
    elif barrier == 'RECEIVING': repo.order.pacs_status = barrier
    else: repo.report = Row(status=barrier)
    with pytest.raises(CaseAssignmentServiceError, match=code):
        assign_case_atomically(repository=repo, policies=policies(), order_id=1, doctor_user_id=2)
    assert repo.rows == [] and all(o.status == 'PENDING' for o in repo.offers)
    if barrier == 'FINAL': assert repo.operations == ['order']


def test_explicit_qualification_and_visit_policies_fail_before_mutation():
    repo = Repository()
    def denied(o, d):
        raise CaseAssignmentServiceError('DOCTOR_CLINICAL_SCOPE_DENIED')
    with pytest.raises(CaseAssignmentServiceError, match='CLINICAL_SCOPE'):
        assign_case_atomically(repository=repo, policies=policies(denied), order_id=1, doctor_user_id=2)
    repo.order.assignment_visit_id = 'synthetic-visit'
    with pytest.raises(CaseAssignmentServiceError, match='VISIT_AUTOMATIC_ASSIGNMENT_DISABLED'):
        assign_case_atomically(repository=repo, policies=policies(allowed=lambda o: False),
                               order_id=1, doctor_user_id=2, assignment_type='AUTO_OFFER')
    assert not repo.rows


def test_offer_acceptance_uses_supplied_group_and_assignment_ports_in_lock_order():
    repo = Repository()
    def group(order, lock):
        assert lock
        repo.operations.append('visit')
    def assign_visit(**values):
        return assign_case_atomically(repository=repo, policies=policies(), **values)
    result, offer = accept_offer_atomically(repository=repo, group_members=group, assign_visit=assign_visit,
                                            offer_id=7, actor_user_id=2, now=datetime(2026, 1, 1))
    assert repo.operations[:3] == ['visit', 'order', 'offer']
    assert offer.status == 'ACCEPTED' and repo.offers[1].status == 'CANCELLED'
    assert result.assignment.doctor_user_id == 2
