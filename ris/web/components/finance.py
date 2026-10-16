"""Runtime-bound web.components.finance; dependencies are supplied at composition.

Legacy behavior is preserved; new policies belong in the independent domain layer.
"""

def install_0017(_rb):
    def _finance_filters():
        today=_rb.date.today(); start=today.replace(day=1); end=today
        try:
            if _rb.request.args.get('start'): start=_rb.date.fromisoformat(_rb.request.args.get('start'))
        except: pass
        try:
            if _rb.request.args.get('end'): end=_rb.date.fromisoformat(_rb.request.args.get('end'))
        except: pass
        if end<start:start,end=end,start
        return {'start':start,'end':end,'branch_id':_rb.request.args.get('branch_id',type=int),
                'contract_id':_rb.request.args.get('contract_id',type=int),
                'device_id':_rb.request.args.get('device_id',type=int),
                'modality':(_rb.request.args.get('modality') or '').upper().strip()}
    return _finance_filters


def install_0415(_rb):
    def _rb_v5462_payment(orders,form):
        import math
        from collection_policy import require_collection_branch
        amount=float(form.get('payment_amount') or 0)
        if not math.isfinite(amount):raise ValueError('Invalid payment amount.')
        if amount<=0: return
        if not _rb.has_perm('payments.create'): _rb.abort(403)
        for o in orders:require_collection_branch(o.branch_id,runtime=_rb)
        method=(form.get('payment_method') or '').strip().upper()
        if method not in ('CASH','VISA','MASTERCARD','WALLET','BANK_TRANSFER'):raise ValueError('Select payment method.')
        total_due=sum(max(0,float(o.patient_share or 0)) for o in orders)
        if amount>total_due+0.01:
            raise ValueError(f'Payment exceeds patient total due ({total_due:.2f}).')
        left=amount
        for o in orders:
            if left<=0: break
            due=max(0,float(o.patient_share or 0))
            part=min(left,due)
            if part<=0: continue
            _rb.db.session.add(_rb.Payment(
                order_id=o.id,amount=part,method=method,
                reference=(form.get('payment_reference') or '').strip(),
                created_by=_rb.current_user().id
            ))
            _rb.db.session.add(_rb.Receipt(receipt_no=_rb.next_receipt_no(),order_id=o.id,amount=part,payment_method=method,reference_no=(form.get('payment_reference') or '').strip(),created_by=_rb.current_user().id))
            _rb.db.session.flush()
            _rb.audit('PAYMENT_RECEIVED','order',o.id,'Registration collection; amount='+str(part))
            o.paid_amount=float(o.paid_amount or 0)+part
            left=round(left-part,2)
    return _rb_v5462_payment
