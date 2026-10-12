"""Existing decimal and receipt/refund reconciliation rules."""
from decimal import Decimal, InvalidOperation

def money(value):
    try:
        amount = Decimal(str(value or 0))
        if not amount.is_finite():
            raise ValueError('Non-finite amount')
        return amount.quantize(Decimal('0.01'))
    except (InvalidOperation, ValueError):
        raise ValueError('Enter valid counted amounts. / أدخل مبالغ جرد صحيحة.') from None


def net_payment_totals(receipts, refunds):
    totals = {key: Decimal('0') for key in ('CASH', 'CARD', 'OTHER')}
    for rows, sign in ((receipts, 1), (refunds, -1)):
        for row in rows:
            payment = row if sign == 1 else row.payment
            if payment is None or (sign == -1 and payment.order_id != row.order_id):
                raise ValueError('Refund receipt mismatch; accounting review required.')
            method = (payment.method or '').upper()
            bucket = 'CASH' if method == 'CASH' else 'CARD' if method in (
                'VISA', 'MASTERCARD', 'CARD', 'POS') else 'OTHER'
            totals[bucket] += sign * money(row.amount)
    return {key: float(value) for key, value in totals.items()}
