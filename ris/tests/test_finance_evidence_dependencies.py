from datetime import date,datetime
from types import SimpleNamespace as Row
import pytest
from application.services.finance.collection_access import CollectionAccess
from application.services.finance.closing_totals import payment_totals
from domain.finance.closing_policy import money


class BranchRepository:
    def __init__(self, branch): self.row=branch;self.calls=[]
    def branch(self, branch_id): self.calls.append(branch_id);return self.row


@pytest.mark.parametrize('role,active,branch_id,target,enabled,allowed', [
    ('RECEPTION',True,1,1,True,True),('RECEPTION',True,1,1,False,False),
    ('RECEPTION',True,1,2,True,False),('CASHIER',True,1,2,True,False),
    ('CASHIER',True,1,1,False,True),('CASHIER',False,1,1,True,False),
    ('CASHIER',True,None,1,True,False),
])
def test_collection_boundary_keeps_branch_setting_and_active_user(role,active,branch_id,target,enabled,allowed):
    repo=BranchRepository(Row(active=True,reception_collection_enabled=enabled))
    user=Row(active=active,branch_id=branch_id,role=Row(code=role))
    assert CollectionAccess(repo).branch_allowed(user,target)==allowed
    if role!='RECEPTION' or branch_id!=target or not active:
        assert repo.calls==[]


def test_missing_or_inactive_branch_does_not_enable_reception():
    user=Row(active=True,branch_id=1)
    for branch in (None,Row(active=False,reception_collection_enabled=True)):
        assert not CollectionAccess(BranchRepository(branch)).reception_allowed(user)


def test_collection_guard_does_not_replace_route_permission_gate():
    repo=BranchRepository(None)
    assert CollectionAccess(repo).branch_allowed(Row(active=True,branch_id=None,role=Row(code='MANAGEMENT')),1)
    assert repo.calls==[]  # Existing route remains responsible for financial permission.


class PaymentRepository:
    def __init__(self, receipts, refunds):self.receipt_rows=receipts;self.refund_rows=refunds;self.calls=[]
    def receipts(self,*args):self.calls.append(('receipts',args));return self.receipt_rows
    def refunds(self,*args):self.calls.append(('refunds',args));return self.refund_rows


def test_totals_use_accounting_window_original_refund_method_and_decimal_arithmetic():
    receipt=Row(order_id=3,method='POS',amount='10.10')
    repo=PaymentRepository([receipt,Row(order_id=3,method='CASH',amount='0.1'),Row(order_id=3,method='CASH',amount='0.2')],
                           [Row(order_id=3,payment=receipt,amount='2.10')])
    assert payment_totals(repository=repo,branch_id=7,closing_date=date(2026,1,1))==dict(CASH=0.3,CARD=8.0,OTHER=0.0)
    expected=(7,datetime(2026,1,1),datetime(2026,1,2))
    assert repo.calls==[('receipts',expected),('refunds',expected)]


@pytest.mark.parametrize('payment',[None,Row(order_id=4,method='CASH')])
def test_refund_mismatch_is_not_zeroed(payment):
    repo=PaymentRepository([], [Row(order_id=3,payment=payment,amount=1)])
    with pytest.raises(ValueError,match='Refund receipt mismatch'):
        payment_totals(repository=repo,branch_id=7,closing_date=date(2026,1,1))


@pytest.mark.parametrize('amount',['nan','inf','-inf','bad'])
def test_counted_money_is_finite(amount):
    with pytest.raises(ValueError,match='Enter valid counted amounts'):money(amount)
