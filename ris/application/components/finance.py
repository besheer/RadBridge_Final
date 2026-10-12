"""Runtime-bound application.components.finance; dependencies are supplied at composition.

Legacy behavior is preserved; new policies belong in the independent domain layer.
"""

def install_0018(_rb):
    def _orders_for_finance(f):
        q=_rb.Order.query.filter(_rb.Order.scheduled>=_rb.datetime.combine(f['start'],_rb.datetime.min.time()),
                             _rb.Order.scheduled<_rb.datetime.combine(f['end']+_rb.timedelta(days=1),_rb.datetime.min.time()))
        if f['branch_id']:q=q.filter(_rb.Order.branch_id==f['branch_id'])
        if f['contract_id']:q=q.filter(_rb.Order.contract_id==f['contract_id'])
        if f['device_id']:q=q.filter(_rb.Order.device_id==f['device_id'])
        if f['modality']:q=q.filter(_rb.Order.modality==f['modality'])
        return q.order_by(_rb.Order.scheduled.asc()).all()
    return _orders_for_finance


def install_0019(_rb):
    def _entries_for_finance(f,types=None):
        q=_rb.FinancialEntry.query.filter(_rb.FinancialEntry.entry_date>=f['start'],_rb.FinancialEntry.entry_date<=f['end'],_rb.FinancialEntry.status!='VOID')
        if f['branch_id']:q=q.filter(_rb.FinancialEntry.branch_id==f['branch_id'])
        if f['device_id']:q=q.filter(_rb.FinancialEntry.device_id==f['device_id'])
        if types:q=q.filter(_rb.FinancialEntry.entry_type.in_(types))
        return q.order_by(_rb.FinancialEntry.entry_date.asc()).all()
    return _entries_for_finance


