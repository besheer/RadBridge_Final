"""Runtime-bound web.routes.finance; dependencies are supplied at composition.

Legacy behavior is preserved; new policies belong in the independent domain layer.
"""

def install_0167(_rb):
    @_rb.app.route('/payments/<int:order_id>',methods=['POST'])
    @_rb.require_perm('payments.create')
    def add_payment(order_id):
        # Both collection entrances issue an auditable receipt through one handler.
        return _rb.receive_payment(order_id)
    return add_payment


def install_0515(_rb):
    @_rb.app.route('/accounting/financial-center')
    @_rb.require_perm('financial.view')
    def financial_center():
        key=(_rb.request.args.get('report') or 'summary').strip()
        if key not in _rb.FINANCIAL_REPORTS:key='summary'
        d=_rb._financial_dataset(key,_rb._finance_filters())
        return _rb.render_template('financial_center.html',dataset=d,report_key=key,reports=_rb.FINANCIAL_REPORTS,
          branches=_rb.Branch.query.order_by(_rb.Branch.name).all(),contracts=_rb.Contract.query.order_by(_rb.Contract.name).all(),
          devices=_rb.Device.query.order_by(_rb.Device.modality,_rb.Device.name).all(),
          modalities=sorted({x[0] for x in _rb.db.session.query(_rb.Procedure.modality).distinct().all() if x[0]}))
    return financial_center


def install_0516(_rb):
    @_rb.app.route('/accounting/financial-center/export/<fmt>')
    @_rb.require_perm('export.view')
    def financial_center_export(fmt):
        key=(_rb.request.args.get('report') or 'summary').strip()
        if key not in _rb.FINANCIAL_REPORTS:_rb.abort(400)
        d=_rb._financial_dataset(key,_rb._finance_filters());name=f"{key}-{d['filters']['start']}-{d['filters']['end']}"
        if fmt=='csv':return _rb._export_csv(d,name)
        if fmt=='xlsx':return _rb._export_xlsx(d,name)
        if fmt=='pdf':return _rb._export_pdf(d,name)
        _rb.abort(400)
    return financial_center_export


def install_0517(_rb):
    @_rb.app.route('/accounting/entries',methods=['GET','POST'])
    @_rb.require_perm('financial.view')
    def financial_entries():
        if _rb.request.method=='POST':
            typ=(_rb.request.form.get('entry_type') or '').upper().strip()
            if typ not in _rb.FINANCE_ENTRY_TYPES:_rb.flash('Invalid entry type.','danger');return _rb.redirect(_rb.url_for('financial_entries'))
            if typ=='DOCTOR_FEE':
                from replacement_settlements import guard_case_payout
                guard_case_payout(_rb._reporting_support_sys.modules[_rb.__name__],_rb.request.form.get('branch_id',type=int),
                    _rb.request.form.get('user_id',type=int),_rb.request.form.get('reference_no'))
            try:amount=float(_rb.request.form.get('amount') or 0)
            except:amount=0
            try:ed=_rb.date.fromisoformat(_rb.request.form.get('entry_date') or _rb.date.today().isoformat())
            except:ed=_rb.date.today()
            row=_rb.FinancialEntry(entry_date=ed,branch_id=_rb.request.form.get('branch_id',type=int),entry_type=typ,
              category=(_rb.request.form.get('category') or '').strip(),description=(_rb.request.form.get('description') or '').strip(),
              amount=max(amount,0),payment_method=(_rb.request.form.get('payment_method') or '').upper().strip(),
              device_id=_rb.request.form.get('device_id',type=int),user_id=_rb.request.form.get('user_id',type=int),
              consumable_id=_rb.request.form.get('consumable_id',type=int),quantity=float(_rb.request.form.get('quantity') or 0),
              reference_no=(_rb.request.form.get('reference_no') or '').strip(),notes=(_rb.request.form.get('notes') or '').strip(),created_by=_rb.current_user().id)
            _rb.db.session.add(row);_rb.audit('FINANCIAL_ENTRY_CREATE','financial_entry','',f'{typ} {amount}');_rb.db.session.commit();_rb.flash('Financial entry saved.','success')
            return _rb.redirect(_rb.url_for('financial_entries'))
        return _rb.render_template('financial_entries.html',rows=_rb.FinancialEntry.query.order_by(_rb.FinancialEntry.entry_date.desc(),_rb.FinancialEntry.id.desc()).limit(1000).all(),
          types=_rb.FINANCE_ENTRY_TYPES,branches=_rb.Branch.query.order_by(_rb.Branch.name).all(),devices=_rb.Device.query.order_by(_rb.Device.modality,_rb.Device.name).all(),
          users=_rb.User.query.filter_by(active=True).order_by(_rb.User.full_name).all(),consumables=_rb.Consumable.query.filter_by(active=True).order_by(_rb.Consumable.name).all())
    return financial_entries


