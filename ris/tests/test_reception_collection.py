import json
import pytest
import app as m
from test_assignment_distribution import doctor,order

@pytest.fixture(autouse=True)
def isolated(app_ctx,monkeypatch):
    monkeypatch.setattr(m.db.session,'commit',m.db.session.flush)
    yield
    m.db.session.rollback();m.db.session.remove()

def setup(monkeypatch,role='RECEPTION',enabled=True):
    b=m.Branch(code='UAT-COLLECT',name='CODEX UAT Collection',active=True,reception_collection_enabled=enabled)
    other=m.Branch(code='UAT-OTHER',name='CODEX UAT Other',active=True,reception_collection_enabled=True)
    m.db.session.add_all([b,other]);m.db.session.flush()
    u=doctor('CODEX-UAT-collection-'+role,role);u.branch_id=b.id
    perms=['payments.create','cashier.workstation','orders.view','receipts.print'] if role in ('RECEPTION','CASHIER') else []
    u.role.permissions_json=json.dumps(perms)
    o=order('CODEX-UAT-COLLECTION');o.branch_id=b.id;o.patient_share=100;o.gross_price=100;o.paid_amount=0
    x=order('CODEX-UAT-OTHER-COLLECTION');x.branch_id=other.id;x.patient_share=100;x.gross_price=100;x.paid_amount=0
    m.db.session.flush();monkeypatch.setattr(m,'current_user',lambda:u)
    c=m.app.test_client()
    with c.session_transaction() as s:s['uid']=u.id
    return c,u,b,o,x

@pytest.mark.parametrize('endpoint',['/orders/{}/payment','/payments/{}'])
def test_reception_collects_once_in_own_branch_with_receipt_and_payment(monkeypatch,endpoint):
    c,u,b,o,x=setup(monkeypatch)
    r=c.post(endpoint.format(o.id),data={'amount':'40','payment_method':'CASH'})
    assert r.status_code==302 and o.paid_amount==40
    receipt=m.Receipt.query.filter_by(order_id=o.id).one()
    payment=m.Payment.query.filter_by(order_id=o.id).one()
    assert receipt.created_by==payment.created_by==u.id and float(receipt.amount)==payment.amount==40
    assert c.get('/receipts/'+str(receipt.id)).status_code==200
    assert m.AuditLog.query.filter_by(action='PAYMENT_RECEIVED',user_id=u.id).count()==1

@pytest.mark.parametrize('endpoint',['/orders/{}/payment','/payments/{}'])
@pytest.mark.parametrize('role',['RECEPTION','CASHIER'])
def test_forged_other_branch_payment_denied(monkeypatch,endpoint,role):
    c,u,b,o,x=setup(monkeypatch,role)
    assert c.post(endpoint.format(x.id),data={'amount':'40'}).status_code==403
    assert x.paid_amount==0 and m.Receipt.query.count()==0 and m.Payment.query.count()==0

def test_disabled_branch_blocks_reception_ui_and_direct_post(monkeypatch):
    c,u,b,o,x=setup(monkeypatch,enabled=False)
    assert c.get('/cashier').status_code==403
    assert c.post('/orders/'+str(o.id)+'/payment',data={'amount':'40'}).status_code==403
    with m.app.test_request_context('/'):
        assert not m.has_perm('payments.create') and not m.has_perm('cashier.workstation')


def test_collection_permissions_and_payment_route_use_explicit_runtime(monkeypatch):
    c,u,b,o,x=setup(monkeypatch)
    import application.legacy_runtime as legacy_runtime

    def forbidden_runtime_lookup():
        raise AssertionError('collection policy must use runtime supplied by composition')

    monkeypatch.setattr(legacy_runtime,'resolve_runtime',forbidden_runtime_lookup)
    with m.app.test_request_context('/'):
        assert m.has_perm('payments.create')
    response=c.post('/orders/'+str(o.id)+'/payment',data={'amount':'10'})
    assert response.status_code==302 and o.paid_amount==10

@pytest.mark.parametrize('role',['RECEPTION','CASHIER'])
def test_cashier_list_is_scoped_to_staff_branch(monkeypatch,role):
    c,u,b,o,x=setup(monkeypatch,role)
    response=c.get('/cashier');assert response.status_code==200
    assert o.accession.encode() in response.data and x.accession.encode() not in response.data