def install_0022(_rb):
    def _financial_dataset(key,f):
        orders=_rb._orders_for_finance(f); entries=_rb._entries_for_finance(f)
        revenue=sum(_rb._order_revenue(o) for o in orders)
        collected=sum(_rb._money(o.paid_amount) for o in orders)
        receivables=sum(max(_rb.order_balance(o),0) for o in orders)
        cogs=sum(_rb._order_direct_consumable_cost(o) for o in orders)
        doctor=sum(_rb._money(e.amount) for e in entries if e.entry_type=='DOCTOR_FEE')
        opex=sum(_rb._money(e.amount) for e in entries if e.entry_type in ('EXPENSE','MAINTENANCE','PAYROLL'))
        gross_profit=revenue-cogs-doctor; net_profit=gross_profit-opex
        kpis={'Revenue':revenue,'Collections':collected,'Receivables':receivables,'Consumable COGS':cogs,
              'Doctor Fees':doctor,'Operating Expenses':opex,'Gross Profit':gross_profit,'Net Profit':net_profit,'Cases':len(orders)}
        headers=[];rows=[]

        if key=='summary':
            headers=['Metric','Value'];rows=[[k,v] for k,v in kpis.items()]
        elif key=='profit_loss':
            headers=['Line','Amount'];rows=[['Revenue',revenue],['Less: Consumable COGS',-cogs],['Less: Doctor Fees',-doctor],
            ['Gross Profit',gross_profit],['Less: Operating Expenses',-opex],['Net Profit',net_profit]]
        elif key=='balance_sheet':
            inv=sum(_rb._money(c.stock_qty)*_rb._money(c.unit_cost) for c in _rb.Consumable.query.filter_by(active=True).all())
            assets=sum(_rb._money(e.amount) for e in entries if e.entry_type=='ASSET')
            liab=sum(_rb._money(e.amount) for e in entries if e.entry_type=='LIABILITY')
            equity=sum(_rb._money(e.amount) for e in entries if e.entry_type=='EQUITY')
            total=receivables+inv+assets
            headers=['Section','Line','Amount'];rows=[
            ['Assets','Accounts Receivable',receivables],['Assets','Inventory at Cost',inv],['Assets','Registered Assets',assets],
            ['Assets','Total Assets',total],['Liabilities','Registered Liabilities',liab],['Equity','Registered Equity',equity],
            ['Equity','Calculated Net Position',total-liab]]
        elif key=='cash_flow':
            ids=[o.id for o in orders]; recs=_rb.Receipt.query.filter(_rb.Receipt.order_id.in_(ids)).all() if ids else []
            inflow=sum(_rb._money(r.amount) for r in recs)
            outflow=sum(_rb._money(e.amount) for e in entries if e.entry_type in ('EXPENSE','MAINTENANCE','PAYROLL','DOCTOR_FEE','INVENTORY_PURCHASE'))
            headers=['Cash Flow','Amount'];rows=[['Operating Inflows / Receipts',inflow],['Operating Outflows',-outflow],['Net Cash Flow',inflow-outflow]]
        elif key=='revenue_procedure':
            a={}
            for o in orders:
                k=(o.modality or '',o.proc.name if o.proc else o.procedure);v=a.setdefault(k,[0,0,0,0]);v[0]+=1;v[1]+=_rb._order_revenue(o);v[2]+=_rb._money(o.paid_amount);v[3]+=max(_rb.order_balance(o),0)
            headers=['Modality','Procedure','Cases','Revenue','Collected','Outstanding','Revenue/Case']
            rows=[[k[0],k[1],v[0],v[1],v[2],v[3],v[1]/v[0] if v[0] else 0] for k,v in sorted(a.items())]
        elif key=='revenue_payer':
            a={}
            for o in orders:
                k=o.contract.name if o.contract else 'Cash / Private';v=a.setdefault(k,[0,0,0,0,0,0]);v[0]+=1;v[1]+=_rb._order_revenue(o);v[2]+=_rb._money(o.patient_share);v[3]+=_rb._money(o.company_share);v[4]+=_rb._money(o.paid_amount);v[5]+=max(_rb.order_balance(o),0)
            headers=['Payer','Cases','Revenue','Patient Share','Company Share','Collected','Outstanding']
            rows=[[k]+v for k,v in sorted(a.items())]
        elif key=='aging':
            today=_rb.date.today();buckets={'0-30':0,'31-60':0,'61-90':0,'90+':0}
            headers=['Accession','Patient','Payer','Date','Days','0-30','31-60','61-90','90+','Balance']
            for o in orders:
                bal=max(_rb.order_balance(o),0)
                if bal<=0:continue
                days=max((today-o.scheduled.date()).days,0);bn='0-30' if days<=30 else '31-60' if days<=60 else '61-90' if days<=90 else '90+'
                buckets[bn]+=bal;x={k:0 for k in buckets};x[bn]=bal
                rows.append([o.accession,o.patient.name,o.contract.name if o.contract else 'Cash / Private',o.scheduled.date().isoformat(),days,x['0-30'],x['31-60'],x['61-90'],x['90+'],bal])
            kpis.update({f'Aging {k}':v for k,v in buckets.items()})
        elif key=='exam_costing':
            fees={}
            for e in entries:
                if e.entry_type=='DOCTOR_FEE' and e.reference_no:fees[e.reference_no]=fees.get(e.reference_no,0)+_rb._money(e.amount)
            headers=['Accession','Patient','Procedure','Revenue','Consumables','Doctor Fee','Direct Cost','Gross Profit','Margin %']
            for o in orders:
                rev=_rb._order_revenue(o);cons=_rb._order_direct_consumable_cost(o);fee=fees.get(o.accession,0);cost=cons+fee;gp=rev-cost
                rows.append([o.accession,o.patient.name,o.proc.name if o.proc else o.procedure,rev,cons,fee,cost,gp,gp/rev*100 if rev else 0])
        elif key=='maintenance':
            headers=['Date','Branch','Device','Category','Description','Amount','Reference']
            rows=[[e.entry_date.isoformat(),e.branch.name if e.branch else '',e.device.name if e.device else '',e.category,e.description,_rb._money(e.amount),e.reference_no] for e in entries if e.entry_type=='MAINTENANCE']
        elif key=='payroll_doctor':
            headers=['Date','Type','Employee / Doctor','Branch','Description','Amount','Status']
            rows=[[e.entry_date.isoformat(),e.entry_type,e.user.full_name if e.user else '',e.branch.name if e.branch else '',e.description,_rb._money(e.amount),e.status] for e in entries if e.entry_type in ('PAYROLL','DOCTOR_FEE')]
        elif key=='inventory':
            usage={}
            for o in orders:
                for n in _rb.NursingConsumableEntry.query.filter_by(order_id=o.id,confirmed=True).all():
                    if n.consumable:
                        v=usage.setdefault(n.consumable_id,[0,0]);v[0]+=float(n.actual_qty or 0);v[1]+=_rb._money(n.actual_qty)*_rb._money(n.consumable.unit_cost)
            headers=['Code','Consumable','Unit','Current Stock','Reorder Level','Used Qty','Usage Cost','Stock Value','Status']
            rows=[[c.code,c.name,c.unit,_rb._money(c.stock_qty),_rb._money(c.reorder_level),_rb._money(usage.get(c.id,[0,0])[0]),_rb._money(usage.get(c.id,[0,0])[1]),_rb._money(c.stock_qty)*_rb._money(c.unit_cost),'LOW' if _rb._money(c.stock_qty)<=_rb._money(c.reorder_level) else 'OK'] for c in _rb.Consumable.query.order_by(_rb.Consumable.name).all()]
        elif key in ('device_profitability','branch_profitability'):
            a={}
            for o in orders:
                name=(o.device.name if o.device else 'Unassigned') if key=='device_profitability' else (o.branch.name if o.branch else 'Unassigned')
                v=a.setdefault(name,[0,0,0,0]);v[0]+=1;v[1]+=_rb._order_revenue(o);v[2]+=_rb._order_direct_consumable_cost(o)
            for e in entries:
                name=(e.device.name if e.device else None) if key=='device_profitability' else (e.branch.name if e.branch else None)
                if name in a and e.entry_type in ('EXPENSE','MAINTENANCE','PAYROLL','DOCTOR_FEE'):a[name][3]+=_rb._money(e.amount)
            headers=['Unit','Cases','Revenue','Consumable Cost','Allocated Expense','Contribution','Revenue/Case']
            rows=[[name,v[0],v[1],v[2],v[3],v[1]-v[2]-v[3],v[1]/v[0] if v[0] else 0] for name,v in sorted(a.items())]
        elif key=='collections':
            ids=[o.id for o in orders];recs=_rb.Receipt.query.filter(_rb.Receipt.order_id.in_(ids)).all() if ids else [];a={}
            for r in recs:
                m=(r.payment_method or 'OTHER').upper();v=a.setdefault(m,[0,0]);v[0]+=1;v[1]+=_rb._money(r.amount)
            headers=['Payment Method','Transactions','Amount'];rows=[[m,v[0],v[1]] for m,v in sorted(a.items())]

        return {'title':_rb.FINANCIAL_REPORTS.get(key,key),'headers':headers,'rows':rows,'kpis':kpis,'filters':f}
    return _financial_dataset