def install_0518(_rb):
    @_rb.app.post('/accounting/entries/<int:entry_id>/void')
    @_rb.require_perm('financial.view')
    def financial_entry_void(entry_id):
        row=_rb.FinancialEntry.query.get_or_404(entry_id);reason=(_rb.request.form.get('reason') or '').strip()
        if len(reason)<5:_rb.flash('Void reason is required.','danger');return _rb.redirect(_rb.url_for('financial_entries'))
        row.status='VOID';row.notes=((row.notes or '')+' | VOID: '+reason).strip();_rb.audit('FINANCIAL_ENTRY_VOID','financial_entry',row.id,reason);_rb.db.session.commit()
        _rb.flash('Entry voided; history retained.','warning');return _rb.redirect(_rb.url_for('financial_entries'))
    return financial_entry_void


def install_0521(_rb):
    @_rb.app.route('/orders/<int:order_id>/payment',methods=['POST'])
    @_rb.require_perm('payments.create')
    def receive_payment(order_id):
        from collection_policy import require_collection_branch
        o=_rb.Order.query.filter_by(id=order_id).with_for_update().first_or_404()
        require_collection_branch(o.branch_id)
        discount_percent=float(_rb.request.form.get('discount_percent') or 0)
        import math
        if not math.isfinite(discount_percent) or discount_percent<0 or discount_percent>100:
            _rb.abort(400,description='Invalid discount')
        discount_reason=(_rb.request.form.get('discount_reason') or '').strip()
        if discount_percent>0:
            status,obj=_rb.apply_or_request_discount(o,discount_percent,discount_reason)
            if status=='ERROR':
                _rb.flash(str(obj),'danger'); _rb.db.session.rollback(); return _rb.redirect(_rb.request.referrer or _rb.url_for('order_detail',order_id=o.id))
            if status=='PENDING':
                _rb.db.session.commit()
                _rb.flash('Discount approval requested. Payment was not collected until management approval.','warning')
                return _rb.redirect(_rb.request.referrer or _rb.url_for('order_detail',order_id=o.id))
            _rb.db.session.flush()

        amount=float(_rb.request.form.get('amount') or 0)
        balance=max(0.0,_rb.order_balance(o))
        if not math.isfinite(amount) or amount<=0:
            _rb.flash('Payment amount must be greater than zero.','danger'); _rb.db.session.rollback(); return _rb.redirect(_rb.request.referrer or _rb.url_for('order_detail',order_id=o.id))
        if amount>balance+0.01:
            _rb.flash(f'Payment exceeds current balance ({balance:.2f}).','danger'); _rb.db.session.rollback(); return _rb.redirect(_rb.request.referrer or _rb.url_for('order_detail',order_id=o.id))
        method=(_rb.request.form.get('payment_method') or _rb.request.form.get('method') or 'CASH').upper()
        if method not in ('CASH','VISA','MASTERCARD','WALLET','BANK_TRANSFER'):_rb.abort(400)
        ref=(_rb.request.form.get('reference_no') or _rb.request.form.get('reference') or '').strip()
        r=_rb.Receipt(receipt_no=_rb.next_receipt_no(),order_id=o.id,amount=amount,payment_method=method,
            reference_no=ref,created_by=_rb.current_user().id,notes=_rb.request.form.get('notes',''))
        _rb.db.session.add(r)
        _rb.db.session.add(_rb.Payment(order_id=o.id,amount=amount,method=method,reference=ref,created_by=_rb.current_user().id))
        o.paid_amount=round(float(o.paid_amount or 0)+amount,2)
        _rb.audit('PAYMENT_RECEIVED','order',o.id,f'{r.receipt_no} {amount} {method}; discount={discount_percent}')
        _rb.db.session.commit()
        _rb.flash(f'Payment received. Receipt {r.receipt_no}','success')
        return _rb.redirect(_rb.request.referrer or _rb.url_for('order_detail',order_id=o.id))
    return receive_payment