@pytest.mark.parametrize('role',['NURSING','TECHNICIAN','RADIOLOGIST','CASE_COORDINATOR'])
def test_other_roles_do_not_gain_collection(monkeypatch,role):
    c,u,b,o,x=setup(monkeypatch,role)
    assert c.get('/cashier').status_code==403
    assert c.post('/orders/'+str(o.id)+'/payment',data={'amount':'40'}).status_code==403

@pytest.mark.parametrize('amount',['101','nan','inf','-1','0'])
def test_invalid_or_excess_amount_never_collects(monkeypatch,amount):
    c,u,b,o,x=setup(monkeypatch)
    assert c.post('/orders/'+str(o.id)+'/payment',data={'amount':amount}).status_code==302
    assert o.paid_amount==0 and m.Receipt.query.count()==0 and m.Payment.query.count()==0

def test_branchless_reception_denied(monkeypatch):
    c,u,b,o,x=setup(monkeypatch);u.branch_id=None;m.db.session.flush()
    assert c.post('/orders/'+str(o.id)+'/payment',data={'amount':'40'}).status_code==403

def test_admin_policy_update_audited_and_reception_denied(monkeypatch):
    c,u,b,o,x=setup(monkeypatch)
    assert c.post('/admin/branches',data={'action':'collection_policy','branch_id':b.id}).status_code==403
    admin=doctor('CODEX-UAT-collection-admin','SUPER_ADMIN');monkeypatch.setattr(m,'current_user',lambda:admin)
    assert c.post('/admin/branches',data={'action':'collection_policy','branch_id':b.id}).status_code==302
    assert not b.reception_collection_enabled
    assert m.AuditLog.query.filter_by(action='BRANCH_RECEPTION_COLLECTION',user_id=admin.id).count()==1

def test_cashier_does_not_require_reception_setting(monkeypatch):
    c,u,b,o,x=setup(monkeypatch,'CASHIER',False)
    assert c.post('/orders/'+str(o.id)+'/payment',data={'amount':'40'}).status_code==302
    assert o.paid_amount==40


def test_new_branch_collection_setting_can_be_selected(monkeypatch):
    c,u,b,o,x=setup(monkeypatch)
    admin=doctor('CODEX-UAT-create-branch-admin','SUPER_ADMIN');monkeypatch.setattr(m,'current_user',lambda:admin)
    response=c.post('/admin/branches',data={'code':'UAT-NEW','name':'CODEX UAT New Branch','reception_collection_enabled':'1'})
    assert response.status_code==200
    assert m.Branch.query.filter_by(code='UAT-NEW').one().reception_collection_enabled


def test_registration_collection_has_receipt_and_blocks_cross_branch(monkeypatch):
    c,u,b,o,x=setup(monkeypatch)
    with m.app.test_request_context('/'):
        m._rb_v5462_payment([o],{'payment_amount':'40','payment_method':'CASH'})
        assert o.paid_amount==40 and m.Receipt.query.filter_by(order_id=o.id).count()==1
        from werkzeug.exceptions import Forbidden
        with pytest.raises(Forbidden):m._rb_v5462_payment([x],{'payment_amount':'40','payment_method':'CASH'})
        assert x.paid_amount==0

def test_other_branch_receipt_denied_for_reception(monkeypatch):
    c,u,b,o,x=setup(monkeypatch)
    r=m.Receipt(receipt_no='UAT-OTHER-RECEIPT',order_id=x.id,amount=1)
    m.db.session.add(r);m.db.session.flush()
    assert c.get('/receipts/'+str(r.id)).status_code==403
    assert c.get('/receipts/'+str(r.id)+'/studio-print').status_code==403


@pytest.mark.parametrize('method',['VISA','MASTERCARD','WALLET','BANK_TRANSFER'])
def test_supported_non_cash_methods_record_receipt_and_payment(monkeypatch,method):
    c,u,b,o,x=setup(monkeypatch)
    assert c.post('/orders/'+str(o.id)+'/payment',data={'amount':'40','payment_method':method,'reference_no':'CODEX-UAT-REF'}).status_code==302
    receipt=m.Receipt.query.filter_by(order_id=o.id).one()
    payment=m.Payment.query.filter_by(order_id=o.id).one()
    assert receipt.payment_method==payment.method==method
    assert receipt.reference_no==payment.reference=='CODEX-UAT-REF'
    assert o.paid_amount==40 and float(receipt.amount)==payment.amount==40
