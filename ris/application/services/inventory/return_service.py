"""Original-lot return orchestration with explicit repository and movement ports.

Callers own commit/rollback. This service neither invents lots nor permits a
return exceeding the net quantity previously issued to this case.
"""
from domain.inventory.return_policy import quantity, return_credits

def return_to_original_lots(repository, default_warehouse, current_user, move, order, item, qty, warehouse=None, reason='', user=None):
    qty=quantity(qty)
    warehouse=warehouse or default_warehouse(order)
    if not warehouse:
        raise ValueError('No active warehouse is configured for this branch.')
    user=user or current_user()
    repository.lock_order(order.id)
    rows=repository.usage_rows(order.id,warehouse.id,item.id)
    credits=return_credits(rows)
    if qty>sum(credits.values())+1e-9:
        raise ValueError('Return exceeds the remaining quantity issued to this case. / كمية الإرجاع أكبر من صافي المصروف للحالة.')
    ids={key[0] for key,amount in credits.items() if amount>1e-9}
    lots=repository.locked_lots(ids,warehouse.id,item.id)
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
            movement=move(warehouse,item,take,'RETURN',lot=lot,
                reference_type='ORDER',reference_id=order.id,notes=reason,user=user)
            movement.unit_cost=cost
            usage=repository.create_usage(order_id=order.id,warehouse_id=warehouse.id,
                item_id=item.id,lot_id=lot.id,qty=take,usage_type='RETURN',source='MANUAL',
                reason=reason,unit_cost=cost,created_by=user.id)
            repository.add(usage);result.append(usage);remaining-=take
    return result[0]