def install_0522(_rb):
    @_rb.app.route('/receipts/<int:receipt_id>')
    @_rb.login_required
    def receipt_view(receipt_id):
        r=_rb.Receipt.query.get_or_404(receipt_id)
        from collection_policy import require_collection_branch
        require_collection_branch(r.order.branch_id)
        if not (_rb.has_perm('receipts.print') or _rb.has_perm('payments.create') or _rb.has_perm('financial.view') or _rb.has_perm('*')): _rb.abort(403)
        return _rb.render_template('receipt.html',receipt=r,order=r.order)
    return receipt_view


def install_0524(_rb):
    @_rb.app.route('/cashier')
    @_rb.require_perm('cashier.workstation')
    def cashier_workstation():
        q=(_rb.request.args.get('q') or '').strip()
        query=_rb.Order.query.join(_rb.Patient)
        user=_rb.current_user()
        if user.role and user.role.code in ('RECEPTION','CASHIER'):
            if not user.branch_id:_rb.abort(403)
            query=query.filter(_rb.Order.branch_id==user.branch_id)
        if q:
            query=query.filter(_rb.or_(
                _rb.Order.accession.ilike(f'%{q}%'),
                _rb.Patient.patient_id.ilike(f'%{q}%'),
                _rb.Patient.name.ilike(f'%{q}%'),
                _rb.Patient.phone.ilike(f'%{q}%')
            ))
        rows=query.order_by(_rb.Order.id.desc()).limit(300).all()
        payments={o.id:_rb.Payment.query.filter_by(order_id=o.id).order_by(_rb.Payment.created_at.desc()).all() for o in rows}
        refunds={}
        for o in rows:
            refunds[o.id]=_rb.PaymentRefund.query.filter_by(order_id=o.id).order_by(_rb.PaymentRefund.created_at.desc()).all()
        discount_ctx={o.id:{'due':_rb.effective_patient_due(o),'discount':_rb.total_order_discount(o),'policy':_rb.discount_policy_for(o)} for o in rows}
        return _rb.render_template('cashier.html',orders=rows,payments=payments,refunds=refunds,q=q,discount_ctx=discount_ctx)
    return cashier_workstation


