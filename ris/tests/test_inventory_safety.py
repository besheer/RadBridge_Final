from datetime import date,datetime,timedelta
from types import SimpleNamespace
from uuid import uuid4
import pytest


@pytest.fixture
def stock_case(app_ctx,monkeypatch):
    m=app_ctx;key='CODEX-UAT-'+uuid4().hex[:8]
    b=m.Branch(code=key,name=key,active=True)
    p=m.Patient(patient_id=key,name='CODEX UAT STOCK',dob='19900101',sex='M')
    m.db.session.add_all([b,p]);m.db.session.flush()
    o=m.Order(accession=key,patient_id=p.id,branch_id=b.id,modality='DX',procedure=key,scheduled=datetime(2037,2,3,10))
    w=m.Warehouse(code=key,name=key,branch_id=b.id,warehouse_type='BRANCH',active=True)
    i=m.InventoryItem(code=key,name=key,unit='EA',track_expiry=True,default_cost=99,active=True)
    m.db.session.add_all([o,w,i]);m.db.session.flush()
    user=m.User(username=key,full_name='Synthetic Stock Technician',password_hash='disabled-test-account',
                active=True,branch_id=b.id,role=m.Role.query.filter_by(code='TECHNICIAN').one())
    m.db.session.add(user);m.db.session.flush()
    monkeypatch.setattr(m,'current_user',lambda:user)
    yield SimpleNamespace(m=m,order=o,wh=w,item=i,user=user)
    m.db.session.rollback();m.db.session.remove()


def lot(c,qty=10,expires=None,cost=5,reserved=0):
    row=c.m.InventoryLot(warehouse_id=c.wh.id,item_id=c.item.id,lot_no=uuid4().hex,
        qty_on_hand=qty,qty_reserved=reserved,unit_cost=cost,expiry_date=expires)
    c.m.db.session.add(row);c.m.db.session.flush();return row


def consume(c,qty,kind='USED'):
    return c.m.consume_inventory(c.order,c.item,qty,usage_type=kind,warehouse=c.wh,user=c.user)


def give_back(c,qty):
    return c.m.return_inventory(c.order,c.item,qty,warehouse=c.wh,user=c.user,reason='CODEX UAT')


def test_expired_lot_is_never_consumed_or_counted_available(stock_case):
    c=stock_case;expired=lot(c,expires=date.today()-timedelta(days=1));valid=lot(c,qty=4,expires=date.today())
    assert c.m.inventory_available_qty(c.wh.id,c.item.id)==4
    assert c.m.inventory_on_hand_qty(c.wh.id,c.item.id)==14
    consume(c,3)
    assert expired.qty_on_hand==10 and valid.qty_on_hand==1


def test_insufficient_unexpired_or_reserved_stock_does_not_partially_consume(stock_case):
    c=stock_case;a=lot(c,qty=3,reserved=2);lot(c,expires=date.today()-timedelta(days=1))
    with pytest.raises(ValueError):consume(c,2)
    assert a.qty_on_hand==3
    assert c.m.OrderConsumableUsage.query.filter_by(order_id=c.order.id).count()==0
    assert c.m.WarehouseStockMovement.query.filter_by(reference_id=c.order.id).count()==0


@pytest.mark.parametrize('qty',['nan','inf','-inf',0,-1,'bad',1e-12])
@pytest.mark.parametrize('operation',['consume','return'])
def test_invalid_quantity_cannot_change_stock(stock_case,qty,operation):
    c=stock_case;a=lot(c)
    with pytest.raises(ValueError):(consume if operation=='consume' else give_back)(c,qty)
    assert a.qty_on_hand==10


def test_return_cannot_exceed_net_issued_or_be_repeated(stock_case):
    c=stock_case;a=lot(c)
    with pytest.raises(ValueError):give_back(c,1)
    consume(c,4);give_back(c,2);c.m.db.session.flush()
    assert a.qty_on_hand==8
    with pytest.raises(ValueError):give_back(c,3)
    give_back(c,2);c.m.db.session.flush()
    with pytest.raises(ValueError):give_back(c,1)
    assert a.qty_on_hand==10 and c.m.order_consumable_cost(c.order)==0


def test_multiple_original_lots_and_costs_are_preserved(stock_case):
    c=stock_case;a=lot(c,qty=2,expires=date.today()+timedelta(days=1),cost=5)
    b=lot(c,qty=3,expires=date.today()+timedelta(days=2),cost=7)
    consume(c,4);give_back(c,3);c.m.db.session.flush()
    assert a.qty_on_hand==2 and b.qty_on_hand==2
    returned=c.m.OrderConsumableUsage.query.filter_by(order_id=c.order.id,usage_type='RETURN').all()
    assert {(r.lot_id,r.qty,r.unit_cost) for r in returned}=={(a.id,2,5),(b.id,1,7)}
    assert c.m.order_consumable_cost(c.order)==7


def test_waste_is_not_returnable(stock_case):
    c=stock_case;a=lot(c);consume(c,2,'WASTE')
    with pytest.raises(ValueError):give_back(c,1)
    assert a.qty_on_hand==8


def test_return_of_now_expired_lot_preserves_expiry_and_remains_unavailable(stock_case):
    c=stock_case;a=lot(c);consume(c,2)
    a.expiry_date=date.today()-timedelta(days=1);c.m.db.session.flush()
    give_back(c,1);c.m.db.session.flush()
    assert a.qty_on_hand==9 and c.m.inventory_available_qty(c.wh.id,c.item.id)==0


def test_another_case_cannot_return_this_cases_stock(stock_case):
    c=stock_case;a=lot(c);consume(c,2)
    original=c.order
    o=c.m.Order(accession=uuid4().hex,patient_id=original.patient_id,branch_id=original.branch_id,
        modality='DX',procedure='CODEX UAT',scheduled=datetime(2037,2,3,11))
    c.m.db.session.add(o);c.m.db.session.flush();c.order=o
    with pytest.raises(ValueError):give_back(c,1)
    assert a.qty_on_hand==8
