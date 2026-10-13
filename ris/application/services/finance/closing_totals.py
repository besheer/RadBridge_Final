"""Net receipt/refund totals for one supplied branch/date repository."""
from datetime import datetime, timedelta
from domain.finance.closing_policy import net_payment_totals


def payment_totals(*, repository, branch_id, closing_date):
    start = datetime.combine(closing_date, datetime.min.time())
    end = start + timedelta(days=1)
    receipts = repository.receipts(branch_id, start, end)
    refunds = repository.refunds(branch_id, start, end)
    return net_payment_totals(receipts, refunds)