def install_0525(_rb):
    @_rb.app.post('/payments/<int:payment_id>/refund')
    @_rb.require_perm('payments.refund')
    def refund_payment(payment_id):
        p=_rb.Payment.query.get_or_404(payment_id)
        o=p.order
        from collection_policy import require_collection_branch
        require_collection_branch(o.branch_id)
        amount=float(_rb.request.form.get('amount') or 0)
        reason=(_rb.request.form.get('reason') or '').strip()
        reference=(_rb.request.form.get('reference') or '').strip()

        already=sum(float(x.amount or 0) for x in _rb.PaymentRefund.query.filter_by(payment_id=p.id).all())
        refundable=max(0.0,float(p.amount or 0)-already)

        if amount<=0 or amount>refundable+0.001:
            _rb.flash(f'Invalid refund amount. Maximum refundable is {refundable:.2f}.','danger')
            return _rb.redirect(_rb.request.referrer or _rb.url_for('cashier_workstation'))
        if not reason:
            _rb.flash('Refund reason is required.','danger')
            return _rb.redirect(_rb.request.referrer or _rb.url_for('cashier_workstation'))

        r=_rb.PaymentRefund(
            payment_id=p.id,order_id=o.id,amount=amount,reason=reason,
            reference=reference,created_by=_rb.current_user().id
        )
        _rb.db.session.add(r)
        o.paid_amount=max(0.0,round(float(o.paid_amount or 0)-amount,2))

        if abs(refundable-amount)<0.001:
            p.status='REFUNDED'
        else:
            p.status='PARTIAL_REFUND'

        _rb.audit('PAYMENT_REFUND','order',o.id,
              f'payment={p.id}; amount={amount}; reason={reason}; reference={reference}')
        _rb.db.session.commit()
        _rb.flash(f'Refund {amount:.2f} completed.','success')
        return _rb.redirect(_rb.request.referrer or _rb.url_for('cashier_workstation'))
    return refund_payment


def install_0656(_rb):
    @_rb.app.get('/receipts/<int:receipt_id>/studio-print')
    @_rb.login_required
    def receipt_studio_print(receipt_id):
        receipt=_rb.Receipt.query.get_or_404(receipt_id)
        order=receipt.order
        from collection_policy import require_collection_branch
        require_collection_branch(order.branch_id)
        template=_rb.receipt_studio_template(order)
        legal=_rb.company_legal_for_order(order)
        layout={}
        if template:
            try: layout=_rb.json.loads(template.layout_json or '{}')
            except Exception: layout={}
        return _rb.render_template('receipt_studio_print.html',
            receipt=receipt,order=order,template=template,legal=legal,layout=layout)
    return receipt_studio_print


def install_0775(_rb):
    @_rb.app.route('/admin/referral-commissions',methods=['GET','POST'])
    @_rb.require_perm('users.view')
    def admin_referral_commissions():
        if _rb.request.method=='POST':
            rid=_rb.request.form.get('referrer_id',type=int)
            if not rid: _rb.flash('Select referring doctor.','danger'); return _rb.redirect(_rb.url_for('admin_referral_commissions'))
            row=_rb.ReferralCommissionRule(referrer_id=rid,branch_id=_rb.request.form.get('branch_id',type=int),modality=(_rb.request.form.get('modality') or '').strip().upper(),procedure_id=_rb.request.form.get('procedure_id',type=int),rule_type=(_rb.request.form.get('rule_type') or 'PERCENT').upper(),value=_rb.request.form.get('value',type=float) or 0,active=_rb.request.form.get('active')=='1',created_by=_rb.current_user().id)
            _rb.db.session.add(row);_rb.db.session.commit();_rb.audit('REFERRAL_COMMISSION_CREATE','referral_commission',row.id,str(row.value))
            return _rb.redirect(_rb.url_for('admin_referral_commissions'))
        return _rb.render_template('admin_referral_commissions.html',rows=_rb.ReferralCommissionRule.query.order_by(_rb.ReferralCommissionRule.id.desc()).all(),referrers=_rb.ReferringDoctor.query.filter_by(active=True).order_by(_rb.ReferringDoctor.name).all(),branches=_rb.Branch.query.filter_by(active=True).order_by(_rb.Branch.name).all(),procedures=_rb.Procedure.query.filter_by(active=True).order_by(_rb.Procedure.modality,_rb.Procedure.name).all())
    return admin_referral_commissions


def install_0776(_rb):
    @_rb.app.route('/accounting/daily-closing',methods=['GET','POST'])
    @_rb.login_required
    def daily_closing():
        from daily_closing_policy import closing_page
        return closing_page()
    return daily_closing