def install_0065(_rb):
    def next_receipt_no():
        today=_rb.datetime.utcnow().strftime('%y%m%d')
        prefix='RC'+today
        last=_rb.Receipt.query.filter(_rb.Receipt.receipt_no.like(prefix+'%')).order_by(_rb.Receipt.id.desc()).first()
        seq=1
        if last:
            try: seq=int(last.receipt_no[-5:])+1
            except: seq=last.id+1
        return f'{prefix}{seq:05d}'
    return next_receipt_no


def install_0297(_rb):
    def approved_order_discounts(order):
        return _rb.OrderDiscount.query.filter_by(order_id=order.id,status='APPROVED').order_by(_rb.OrderDiscount.id).all()
    return approved_order_discounts


def install_0298(_rb):
    def total_order_discount(order):
        return round(sum(float(x.amount or 0) for x in _rb.approved_order_discounts(order)),2)
    return total_order_discount


def install_0301(_rb):
    def discount_policy_for(order,user=None):
        user=user or _rb.current_user()
        rows=_rb.DiscountPolicy.query.filter_by(active=True).all()
        candidates=[]
        role_code=getattr(getattr(user,'role',None),'code','') if user else ''
        for p in rows:
            if p.user_id and (not user or p.user_id!=user.id): continue
            if p.role_code and p.role_code!=role_code: continue
            if p.branch_id and p.branch_id!=order.branch_id: continue
            if p.procedure_id and p.procedure_id!=order.procedure_id: continue
            if p.contract_id and p.contract_id!=order.contract_id: continue
            score=(16 if p.user_id else 0)+(8 if p.role_code else 0)+(4 if p.procedure_id else 0)+(2 if p.contract_id else 0)+(1 if p.branch_id else 0)
            candidates.append((score,p))
        return sorted(candidates,key=lambda x:x[0],reverse=True)[0][1] if candidates else None
    return discount_policy_for


