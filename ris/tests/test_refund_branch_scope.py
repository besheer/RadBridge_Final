from types import SimpleNamespace
from unittest.mock import Mock
import pytest

@pytest.fixture
def refund_scope(app_ctx,monkeypatch):
    m=app_ctx
    user=SimpleNamespace(id=1901,active=True,branch_id=2,role=SimpleNamespace(code='CASHIER',permissions=lambda:['payments.refund']))
    order=SimpleNamespace(id=987000,branch_id=2,paid_amount=100)
    payment=SimpleNamespace(id=987000,order=order,amount=100,status='PAID')
    monkeypatch.setattr(m,'current_user',lambda:user)
    monkeypatch.setattr(type(m.Payment.query),'get_or_404',lambda self,pid:payment)
    monkeypatch.setattr(m,'render_template',lambda *a,**kw:'CODEX UAT error')
    monkeypatch.setattr(m,'audit',Mock())
    monkeypatch.setattr(m.db.session,'add',Mock())
    monkeypatch.setattr(m.db.session,'commit',Mock())
    return m,user,order,payment

@pytest.mark.parametrize('boundary',['cross_branch','missing_branch','inactive'])
def test_cashier_denied_before_refund_or_balance_mutation(refund_scope,boundary):
    m,user,order,payment=refund_scope
    if boundary=='cross_branch':order.branch_id=3
    if boundary=='missing_branch':user.branch_id=None
    if boundary=='inactive':user.active=False
    with m.app.test_client() as client:
        r=client.post('/payments/987000/refund',data={'amount':'10','reason':'CODEX UAT refund scope'})
    assert r.status_code==403
    assert order.paid_amount==100 and payment.status=='PAID'
    m.db.session.add.assert_not_called();m.db.session.commit.assert_not_called();m.audit.assert_not_called()

@pytest.mark.parametrize('global_admin',[False,True])
def test_authorized_refund_keeps_amount_and_audit_contract(refund_scope,global_admin):
    m,user,order,payment=refund_scope
    if global_admin:user.role.code='SUPER_ADMIN';user.branch_id=None;order.branch_id=3
    with m.app.test_client() as client:
        r=client.post('/payments/987000/refund',data={'amount':'10','reason':'CODEX UAT refund scope'})
    assert r.status_code==302
    assert order.paid_amount==90 and payment.status=='PARTIAL_REFUND'
    row=m.db.session.add.call_args.args[0]
    assert row.payment_id==payment.id and row.order_id==order.id and row.amount==10
    assert m.audit.call_args.args[0]=='PAYMENT_REFUND'
    m.db.session.commit.assert_called_once()