def install_0777(_rb):
    @_rb.app.route('/admin/doctor-share-rules',methods=['GET','POST'])
    @_rb.require_perm('finance.doctor_share.manage')
    def admin_doctor_share_rules():
        if _rb.request.method=='POST':
            doctor_id=_rb.request.form.get('doctor_user_id',type=int)
            if not doctor_id:
                _rb.flash('Select doctor.','danger')
                return _rb.redirect(_rb.url_for('admin_doctor_share_rules'))
            row=_rb.PerformingDoctorShareRule(
                doctor_user_id=doctor_id,
                branch_id=_rb.request.form.get('branch_id',type=int),
                modality=(_rb.request.form.get('modality') or '').strip().upper(),
                procedure_id=_rb.request.form.get('procedure_id',type=int),
                contract_id=_rb.request.form.get('contract_id',type=int),
                rule_type=(_rb.request.form.get('rule_type') or 'PERCENT').upper(),
                basis=(_rb.request.form.get('basis') or 'NET_AFTER_DISCOUNT').upper(),
                value=max(0.0,_rb.request.form.get('value',type=float) or 0),
                active=_rb.request.form.get('active')=='1',
                created_by=_rb.current_user().id
            )
            _rb.db.session.add(row);_rb.db.session.commit()
            _rb.audit('DOCTOR_SHARE_RULE_CREATE','doctor_share_rule',row.id,f'{doctor_id} {row.rule_type} {row.value}')
            return _rb.redirect(_rb.url_for('admin_doctor_share_rules'))
        return _rb.render_template('admin_doctor_share_rules.html',
            rows=_rb.PerformingDoctorShareRule.query.order_by(_rb.PerformingDoctorShareRule.id.desc()).all(),
            doctors=_rb.User.query.filter_by(active=True).order_by(_rb.User.full_name).all(),
            branches=_rb.Branch.query.filter_by(active=True).order_by(_rb.Branch.name).all(),
            procedures=_rb.Procedure.query.filter_by(active=True).order_by(_rb.Procedure.modality,_rb.Procedure.name).all(),
            contracts=_rb.Contract.query.filter_by(active=True).order_by(_rb.Contract.name).all())
    return admin_doctor_share_rules


def install_0778(_rb):
    @_rb.app.post('/admin/doctor-share-rules/<int:rule_id>/toggle')
    @_rb.require_perm('finance.doctor_share.manage')
    def doctor_share_rule_toggle(rule_id):
        row=_rb.PerformingDoctorShareRule.query.get_or_404(rule_id)
        row.active=not row.active;_rb.db.session.commit()
        _rb.audit('DOCTOR_SHARE_RULE_TOGGLE','doctor_share_rule',row.id,str(row.active))
        return _rb.redirect(_rb.url_for('admin_doctor_share_rules'))
    return doctor_share_rule_toggle