def install_0302(_rb):
    def apply_or_request_discount(order,percent,reason,user=None):
        user=user or _rb.current_user()
        percent=max(0.0,float(percent or 0))
        reason=(reason or '').strip()
        if percent<=0: return 'NONE',None
        if not reason: return 'ERROR','Discount reason is required.'
        base=_rb.base_patient_due(order)
        if base<=0: return 'ERROR','No patient due amount is available for discount.'
        policy=_rb.discount_policy_for(order,user)
        direct=float(policy.max_direct_percent or 0) if policy else 0
        request_max=float(policy.max_request_percent or 0) if policy else 0
        amount=round(base*percent/100.0,2)

        # Management/Super Admin can approve directly when granted.
        if _rb.has_perm('finance.discount.approve'):
            row=_rb.OrderDiscount(order_id=order.id,discount_type='MANUAL',percent=percent,amount=amount,base_amount=base,
                reason=reason,status='APPROVED',requested_by=user.id,approved_by=user.id,approved_at=_rb.datetime.utcnow())
            _rb.db.session.add(row);_rb.audit('DISCOUNT_APPROVED_DIRECT','order',order.id,f'{percent}% {amount:.2f} {reason}')
            return 'APPROVED',row

        if _rb.has_perm('finance.discount.apply') and percent<=direct+1e-9:
            row=_rb.OrderDiscount(order_id=order.id,discount_type='MANUAL',percent=percent,amount=amount,base_amount=base,
                reason=reason,status='APPROVED',requested_by=user.id,approved_by=user.id,approved_at=_rb.datetime.utcnow())
            _rb.db.session.add(row);_rb.audit('DISCOUNT_APPLIED','order',order.id,f'{percent}% {amount:.2f} {reason}')
            return 'APPROVED',row

        if _rb.has_perm('finance.discount.request') and percent<=request_max+1e-9 and request_max>0:
            pending=_rb.DiscountApprovalRequest.query.filter_by(order_id=order.id,status='PENDING',requested_by=user.id).first()
            if pending:
                pending.requested_percent=percent;pending.requested_amount=amount;pending.reason=reason;pending.requested_at=_rb.datetime.utcnow()
            else:
                pending=_rb.DiscountApprovalRequest(order_id=order.id,requested_percent=percent,requested_amount=amount,
                    reason=reason,status='PENDING',requested_by=user.id)
                _rb.db.session.add(pending)
            _rb.audit('DISCOUNT_APPROVAL_REQUEST','order',order.id,f'{percent}% {amount:.2f} {reason}')
            return 'PENDING',pending

        if request_max and percent>request_max:
            return 'ERROR',f'Request exceeds your maximum allowed discount request ({request_max:.2f}%).'
        return 'ERROR','You do not have permission/policy to apply this discount.'
    return apply_or_request_discount


def install_0312(_rb):
    def referral_commission_for_order(order):
        if not order.referring_doctor_id: return 0.0,None
        candidates=[]
        for r in _rb.ReferralCommissionRule.query.filter_by(referrer_id=order.referring_doctor_id,active=True).all():
            if r.branch_id and r.branch_id!=order.branch_id: continue
            if r.modality and r.modality!=order.modality: continue
            if r.procedure_id and r.procedure_id!=getattr(order,'procedure_id',None): continue
            score=(4 if r.procedure_id else 0)+(2 if r.modality else 0)+(1 if r.branch_id else 0)
            candidates.append((score,r))
        if not candidates: return 0.0,None
        rule=sorted(candidates,key=lambda x:x[0],reverse=True)[0][1]
        base=float(getattr(order,'contract_price',0) or getattr(order,'gross_price',0) or 0)
        val=float(rule.value or 0)
        return round(base*val/100.0 if rule.rule_type=='PERCENT' else val,2),rule
    return referral_commission_for_order


def install_0313(_rb):
    def daily_payment_totals(branch_id,closing_date):
        from daily_closing_policy import payment_totals
        return payment_totals(branch_id,closing_date)
    return daily_payment_totals


def install_0324(_rb):
    def receipt_studio_template(order):
        q=_rb.StudioTemplate.query.filter_by(template_type='RECEIPT',status='PUBLISHED')
        branch_id=getattr(order,'branch_id',None)
        if branch_id:
            scoped=q.filter(_rb.or_(_rb.StudioTemplate.branch_id==branch_id,_rb.StudioTemplate.branch_id.is_(None))).order_by(
                _rb.StudioTemplate.branch_id.desc(),_rb.StudioTemplate.id.desc()
            ).first()
            if scoped: return scoped
        return q.order_by(_rb.StudioTemplate.id.desc()).first()
    return receipt_studio_template

