"""Finite quantity and original-lot return credit validation."""
import math

def quantity(value):
    try:
        result=float(value)
    except (TypeError,ValueError):
        result=0
    if not math.isfinite(result) or result<=1e-9:
        raise ValueError('Quantity must be a finite positive number. / يجب أن تكون الكمية رقمًا موجبًا صحيحًا.')
    return result


def return_credits(rows):
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
    return credits