def install_0780(_rb):
    @_rb.app.route('/admin/discount-policies',methods=['GET','POST'])
    @_rb.require_perm('finance.discount.manage')
    def admin_discount_policies():
        if _rb.request.method=='POST':
            row=_rb.DiscountPolicy(
                name=(_rb.request.form.get('name') or 'Discount Policy').strip(),
                role_code=(_rb.request.form.get('role_code') or '').strip().upper(),
                user_id=_rb.request.form.get('user_id',type=int),
                branch_id=_rb.request.form.get('branch_id',type=int),
                procedure_id=_rb.request.form.get('procedure_id',type=int),
                contract_id=_rb.request.form.get('contract_id',type=int),
                max_direct_percent=max(0.0,_rb.request.form.get('max_direct_percent',type=float) or 0),
                max_request_percent=max(0.0,_rb.request.form.get('max_request_percent',type=float) or 0),
                active=_rb.request.form.get('active')=='1',
                created_by=_rb.current_user().id
            )
            if row.max_request_percent<row.max_direct_percent:
                row.max_request_percent=row.max_direct_percent
            _rb.db.session.add(row);_rb.db.session.commit()
            _rb.audit('DISCOUNT_POLICY_CREATE','discount_policy',row.id,row.name)
            return _rb.redirect(_rb.url_for('admin_discount_policies'))
        return _rb.render_template('admin_discount_policies.html',
            rows=_rb.DiscountPolicy.query.order_by(_rb.DiscountPolicy.id.desc()).all(),
            roles=_rb.Role.query.order_by(_rb.Role.name).all(),
            users=_rb.User.query.filter_by(active=True).order_by(_rb.User.full_name).all(),
            branches=_rb.Branch.query.filter_by(active=True).order_by(_rb.Branch.name).all(),
            procedures=_rb.Procedure.query.filter_by(active=True).order_by(_rb.Procedure.modality,_rb.Procedure.name).all(),
            contracts=_rb.Contract.query.filter_by(active=True).order_by(_rb.Contract.name).all())
    return admin_discount_policies


def install_0781(_rb):
    @_rb.app.post('/admin/discount-policies/<int:policy_id>/toggle')
    @_rb.require_perm('finance.discount.manage')
    def discount_policy_toggle(policy_id):
        row=_rb.DiscountPolicy.query.get_or_404(policy_id)
        row.active=not row.active;_rb.db.session.commit()
        _rb.audit('DISCOUNT_POLICY_TOGGLE','discount_policy',row.id,str(row.active))
        return _rb.redirect(_rb.url_for('admin_discount_policies'))
    return discount_policy_toggle


def install_0782(_rb):
    @_rb.app.get('/finance/discount-approvals')
    @_rb.require_perm('finance.discount.approve')
    def discount_approval_queue():
        rows=_rb.DiscountApprovalRequest.query.order_by(
            _rb.db.case((_rb.DiscountApprovalRequest.status=='PENDING',0),else_=1),
            _rb.DiscountApprovalRequest.requested_at.desc()
        ).limit(500).all()
        return _rb.render_template('discount_approval_queue.html',rows=rows)
    return discount_approval_queue


def install_0783(_rb):
    @_rb.app.post('/finance/discount-approvals/<int:req_id>/decision')
    @_rb.require_perm('finance.discount.approve')
    def discount_approval_decision(req_id):
        row=_rb.DiscountApprovalRequest.query.get_or_404(req_id)
        if row.status!='PENDING':
            _rb.flash('Request already decided.','warning')
            return _rb.redirect(_rb.url_for('discount_approval_queue'))
        action=(_rb.request.form.get('action') or '').upper()
        notes=(_rb.request.form.get('decision_notes') or '').strip()
        row.decided_by=_rb.current_user().id;row.decided_at=_rb.datetime.utcnow();row.decision_notes=notes
        if action=='APPROVE':
            base=_rb.base_patient_due(row.order)
            amount=round(base*float(row.requested_percent or 0)/100.0,2)
            disc=_rb.OrderDiscount(order_id=row.order_id,discount_type='APPROVED_REQUEST',
                percent=row.requested_percent,amount=amount,base_amount=base,reason=row.reason,
                status='APPROVED',requested_by=row.requested_by,approved_by=_rb.current_user().id,approved_at=_rb.datetime.utcnow())
            _rb.db.session.add(disc);row.status='APPROVED'
            _rb.audit('DISCOUNT_REQUEST_APPROVED','order',row.order_id,f'{row.requested_percent}% {amount:.2f}')
        else:
            row.status='REJECTED'
            _rb.audit('DISCOUNT_REQUEST_REJECTED','order',row.order_id,f'{row.requested_percent}% {notes}')
        _rb.db.session.commit()
        return _rb.redirect(_rb.url_for('discount_approval_queue'))
    return discount_approval_decision
