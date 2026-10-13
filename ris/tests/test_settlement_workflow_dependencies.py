"""Entitlement policy and settlement workflows with synthetic explicit evidence."""
from types import SimpleNamespace as Row
from datetime import datetime
from decimal import Decimal
from pathlib import Path
import subprocess
import sys

import pytest

from domain.finance.settlement_policy import SettlementError, rule_share, fingerprint
from application.services.finance import settlement_workflow as workflow


def rule(**changes):
    data=dict(id=1, doctor_user_id=3, branch_id=None, modality='', procedure_id=None,
              contract_id=None, basis='GROSS', rule_type='PERCENT', value=25)
    return Row(**dict(data, **changes))


def test_most_specific_rule_and_frozen_amount_use_explicit_facts():
    order=Row(branch_id=5, modality='CT', procedure_id=6, contract_id=None,
              gross_price=200, contract_price=180, patient_share=100)
    amount, frozen=rule_share(order,[rule(),rule(id=2,procedure_id=6,value=30)],[])
    assert amount == Decimal('60.00') and frozen['id'] == 2
    assert frozen['base'] == '200.00' and frozen['amount'] == '60.00'


def test_ambiguous_rule_denies_before_discount_evidence_is_consumed():
    order=Row(branch_id=5,modality='CT',procedure_id=6,contract_id=None)
    def discounts():
        raise AssertionError('discount evidence must not be read')
        yield
    with pytest.raises(SettlementError, match='AMBIGUOUS_RULE'):
        rule_share(order,[rule(),rule(id=2)],discounts())


class Repository:
    def __init__(self):
        self.order=Row(id=1,branch_id=5,accession='SYNTHETIC',status='FINAL')
        self.revision=Row(id=9,order_id=1,revision_no=1,doctor_id=3,kind='REPLACEMENT',status='FINAL',finalized_at=datetime(2026,10,11))
        self.saved=None;self.events=[]
    def get_order(self, order_id): return self.order
    def latest(self, order_id): return None
    def earlier_unsettled(self, *args): return None
    def get_doctor(self, doctor_id): return Row(id=doctor_id)
    def payouts(self, *args): return [Row(id=8,amount=20,entry_date=datetime(2026,10,10).date(),payment_method='CASH',reference_no='SYNTHETIC')]
    def lock_order(self, order_id): self.events.append('order');return self.order
    def lock_revision(self, revision_id): self.events.append('revision');return self.revision
    def by_revision(self, revision_id): return self.saved
    def create(self, **values): return Row(id=10, **values)
    def add(self, row): self.saved=row
    def flush(self): self.events.append('flush')


def policies(repo):
    return workflow.SettlementPolicies(actor=lambda order,manage:Row(id=4),original_doctor=lambda order:Row(id=2),
        rule_share=lambda order,doctor_id:(Decimal('50.00'),{'amount':'50.00'}),
        final_version=lambda revision:Row(id=7,finalized_at=datetime(2026,10,11),sha256='synthetic-sha'),
        audit=lambda *args:repo.events.append('audit'))


def plan(repo):
    return workflow.plan(repo,policies(repo),repo.revision,'40','Synthetic verified transfer',True,'20')


def test_confirm_is_idempotent_locks_in_order_and_never_mutates_original_order():
    repo=Repository();original=dict(vars(repo.order))
    data=plan(repo);claims={'data':data,'sha256':fingerprint(data)}
    row,retry=workflow.confirm(repo,policies(repo),claims)
    assert not retry and row.old_amount == Decimal('40') and row.new_amount == Decimal('50')
    assert repo.events == ['order','revision','flush','audit']
    again,retry=workflow.confirm(repo,policies(repo),claims)
    assert retry and again is row and repo.events.count('audit') == 1
    assert vars(repo.order) == original


def test_non_final_replacement_or_unverified_payout_evidence_cannot_plan():
    repo=Repository();repo.revision.kind='ADDENDUM'
    with pytest.raises(SettlementError,match='FINAL_REPLACEMENT_ONLY'):plan(repo)
    repo.revision.kind='REPLACEMENT'
    with pytest.raises(SettlementError,match='PAYMENTS_NOT_VERIFIED'):
        workflow.plan(repo,policies(repo),repo.revision,'40','Synthetic verified transfer',True,'19')
    assert repo.saved is None and repo.events == []


def test_changed_preview_does_not_persist_or_audit():
    repo=Repository();data=plan(repo);claims={'data':data,'sha256':fingerprint(data)}
    repo.revision.doctor_id=6
    with pytest.raises(SettlementError,match='STALE_PREVIEW'):workflow.confirm(repo,policies(repo),claims)
    assert repo.saved is None and 'audit' not in repo.events


def test_workflow_import_has_no_database_web_or_runtime():
    ris=str(Path(__file__).resolve().parents[1])
    code="import sys;sys.path.insert(0,%r);import application.services.finance.settlement_workflow;assert not any(n == 'flask' or n == 'sqlalchemy' or n.startswith('infrastructure.') or n == 'application.legacy_runtime' for n in sys.modules)" % ris
    subprocess.run([sys.executable,'-c',code],check=True)
