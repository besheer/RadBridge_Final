"""Finite quantities and lot-preserving order returns; callers own transactions."""
import math


def quantity(value):
    try:
        result=float(value)
    except (TypeError,ValueError):
        result=0
    if not math.isfinite(result) or result<=1e-9:
        raise ValueError('Quantity must be a finite positive number. / يجب أن تكون الكمية رقمًا موجبًا صحيحًا.')
    return result


def lock_order(order):
    import app as m
    if not m.Order.query.filter_by(id=order.id).with_for_update().first():
        raise ValueError('Order not found.')


def return_to_original_lots(order,item,qty,warehouse=None,reason='',user=None):
    import app as m
    qty=quantity(qty)
    warehouse=warehouse or m.default_warehouse_for_order(order)
    if not warehouse:
        raise ValueError('No active warehouse is configured for this branch.')
    user=user or m.current_user()
    lock_order(order)
    rows=m.OrderConsumableUsage.query.filter_by(order_id=order.id,warehouse_id=warehouse.id,
        item_id=item.id).order_by(m.OrderConsumableUsage.id).all()
    consumed={};returned={}
    for row in rows:
        if row.usage_type not in ('USED','EXTRA','RETURN'):
            continue
        if not row.lot_id:
            raise ValueError('Original lot is missing; inventory review is required.')
        key=(row.lot_id,float(row.unit_cost or 0))
        target=returned if row.usage_type=='RETURN' else consumed
        target[key]=target.get(key,0)+quantity(row.qty)
    if any(key not in consumed or amount>consumed[key]+1e-9 for key,amount in returned.items()):
        raise ValueError('Previous returns do not match original usage; inventory review is required.')
    credits={key:amount-returned.get(key,0) for key,amount in consumed.items()}
    if qty>sum(credits.values())+1e-9:
        raise ValueError('Return exceeds the remaining quantity issued to this case. / كمية الإرجاع أكبر من صافي المصروف للحالة.')
    ids={key[0] for key,amount in credits.items() if amount>1e-9}
    lots=m.InventoryLot.query.filter(m.InventoryLot.id.in_(ids),m.InventoryLot.warehouse_id==warehouse.id,
        m.InventoryLot.item_id==item.id).order_by(
            m.db.case((m.InventoryLot.expiry_date.is_(None),1),else_=0),
            m.InventoryLot.expiry_date,m.InventoryLot.id).populate_existing().with_for_update().all()
    if {lot.id for lot in lots}!=ids:
        raise ValueError('Original lot does not match the item and warehouse.')
    remaining=qty;result=[]
    for lot in lots:
        for (lot_id,cost),credit in credits.items():
            if lot_id!=lot.id or credit<=1e-9:
                continue
            take=min(credit,remaining)
            if take<=1e-9:
                break
            movement=m.inventory_move(warehouse,item,take,'RETURN',lot=lot,
                reference_type='ORDER',reference_id=order.id,notes=reason,user=user)
            movement.unit_cost=cost
            usage=m.OrderConsumableUsage(order_id=order.id,warehouse_id=warehouse.id,
                item_id=item.id,lot_id=lot.id,qty=take,usage_type='RETURN',source='MANUAL',
                reason=reason,unit_cost=cost,created_by=user.id)
            m.db.session.add(usage);result.append(usage);remaining-=take
    return result[0]
