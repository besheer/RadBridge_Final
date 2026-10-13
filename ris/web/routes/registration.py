"""Runtime-bound web.routes.registration; dependencies are supplied at composition.

Legacy behavior is preserved; new policies belong in the independent domain layer.
"""

def install_0150(_rb):
    @_rb.app.route('/patients')
    @_rb.require_perm('patients.view')
    def patients():
        q=_rb.request.args.get('q','').strip(); query=_rb.Patient.query
        if q: query=query.filter(_rb.or_(_rb.Patient.name.ilike(f'%{q}%'),_rb.Patient.patient_id.ilike(f'%{q}%'),_rb.Patient.phone.ilike(f'%{q}%'),_rb.Patient.national_id.ilike(f'%{q}%')))
        # RB_SMART_BOOKING_V2_PATIENTS_CONTEXT_V1
        return _rb.render_template(
            'patients.html',
            patients=query.order_by(_rb.Patient.id.desc()).limit(300).all(),
            q=q,
            smart_booking_branches=_rb.Branch.query.filter_by(active=True).order_by(_rb.Branch.name).all(),
            # RB_SMART_BOOKING_V2_JSON_CONTEXT_V1
            smart_booking_procedures=[
                {
                    'id':p.id,
                    'code':p.code or '',
                    'name':p.name or '',
                    'name_ar':p.name_ar or '',
                    'modality':p.modality or '',
                    'duration_min':int(p.duration_min or 20),
                }
                for p in _rb.Procedure.query.filter_by(active=True).order_by(
                    _rb.Procedure.modality,
                    _rb.Procedure.name
                ).all()
            ],
            smart_booking_procedure_branches=[
                {
                    'branch_id':row.branch_id,
                    'procedure_id':row.procedure_id,
                    'active':bool(row.active),
                }
                for row in _rb.ProcedureBranch.query.filter_by(active=True).all()
            ],
        )
    return patients


def install_0151(_rb):
    @_rb.app.route('/patients/new',methods=['GET','POST'])
    @_rb.require_perm('patients.create')
    def new_patient():
        # v5.46.3: one visible registration entry point.
        if _rb.request.method=='GET':
            return _rb.redirect(_rb.url_for('schedule_calendar',open_registration='1'))

        if _rb.request.method=='POST':
            name=_rb.request.form['name'].strip()
            try:
                dob_resolution=_rb.resolve_patient_dob(_rb.request.form, prefix='')
            except ValueError as exc:
                _rb.flash(str(exc), 'danger')
                return _rb.render_template(
                    'patient_form.html',
                    duplicates=[],
                    form_data=_rb.request.form,
                ), 422
            dob=dob_resolution.dob
            phone=_rb.request.form.get('phone','').strip()
            national_id=_rb.request.form.get('national_id','').strip()
            from registration_policy import validate_patient_fields
            try:
                validate_patient_fields(dict(name=name,phone=phone,national_id=national_id,dob=dob,sex=_rb.request.form.get('sex',''),
                    email=_rb.request.form.get('email',''),address=_rb.request.form.get('address',''),nationality=_rb.request.form.get('nationality','')))
            except ValueError as exc:
                return _rb.render_template('patient_form.html',duplicates=[],form_data=_rb.request.form,error=str(exc)),422
            duplicates=_rb.find_duplicate_patients(name,dob,phone,national_id)
            if duplicates and _rb.request.form.get('confirm_duplicate')!='1':
                return _rb.render_template('patient_form.html',duplicates=duplicates,form_data=_rb.request.form),409
            p=_rb.Patient(patient_id='TMP'+_rb.secrets.token_hex(8),name=name,
                      dob=dob,dob_estimated=dob_resolution.estimated,
                      sex=_rb.request.form.get('sex',''),
                      phone=phone,national_id=national_id,
                      address=_rb.request.form.get('address','').strip(),
                      email=_rb.request.form.get('email','').strip(),
                      worklist_name=_rb.normalized_worklist_name(name,_rb.request.form.get('worklist_name','')))
            _rb.db.session.add(p); _rb.db.session.flush(); p.patient_id=_rb.generate_patient_id(p)
            _rb.db.session.add(_rb.PatientDemographicsExtra(patient_id=p.id,nationality=_rb.request.form.get('nationality','').strip()))
            _rb.audit('PATIENT_CREATE','patient',p.id,f'{p.patient_id} {p.name}'); _rb.db.session.commit()
            _rb.flash(
                f'PATIENT_CREATED|{p.patient_id}|{p.name}',
                'success'
            )
            return _rb.redirect(_rb.url_for('new_order',patient=p.id,patient_created=1))
        return _rb.render_template('patient_form.html')
    return new_patient


def install_0157(_rb):
    @_rb.app.route('/admin/insurance-approvals',methods=['GET','POST'])
    @_rb.require_perm('contracts.manage')
    def admin_insurance_approvals():

        branches=_rb.Branch.query.filter_by(active=True).order_by(_rb.Branch.name).all()
        contracts=_rb.Contract.query.filter_by(active=True).order_by(_rb.Contract.name).all()

        if _rb.request.method=='POST':

            branch_id=_rb.request.form.get('branch_id',type=int)
            payer_name=(_rb.request.form.get('payer_name') or '').strip()

            if not branch_id or not payer_name:
                _rb.flash('Branch and insurance company are required.','danger')
                return _rb.redirect(_rb.url_for('admin_insurance_approvals'))

            row=_rb.InsurancePortalAccount.query.filter_by(
                branch_id=branch_id,
                payer_name=payer_name
            ).first()

            if not row:
                row=_rb.InsurancePortalAccount(
                    branch_id=branch_id,
                    payer_name=payer_name
                )
                _rb.db.session.add(row)

            row.portal_url=(_rb.request.form.get('portal_url') or '').strip()
            row.login_url=(_rb.request.form.get('login_url') or '').strip()
            row.portal_type=(_rb.request.form.get('portal_type') or 'WEB').strip().upper()

            row.username=(_rb.request.form.get('username') or '').strip()
            row.credential_ref=(_rb.request.form.get('credential_ref') or '').strip()

            row.workflow_mode=(_rb.request.form.get('workflow_mode') or 'MANUAL').strip().upper()

            allowed_modes={'MANUAL','BROWSER','API','EMAIL','HYBRID'}
            if row.workflow_mode not in allowed_modes:
                row.workflow_mode='MANUAL'

            row.enabled=_rb.request.form.get('enabled')=='1'

            # MANUAL means no automatic portal execution.
            if row.workflow_mode=='MANUAL':
                row.automation_enabled=False
            else:
                row.automation_enabled=_rb.request.form.get('automation_enabled')=='1'

            row.telegram_enabled=_rb.request.form.get('telegram_enabled')=='1'
            row.email_enabled=_rb.request.form.get('email_enabled')=='1'
            row.requires_otp=_rb.request.form.get('requires_otp')=='1'

            row.login_notes=(_rb.request.form.get('login_notes') or '').strip()
            row.workflow_notes=(_rb.request.form.get('workflow_notes') or '').strip()
            row.training_notes=(_rb.request.form.get('training_notes') or '').strip()

            row.selectors_json=(_rb.request.form.get('selectors_json') or '{}').strip()

            workflow_steps=[]

            step_map=[
                ('step_login','LOGIN'),
                ('step_search_member','SEARCH_MEMBER'),
                ('step_create_request','CREATE_REQUEST'),
                ('step_upload_documents','UPLOAD_DOCUMENTS'),
                ('step_submit','SUBMIT'),
                ('step_check_status','CHECK_STATUS'),
                ('step_download_approval','DOWNLOAD_APPROVAL'),
            ]

            for field_name,step_name in step_map:
                if _rb.request.form.get(field_name)=='1':
                    workflow_steps.append(step_name)

            config={
                'version':1,
                'workflow_steps':workflow_steps
            }

            # Validate portal configuration before save.
            validation_errors=[]

            effective_url=(row.login_url or row.portal_url or '').strip()

            if row.workflow_mode=='BROWSER' and row.automation_enabled:
                if not effective_url:
                    validation_errors.append('Browser Automation requires Portal/Login URL.')

                if not row.username:
                    validation_errors.append('Browser Automation requires Username.')

                if not row.credential_ref:
                    validation_errors.append('Browser Automation requires Credential Reference.')

                required_steps={'LOGIN','SUBMIT','CHECK_STATUS'}
                missing=sorted(required_steps-set(workflow_steps))

                if missing:
                    validation_errors.append(
                        'Browser Automation missing required workflow steps: '
                        + ', '.join(missing)
                    )

            elif row.workflow_mode=='API' and row.automation_enabled:
                if not effective_url:
                    validation_errors.append('API workflow requires endpoint URL.')

                required_steps={'SUBMIT','CHECK_STATUS'}
                missing=sorted(required_steps-set(workflow_steps))

                if missing:
                    validation_errors.append(
                        'API workflow missing required workflow steps: '
                        + ', '.join(missing)
                    )

            elif row.workflow_mode=='HYBRID' and row.automation_enabled:
                if not effective_url:
                    validation_errors.append('Hybrid workflow requires Portal/API URL.')

                if not workflow_steps:
                    validation_errors.append('Hybrid workflow requires at least one workflow step.')

            if validation_errors:
                _rb.db.session.rollback()

                for msg in validation_errors:
                    _rb.flash(msg,'danger')

                return _rb.redirect(
                    _rb.url_for('admin_insurance_approvals')
                )

            row.automation_config_json=_rb.json.dumps(
                config,
                ensure_ascii=False
            )

            row.updated_at=_rb.datetime.utcnow()

            _rb.audit(
                'INSURANCE_PORTAL_SAVE',
                'insurance_portal_account',
                row.id or 0,
                f'branch={branch_id}; payer={payer_name}'
            )

            _rb.db.session.commit()

            _rb.flash('Insurance portal configuration saved.','success')
            return _rb.redirect(
                _rb.url_for(
                    'admin_insurance_approval_edit',
                    portal_id=row.id
                )
            )

        rows=_rb.InsurancePortalAccount.query.order_by(
            _rb.InsurancePortalAccount.payer_name,
            _rb.InsurancePortalAccount.branch_id
        ).all()

        return _rb.render_template(
            'admin_insurance_approvals.html',
            rows=rows,
            branches=branches,
            contracts=contracts
        )
    return admin_insurance_approvals


def install_0158(_rb):
    @_rb.app.get('/admin/insurance-approvals/<int:portal_id>')
    @_rb.require_perm('contracts.manage')
    def admin_insurance_approval_edit(portal_id):

        row=_rb.InsurancePortalAccount.query.get_or_404(portal_id)

        return _rb.render_template(
            'admin_insurance_approvals.html',
            rows=_rb.InsurancePortalAccount.query.order_by(
                _rb.InsurancePortalAccount.payer_name
            ).all(),
            branches=_rb.Branch.query.filter_by(active=True).order_by(_rb.Branch.name).all(),
            contracts=_rb.Contract.query.filter_by(active=True).order_by(_rb.Contract.name).all(),
            edit_row=row
        )
    return admin_insurance_approval_edit


def install_0159(_rb):
    @_rb.app.post('/admin/insurance-approvals/<int:portal_id>/toggle')
    @_rb.require_perm('contracts.manage')
    def admin_insurance_approval_toggle(portal_id):

        row=_rb.InsurancePortalAccount.query.get_or_404(portal_id)

        row.enabled=not bool(row.enabled)
        row.updated_at=_rb.datetime.utcnow()

        _rb.audit(
            'INSURANCE_PORTAL_TOGGLE',
            'insurance_portal_account',
            row.id,
            f'enabled={row.enabled}'
        )

        _rb.db.session.commit()

        return _rb.redirect(_rb.url_for('admin_insurance_approvals'))
    return admin_insurance_approval_toggle


def install_0160(_rb):
    @_rb.app.post('/admin/insurance-approvals/<int:portal_id>/test')
    @_rb.require_perm('contracts.manage')
    def admin_insurance_approval_test(portal_id):

        row=_rb.InsurancePortalAccount.query.get_or_404(portal_id)

        # Safe configuration test only.
        # No external portal login is executed in v5.34 phase 1.

        problems=[]

        if not row.portal_url and not row.login_url:
            problems.append('Portal URL is missing')

        if not row.username:
            problems.append('Username is missing')

        if row.automation_enabled and not row.credential_ref:
            problems.append('Credential Reference is missing')

        if problems:
            row.last_error_at=_rb.datetime.utcnow()
            row.last_error='; '.join(problems)
            _rb.db.session.commit()

            _rb.flash(
                'Configuration needs attention: '+row.last_error,
                'warning'
            )

        else:
            row.last_success_at=_rb.datetime.utcnow()
            row.last_error=''
            _rb.db.session.commit()

            _rb.flash(
                'Configuration test passed. No live login was performed.',
                'success'
            )

        return _rb.redirect(_rb.url_for('admin_insurance_approval_edit',portal_id=row.id))
    return admin_insurance_approval_test


def install_0161(_rb):
    @_rb.app.get('/approvals')
    @_rb.require_perm('orders.view')
    def insurance_approvals_dashboard():
        view=(_rb.request.args.get('view') or 'pending').strip().lower()

        query=_rb.InsuranceApprovalRequest.query.join(
            _rb.Order,
            _rb.InsuranceApprovalRequest.order_id==_rb.Order.id
        ).join(
            _rb.Patient,
            _rb.Order.patient_id==_rb.Patient.id
        )

        if view=='approved':
            query=query.filter(
                _rb.InsuranceApprovalRequest.status=='APPROVED'
            )

        elif view=='action':
            query=query.filter(
                _rb.InsuranceApprovalRequest.status.in_(
                    ['REJECTED','NEED_INFO','ERROR']
                )
            )

        elif view=='all':
            pass

        else:
            view='pending'
            query=query.filter(
                _rb.InsuranceApprovalRequest.status.in_(
                    ['REQUIRED','SUBMITTED','PENDING']
                )
            )

        rows=query.order_by(
            _rb.InsuranceApprovalRequest.updated_at.desc(),
            _rb.InsuranceApprovalRequest.id.desc()
        ).limit(500).all()

        counts={
            'pending': _rb.InsuranceApprovalRequest.query.filter(
                _rb.InsuranceApprovalRequest.status.in_(
                    ['REQUIRED','SUBMITTED','PENDING']
                )
            ).count(),

            'approved': _rb.InsuranceApprovalRequest.query.filter_by(
                status='APPROVED'
            ).count(),

            'action': _rb.InsuranceApprovalRequest.query.filter(
                _rb.InsuranceApprovalRequest.status.in_(
                    ['REJECTED','NEED_INFO','ERROR']
                )
            ).count(),

            'all': _rb.InsuranceApprovalRequest.query.count()
        }

        return _rb.render_template(
            'approvals.html',
            rows=rows,
            view=view,
            counts=counts,
            now=_rb.datetime.utcnow()
        )
    return insurance_approvals_dashboard


def install_0162(_rb):
    @_rb.app.route('/orders/<int:order_id>')
    @_rb.require_perm('orders.view')
    def order_detail(order_id):
        order=_rb.Order.query.get_or_404(order_id)
        payments=_rb.Payment.query.filter_by(order_id=order.id).order_by(_rb.Payment.id.desc()).all()
        consumables=_rb.OrderConsumable.query.filter_by(order_id=order.id).all()
        attachments=_rb.Attachment.query.filter_by(order_id=order.id).order_by(_rb.Attachment.created_at.desc()).all()
        receipts=_rb.Receipt.query.filter_by(order_id=order.id).order_by(_rb.Receipt.created_at.desc()).all()
        delivery_events=_rb.DeliveryEvent.query.filter_by(order_id=order.id).order_by(_rb.DeliveryEvent.delivered_at.desc()).all()

        insurance_approval=_rb.InsuranceApprovalRequest.query.filter_by(
            order_id=order.id
        ).order_by(_rb.InsuranceApprovalRequest.id.desc()).first()

        approval_attachment=_rb.Attachment.query.filter_by(
            order_id=order.id,
            category='APPROVAL'
        ).order_by(_rb.Attachment.created_at.desc()).first()

        work_order_decision=_rb.work_order_gate(
            order_status=order.status,
            balance=_rb.order_balance(order),
            patient_id=(order.patient.patient_id if order.patient else ''),
            patient_dob=(order.patient.dob if order.patient else ''),
            accession=order.accession,
            modality=order.modality,
            procedure=order.procedure,
            device_id=order.device_id,
            station_ae=order.station_ae,
        )

        return _rb.render_template('order_detail.html',order=order,payments=payments,consumables=consumables,
            attachments=attachments,receipts=receipts,delivery_events=delivery_events,
            order_discounts=_rb.approved_order_discounts(order),effective_due=_rb.effective_patient_due(order),
            discount_policy=_rb.discount_policy_for(order),performing_doctor=_rb.performing_doctor_for_order(order),
            performing_share=_rb.performing_doctor_share_for_order(order)[0],
            doctors=_rb.User.query.filter_by(active=True).order_by(_rb.User.full_name).all(),
            consumable_cost=_rb.order_consumable_cost(order),
            branch_warehouse=_rb.default_warehouse_for_order(order),
            insurance_approval=insurance_approval,
            approval_attachment=approval_attachment,
            work_order_gate=work_order_decision,
            delivery_readiness=__import__('delivery_policy').snapshot(order))
    return order_detail


def install_0163(_rb):
    @_rb.app.post('/orders/<int:order_id>/insurance-approval/start')
    @_rb.require_perm('orders.view')
    def insurance_approval_start(order_id):
        order=_rb.Order.query.filter_by(id=order_id).with_for_update().first_or_404()
        from insurance_policy import require_actor
        require_actor(order)

        method=(_rb.request.form.get('method') or 'MANUAL').strip().upper()

        if method not in ('MANUAL','AUTO'):
            method='MANUAL'

        row=_rb.InsuranceApprovalRequest.query.filter_by(
            order_id=order.id
        ).order_by(_rb.InsuranceApprovalRequest.id.desc()).first()

        if row and row.status in ('REQUIRED','SUBMITTED','PENDING'):
            _rb.flash('يوجد طلب موافقة مفتوح بالفعل لهذه الحالة.','warning')
            return _rb.redirect(_rb.url_for('order_detail',order_id=order.id))

        payer_name=order.contract.name if order.contract else ''

        row=_rb.InsuranceApprovalRequest(
            order_id=order.id,
            method=method,
            status='PENDING' if method=='AUTO' else 'REQUIRED',
            payer_name=payer_name,
            requested_at=_rb.datetime.utcnow(),
            created_by=_rb.current_user().id
        )

        _rb.db.session.add(row)
        _rb.db.session.flush()

        _rb.db.session.add(_rb.InsuranceApprovalEvent(
            approval_request_id=row.id,
            event_type='CREATED',
            old_status='',
            new_status=row.status,
            message='Approval request created',
            user_id=_rb.current_user().id
        ))

        _rb.audit(
            'INSURANCE_APPROVAL_CREATE',
            'order',
            order.id,
            f'method={method}; status={row.status}'
        )

        _rb.db.session.commit()

        if method=='AUTO':
            _rb.flash('تم إرسال طلب الموافقة للنظام للمتابعة التلقائية.','success')
        else:
            _rb.flash('تم فتح متابعة الموافقة اليدوية.','success')

        return _rb.redirect(_rb.url_for('order_detail',order_id=order.id))
    return insurance_approval_start


def install_0164(_rb):
    @_rb.app.post('/orders/<int:order_id>/insurance-approval/update')
    @_rb.require_perm('orders.view')
    def insurance_approval_update(order_id):
        order=_rb.Order.query.filter_by(id=order_id).with_for_update().first_or_404()
        from insurance_policy import require_actor
        require_actor(order)

        row=_rb.InsuranceApprovalRequest.query.filter_by(
            order_id=order.id
        ).order_by(_rb.InsuranceApprovalRequest.id.desc()).first_or_404()

        new_status=(_rb.request.form.get('status') or '').strip().upper()

        allowed={
            'REQUIRED',
            'SUBMITTED',
            'PENDING',
            'APPROVED',
            'REJECTED',
            'NEED_INFO',
            'ERROR'
        }

        if new_status not in allowed:
            _rb.flash('حالة الموافقة غير صحيحة.','danger')
            return _rb.redirect(_rb.url_for('order_detail',order_id=order.id))

        approval_no=(_rb.request.form.get('approval_no') or '').strip()
        if new_status=='APPROVED' and not approval_no:
            _rb.flash('Approval reference is required. / يلزم رقم موافقة التأمين.','danger')
            return _rb.redirect(_rb.url_for('order_detail',order_id=order.id))

        old_status=row.status or ''

        row.status=new_status
        row.approval_no=(_rb.request.form.get('approval_no') or '').strip()
        row.notes=(_rb.request.form.get('notes') or '').strip()
        row.updated_at=_rb.datetime.utcnow()

        if new_status in ('APPROVED','REJECTED'):
            row.decided_at=_rb.datetime.utcnow()

        # Clear stale approval references when the latest decision is unresolved.
        order.approval_no=row.approval_no if new_status=='APPROVED' else ''

        _rb.db.session.add(_rb.InsuranceApprovalEvent(
            approval_request_id=row.id,
            event_type='STATUS_CHANGE',
            old_status=old_status,
            new_status=new_status,
            message=row.notes,
            user_id=_rb.current_user().id
        ))

        _rb.audit(
            'INSURANCE_APPROVAL_UPDATE',
            'order',
            order.id,
            f'{old_status}->{new_status}; approval_no={row.approval_no}'
        )

        _rb.db.session.commit()

        _rb.flash('تم تحديث حالة الموافقة.','success')

        return _rb.redirect(_rb.url_for('order_detail',order_id=order.id))
    return insurance_approval_update


def install_0165(_rb):
    @_rb.app.post('/orders/<int:order_id>/convert-to-work-order')
    @_rb.require_perm('orders.create')
    def convert_to_work_order(order_id):
        order=_rb.Order.query.filter_by(id=order_id).with_for_update().first_or_404()
        _rb.Patient.query.filter_by(id=order.patient_id).with_for_update().first_or_404()

        from insurance_policy import approval_blocker
        insurance_blocker=approval_blocker(order)
        if insurance_blocker:
            _rb.audit('WORK_ORDER_BLOCKED','order',order.id,insurance_blocker)
            _rb.db.session.commit()
            _rb.flash(insurance_blocker,'danger')
            return _rb.redirect(_rb.url_for('order_detail',order_id=order.id))

        # Legacy contract marker retained for regression traceability:
        # order_balance(order) > 0.01 is enforced inside work_order_gate().
        decision=_rb.work_order_gate(
            order_status=order.status,
            balance=_rb.order_balance(order),
            patient_id=(order.patient.patient_id if order.patient else ''),
            patient_dob=(order.patient.dob if order.patient else ''),
            accession=order.accession,
            modality=order.modality,
            procedure=order.procedure,
            device_id=order.device_id,
            station_ae=order.station_ae,
        )

        if not decision.allowed:
            _rb.audit(
                'WORK_ORDER_BLOCKED',
                'order',
                order.id,
                _rb.blockers_text(decision.blockers),
            )
            _rb.db.session.commit()
            _rb.flash(
                'Work Order blocked: ' + _rb.blockers_text(decision.blockers),
                'danger',
            )
            return _rb.redirect(_rb.url_for('order_detail',order_id=order.id))

        try:
            mwl_event=_rb.enqueue_event(
                'ORDER_MWL_CREATE',
                'order',
                order.id,
                {
                    'accession':order.accession,
                    'device_id':order.device_id
                }
            )
            order.status='MWL_PENDING'
            _rb.audit(
                'WORK_ORDER_MWL_PENDING',
                'order',
                order.id,
                f'accession={order.accession}; station_ae={order.station_ae}'
            )
            _rb.db.session.commit()
            mwl_event_id=mwl_event.id
        except Exception as exc:
            _rb.db.session.rollback()
            _rb.app.logger.exception(
                'Work Order preparation failed order=%s',
                order.id
            )
            _rb.flash(
                f'Work Order preparation failed: {exc}',
                'danger'
            )
            return _rb.redirect(_rb.url_for('order_detail',order_id=order.id))

        try:
            order=_rb.Order.query.filter_by(id=order_id).populate_existing().with_for_update().first_or_404()
            _rb.send_mwl(order)

            mwl_event=_rb.EventOutbox.query.get(mwl_event_id)
            order.status='SCHEDULED'
            order.exam_status='ORDERED'

            if mwl_event:
                mwl_event.status='PROCESSED'
                mwl_event.attempts=int(mwl_event.attempts or 0)+1
                mwl_event.processed_at=_rb.datetime.utcnow()
                mwl_event.last_error=''

            _rb.audit(
                'WORK_ORDER_CREATED',
                'order',
                order.id,
                f'accession={order.accession}; station_ae={order.station_ae}'
            )
            _rb.db.session.commit()
            _rb.flash('Work Order created and MWL sent successfully.','success')
        except Exception as exc:
            _rb.db.session.rollback()

            order=_rb.Order.query.get(order_id)
            mwl_event=_rb.EventOutbox.query.get(mwl_event_id)

            if order:
                order.status='MWL_ERROR'

            if mwl_event:
                mwl_event.status='FAILED'
                mwl_event.attempts=int(mwl_event.attempts or 0)+1
                mwl_event.last_error=str(exc)[:2000]

            if order:
                _rb.audit(
                    'WORK_ORDER_MWL_FAILED',
                    'order',
                    order.id,
                    str(exc)[:500]
                )

            _rb.db.session.commit()
            _rb.app.logger.exception(
                'Work Order MWL delivery failed order=%s',
                order_id
            )
            _rb.flash(
                'Work Order was not activated because MWL delivery failed.',
                'danger'
            )

        return _rb.redirect(_rb.url_for('order_detail',order_id=order_id))
    return convert_to_work_order


def install_0173(_rb):
    @_rb.app.route('/portal/<token>',methods=['GET','POST'])
    def patient_portal(token):
        x=_rb.PortalAccessToken.query.filter_by(token=token,revoked=False).first_or_404()
        if x.expires_at<_rb.datetime.utcnow(): _rb.abort(410)
        o=x.order
        if not o: _rb.abort(404)
        verify_key='portal_verified_'+token
        digits=_rb.re.sub(r'\D','',o.patient.phone or '')
        needs_verify=_rb.PORTAL_REQUIRE_PHONE_VERIFY and len(digits)>=4
        if needs_verify and not _rb.session.get(verify_key):
            if _rb.request.method=='POST':
                if _rb.re.sub(r'\D','',_rb.request.form.get('phone_last4',''))==digits[-4:]:
                    _rb.session[verify_key]=True
                    return _rb.redirect(_rb.url_for('patient_portal',token=token))
                _rb.flash('Verification code does not match the registered mobile number.','danger')
            return _rb.render_template('patient_portal_verify.html',order=o,portal_token=token)
        report=o.report if o.report and o.report.status=='FINAL' else None
        viewer_url=_rb.case_pacs_url(o) if int(o.pacs_image_count or 0)>0 else ''
        return _rb.render_template('patient_portal.html',order=o,report=report,portal_token=token,viewer_url=viewer_url)
    return patient_portal


def install_0207(_rb):
    @_rb.app.get('/api/registration/visits')
    @_rb.login_required
    def api_registration_visits():
        _rb._rb_v5462_allow_registration()
        try: day=_rb.datetime.strptime(_rb.request.args.get('date',''),'%Y-%m-%d').date()
        except ValueError: return _rb.jsonify(error='Invalid visit date'),400
        patient_id=_rb.request.args.get('patient_id',type=int);branch_id=_rb.request.args.get('branch_id',type=int)
        from registration_policy import require_registration_branch
        require_registration_branch(branch_id)
        rows=_rb.AssignmentVisit.query.filter_by(patient_id=patient_id,branch_id=branch_id,visit_date=day).order_by(_rb.AssignmentVisit.sequence_id.desc()).limit(50).all()
        return _rb.jsonify(visits=[dict(id=v.id,label=f'Visit #{v.sequence_id} · {v.visit_date}',assignment_mode=v.assignment_mode or 'AUTO',doctor_id=v.preferred_doctor_id,registration_open=bool(v.registration_open)) for v in rows])
    return api_registration_visits


def install_0406(_rb):
    @_rb.app.route('/schedule/calendar')
    @_rb.require_perm('appointments.manage')
    def schedule_calendar():
        from datetime import datetime, timedelta

        day_raw=_rb.request.args.get('date','').strip()
        try:
            selected=datetime.strptime(day_raw,'%Y-%m-%d').date() if day_raw else datetime.now().date()
        except Exception:
            selected=datetime.now().date()

        start=datetime.combine(selected,datetime.min.time())
        end=start+timedelta(days=1)

        from registration_policy import allowed_registration_branches,require_registration_branch
        allowed_branches=allowed_registration_branches()
        branches_q=_rb.Branch.query.filter_by(active=True)
        if allowed_branches is not None:
            branches_q=branches_q.filter(_rb.Branch.id.in_(allowed_branches))
        visible_branches=branches_q.order_by(_rb.Branch.name).all()
        branch_id=_rb.request.args.get('branch_id',type=int)
        if branch_id:require_registration_branch(branch_id)
        if not branch_id and allowed_branches is not None:
            if not visible_branches:_rb.abort(403)
            branch_id=visible_branches[0].id
        selected_device_id=_rb.request.args.get('device_id',type=int)

        devices_q=_rb.Device.query.filter_by(active=True)
        if allowed_branches is not None:devices_q=devices_q.filter(_rb.Device.branch_id.in_(allowed_branches))
        if branch_id:
            devices_q=devices_q.filter(_rb.Device.branch_id==branch_id)
        if selected_device_id:
            devices_q=devices_q.filter(_rb.Device.id==selected_device_id)
        devices=devices_q.order_by(_rb.Device.modality,_rb.Device.name).all()

        device_ids=[d.id for d in devices]

        q=_rb.Appointment.query.filter(
            _rb.Appointment.scheduled>=start,
            _rb.Appointment.scheduled<end,
            _rb.Appointment.status.notin_(['CANCELLED','NO_SHOW'])
        )
        if branch_id:
            q=q.filter(_rb.Appointment.branch_id==branch_id)
        if selected_device_id:
            q=q.filter(_rb.Appointment.device_id==selected_device_id)
        elif device_ids:
            q=q.filter(_rb.or_(_rb.Appointment.device_id.in_(device_ids),_rb.Appointment.device_id.is_(None)))

        appointments=q.order_by(_rb.Appointment.scheduled.asc()).all()

        # 15-minute slots. Booking only; Order is intentionally not created here.
        slots=[]
        cur=start.replace(hour=7,minute=0)
        stop=start.replace(hour=23,minute=0)
        while cur<stop:
            slots.append(cur)
            cur+=timedelta(minutes=15)

        calendar_cells=_rb.build_calendar_cells(appointments,slots)

        return _rb.render_template(
            'schedule_calendar.html',
            selected=selected,
            prev_day=selected-timedelta(days=1),
            next_day=selected+timedelta(days=1),
            slots=slots,
            appointments=appointments,
            calendar_cells=calendar_cells,
            branches=visible_branches,
            devices=devices,
            all_devices=_rb.Device.query.filter_by(active=True).filter(_rb.Device.branch_id.in_([b.id for b in visible_branches])).order_by(_rb.Device.modality,_rb.Device.name).all(),
            procedures=_rb.Procedure.query.filter_by(active=True).order_by(_rb.Procedure.modality,_rb.Procedure.name).all(),
            patients=_rb.Patient.query.order_by(_rb.Patient.name).limit(1000).all(),
            contracts=_rb.Contract.query.filter_by(active=True).order_by(_rb.Contract.name).all(),
            referrers=_rb.ReferringDoctor.query.filter_by(active=True).order_by(_rb.ReferringDoctor.name).all(),
            document_types=_rb.SMART_DOCUMENT_TYPES,
            registration_field_rules=__import__('registration_policy').field_rules_for_ui(),
            registration_doctors=_rb.assignable_doctors(),
            can_take_payment=_rb.has_perm('payments.create'),
            branch_id=branch_id,
            selected_device_id=selected_device_id,
        )
    return schedule_calendar


def install_0416(_rb):
    @_rb.app.post('/schedule/ocr-preview')
    @_rb.login_required
    def schedule_ocr_preview():
        _rb._rb_v5462_allow_registration()
        f=_rb.request.files.get('file')
        if not f or not f.filename:
            return _rb.jsonify({'ok':False,'error':'Choose a document.'}),400

        intake=_rb.SmartIntakeSession.query.get(_rb.request.form.get('intake_id',type=int)) if _rb.request.form.get('intake_id') else None
        if not intake:
            intake=_rb.SmartIntakeSession(
                session_key=_rb.secrets.token_urlsafe(24),
                created_by=_rb.current_user().id,status='UPLOADING'
            )
            _rb.db.session.add(intake); _rb.db.session.flush()

        dtype=(_rb.request.form.get('document_type') or 'OTHER').upper()
        if dtype not in {x[0] for x in _rb.SMART_DOCUMENT_TYPES}: dtype='OTHER'
        ext=_rb.os.path.splitext(f.filename)[1].lower()
        if ext not in {'.pdf','.png','.jpg','.jpeg','.tif','.tiff','.webp','.bmp','.dcm'}:
            _rb.db.session.rollback()
            return _rb.jsonify({'ok':False,'error':f'Unsupported file type: {ext or "unknown"}'}),400

        folder=_rb.smart_intake_dir(intake.id)
        safe=_rb.re.sub(r'[^A-Za-z0-9._-]','_',f.filename)[:180]
        path=_rb.os.path.join(folder,f'{_rb.uuid.uuid4().hex}_{safe}')
        f.save(path)
        digest=_rb._intake_file_sha256(path)

        doc=_rb.SmartIntakeDocument.query.filter_by(intake_id=intake.id,content_sha256=digest).first()
        if doc:
            try: _rb.os.remove(path)
            except Exception: pass
        else:
            doc=_rb.SmartIntakeDocument(
                intake_id=intake.id,document_type=dtype,original_name=f.filename,
                file_path=path,mime_type=f.mimetype or '',status='UPLOADED',
                content_sha256=digest
            )
            _rb.db.session.add(doc); _rb.db.session.flush()

        result,error=_rb.call_ocr_provider(doc)
        classification={}; fields={}; text_value=''; warning=''
        if result:
            classification=_rb._apply_smart_intake_ocr_result(doc,result)
            fields=dict(result.get('fields') or {})
            text_value=str(result.get('text') or '')
        else:
            warning=error or 'OCR unavailable. Document kept for manual review.'
            doc.status='OCR_FAILED'; doc.ocr_error=warning[:500]

        searchable=(text_value+' '+_rb.json.dumps(fields,ensure_ascii=False)).lower()
        matches=[]
        if searchable.strip():
            for p in _rb.Procedure.query.filter_by(active=True).all():
                vals=[p.name or '',p.name_ar or '',p.code or '']
                if any(v and v.lower() in searchable for v in vals):
                    matches.append({'id':p.id,'name':p.name,'modality':p.modality,'duration':int(p.duration_min or 20)})

        contract_match=None
        if searchable.strip():
            for c in _rb.Contract.query.filter_by(active=True).all():
                if c.name and c.name.lower() in searchable:
                    contract_match={'id':c.id,'name':c.name,'approval_required':bool(c.approval_required)}
                    break

        suggested=classification.get('suggested_type') or classification.get('type') or doc.document_type or 'OTHER'
        _rb.db.session.commit()
        return _rb.jsonify({
            'ok':True,'intake_id':intake.id,'document_id':doc.id,
            'filename':doc.original_name,'suggested_type':suggested,
            'confidence':float(doc.confidence or 0),'fields':fields,
            'text':text_value[:12000],'procedure_matches':matches,
            'contract_match':contract_match,'warning':warning
        })
    return schedule_ocr_preview


def install_0417(_rb):
    @_rb.app.post('/schedule/unified-submit')
    @_rb.login_required
    def schedule_unified_submit():
        _rb._rb_v5462_allow_registration()
        action=(_rb.request.form.get('registration_action') or 'REGISTER').upper()
        if action not in ('BOOK','REGISTER'): _rb.abort(400)

        saved=[]; orders=[]; appts=[]
        try:
            try:
                scheduled=_rb.datetime.fromisoformat((_rb.request.form.get('scheduled') or '').strip())
            except Exception:
                raise ValueError('Invalid appointment date/time.')

            branch=_rb.Branch.query.get_or_404(_rb.request.form.get('branch_id',type=int))
            from registration_policy import require_registration_branch
            require_registration_branch(branch.id)
            device=_rb.Device.query.get_or_404(_rb.request.form.get('device_id',type=int))
            if device.branch_id!=branch.id:
                raise ValueError('Selected device does not belong to this branch.')

            procs=[_rb.Procedure.query.get_or_404(x) for x in _rb._rb_v5462_proc_ids(_rb.request.form)]
            if not procs: raise ValueError('Add at least one examination.')
            for p in procs:
                if (p.modality or '').upper()!=(device.modality or '').upper():
                    raise ValueError(f'{p.name} is not compatible with {device.name}.')
                if not _rb.procedure_available_in_branch(p.id,branch.id):
                    raise ValueError(f'{p.name} is not available in {branch.name}.')

            patient=_rb._rb_v5462_patient(_rb.request.form)
            contract=_rb.Contract.query.get(_rb.request.form.get('contract_id',type=int)) if _rb.request.form.get('contract_id') else None
            referrer=_rb.request.form.get('referring_doctor_id',type=int)
            priority=(_rb.request.form.get('priority') or 'ROUTINE').upper()
            waiting=_rb.request.form.get('waiting_list')=='1'
            cursor=scheduled
            from registration_policy import select_visit
            visit_id=select_visit(patient,branch,scheduled,procs,_rb.request.form)

            if action=='BOOK':
                for p in procs:
                    duration=max(5,int(p.duration_min or 20))
                    if not waiting:
                        _rb.acquire_booking_slot_lock(device.id,cursor)
                        reason=_rb.booking_restriction_reason(branch,p,device,cursor,duration)
                        if reason: raise ValueError(f'{p.name}: {reason}')
                    dup=_rb.Appointment.query.filter_by(
                        patient_id=patient.id,procedure_id=p.id,scheduled=cursor
                    ).filter(_rb.Appointment.status!='CANCELLED').first()
                    if dup: raise ValueError(f'Duplicate booking exists for {p.name} at {cursor.strftime("%H:%M")}.')
                    a=_rb.Appointment(
                        patient_id=patient.id,branch_id=branch.id,procedure_id=p.id,
                        device_id=device.id,scheduled=cursor,
                        status='WAITING' if waiting else 'BOOKED',
                        source='FULL_REGISTRATION_WORKSPACE',assignment_visit_id=visit_id,
                        duration_min=duration,priority=priority,waiting_list=waiting,
                        notes=(_rb.request.form.get('notes') or '').strip(),
                        created_by=_rb.current_user().id
                    )
                    _rb.db.session.add(a); _rb.db.session.flush(); appts.append(a)
                    cursor+=_rb.timedelta(minutes=duration)

                first=appts[0]
                saved+=_rb._rb_v5462_direct_attachments(patient,appointment=first)
                _rb._rb_v5462_attach_ocr(patient,_rb.request.form.get('ocr_intake_id',type=int),appointment=first)
                _rb.audit('FULL_REGISTRATION_BOOK_ONLY','appointment',first.id,f'patient={patient.id}; exams={len(appts)}')
                _rb.db.session.commit()
                _rb.flash(f'Booked {len(appts)} examination(s) for {patient.name}.','success')
                return _rb._rb_calendar_redirect(scheduled,branch.id,device.id)

            if not (_rb.has_perm('*') or _rb.has_perm('orders.create')): _rb.abort(403)

            for p in procs:
                duration=max(5,int(p.duration_min or 20))
                _rb.acquire_booking_slot_lock(device.id,cursor)
                reason=_rb.booking_restriction_reason(branch,p,device,cursor,duration)
                if reason: raise ValueError(f'{p.name}: {reason}')
                gross,effective,patient_share,company_share,_=_rb.price_order(p,contract)
                o=_rb.Order(
                    accession=_rb.new_accession(),patient=patient,modality=p.modality,
                    procedure=p.name,procedure_id=p.id,branch_id=branch.id,
                    device_id=device.id,station_ae=device.ae_title,
                    contract_id=(contract.id if contract else None),
                    referring_doctor_id=referrer or None,scheduled=cursor,
                    status='REGISTERED',gross_price=gross,contract_price=effective,
                    patient_share=patient_share,company_share=company_share,
                    created_by=_rb.current_user().id,priority=priority,assignment_visit_id=visit_id
                )
                _rb.db.session.add(o); _rb.db.session.flush()
                a=_rb.Appointment(
                    patient_id=patient.id,
                    branch_id=branch.id,
                    procedure_id=p.id,
                    device_id=device.id,
                    order_id=o.id,
                    scheduled=cursor,
                    status='REGISTERED',
                    source='FULL_REGISTRATION_WORKSPACE',assignment_visit_id=visit_id,
                    duration_min=duration,
                    priority=priority,
                    waiting_list=False,
                    notes=(_rb.request.form.get('notes') or '').strip(),
                    created_by=_rb.current_user().id,
                )
                _rb.db.session.add(a); _rb.db.session.flush(); appts.append(a)
                _rb._rb_v5462_insurance(o,contract,_rb.request.form)
                _rb._rb_v5462_notes(o,_rb.request.form)
                _rb.ensure_journey(o,'REGISTERED')
                for pc in _rb.ProcedureConsumable.query.filter_by(procedure_id=p.id).all():
                    _rb.db.session.add(_rb.OrderConsumable(
                        order_id=o.id,consumable_id=pc.consumable_id,qty=pc.qty,
                        source='DEFAULT',created_by=_rb.current_user().id
                    ))
                # RB_WORK_ORDER_GATE_V1
                # Registration creates the clinical order only.
                # MWL is created later by explicit Convert to Work Order.
                orders.append(o); cursor+=_rb.timedelta(minutes=duration)

            first=orders[0]
            from registration_policy import assign_reserved_visit
            assign_reserved_visit(first)
            saved+=_rb._rb_v5462_direct_attachments(patient,order=first)
            _rb._rb_v5462_attach_ocr(patient,_rb.request.form.get('ocr_intake_id',type=int),order=first)
            _rb._rb_v5462_payment(orders,_rb.request.form)
            _rb.audit('FULL_REGISTRATION_CREATE','order',first.id,f'patient={patient.id}; exams={len(orders)}')
            _rb.db.session.commit()

            # RB_WORK_ORDER_GATE_V1
            # Do not create MWL during registration.
            # Orders remain REGISTERED until an authorized employee
            # explicitly converts them to Work Orders.
            _rb.flash(f'Registered {len(orders)} examination(s) for {patient.name}.','success')
            return _rb._rb_calendar_redirect(scheduled,branch.id,device.id)

        except ValueError as exc:
            _rb.db.session.rollback()
            for p in saved:
                try:
                    if _rb.os.path.isfile(p): _rb.os.remove(p)
                except Exception: pass
            _rb.flash(str(exc),'danger')
            return _rb.redirect(_rb.url_for('schedule_calendar'))
    return schedule_unified_submit


def install_0418(_rb):
    @_rb.app.post('/schedule/book')
    @_rb.require_perm('appointments.manage')
    def schedule_book():
        try: scheduled=_rb.datetime.fromisoformat((_rb.request.form.get('scheduled') or '').strip())
        except Exception:
            _rb.flash('Invalid booking date/time.','danger');return _rb.redirect(_rb.url_for('schedule_calendar'))
        branch_id=_rb.request.form.get('branch_id',type=int);device_id=_rb.request.form.get('device_id',type=int)
        if not branch_id or not device_id:
            _rb.flash('Branch and device are required.','danger');return _rb._rb_calendar_redirect(scheduled,branch_id,device_id)
        branch=_rb.Branch.query.get_or_404(branch_id);device=_rb.Device.query.get_or_404(device_id)
        from registration_policy import require_registration_branch
        require_registration_branch(branch.id)
        if device.branch_id!=branch.id:
            _rb.flash('Selected device does not belong to the selected branch.','danger');return _rb._rb_calendar_redirect(scheduled,branch.id,device.id)
        procedure_ids=[]
        for raw in _rb.request.form.getlist('procedure_ids'):
            try: pid=int(raw)
            except Exception: continue
            if pid not in procedure_ids:procedure_ids.append(pid)
        if not procedure_ids:
            one=_rb.request.form.get('procedure_id',type=int)
            if one:procedure_ids=[one]
        if not procedure_ids:
            _rb.flash('Add at least one examination.','danger');return _rb._rb_calendar_redirect(scheduled,branch.id,device.id)
        procedures=[]
        for pid in procedure_ids:
            proc=_rb.Procedure.query.get_or_404(pid)
            if (proc.modality or '').upper()!=(device.modality or '').upper():
                _rb.flash(f'{proc.name} is not compatible with {device.name}.','danger');return _rb._rb_calendar_redirect(scheduled,branch.id,device.id)
            if not _rb.procedure_available_in_branch(proc.id,branch.id):
                _rb.flash(f'{proc.name} is not available in this branch.','danger');return _rb._rb_calendar_redirect(scheduled,branch.id,device.id)
            procedures.append(proc)
        mode=(_rb.request.form.get('patient_mode') or 'existing').strip().lower()
        try:
            if mode=='new':patient=_rb._rb_registration_v2_create_patient(_rb.request.form,'PATIENT_CREATE_FROM_UNIFIED_BOOKING')
            else:
                patient_id=_rb.request.form.get('patient_id',type=int)
                if not patient_id:raise ValueError('Choose an existing patient or select New Patient.')
                patient=_rb.Patient.query.get_or_404(patient_id)
        except ValueError as exc:
            _rb.db.session.rollback();_rb.flash(str(exc),'danger');return _rb._rb_calendar_redirect(scheduled,branch.id,device.id)
        waiting=_rb.request.form.get('waiting_list')=='1';priority=(_rb.request.form.get('priority') or 'NORMAL').upper();notes=(_rb.request.form.get('notes') or '').strip()
        cursor=scheduled;created=[]
        try:
            from registration_policy import select_visit,validate_patient
            validate_patient(patient)
            visit_id=select_visit(patient,branch,scheduled,procedures,_rb.request.form)
            for proc in procedures:
                duration=max(5,int(proc.duration_min or 20))
                if not waiting:
                    _rb.acquire_booking_slot_lock(device.id,cursor)
                    reason=_rb.booking_restriction_reason(branch,proc,device,cursor,duration)
                    if reason:raise ValueError(f'{proc.name}: {reason}')
                duplicate=_rb.Appointment.query.filter_by(patient_id=patient.id,procedure_id=proc.id,scheduled=cursor).filter(_rb.Appointment.status!='CANCELLED').first()
                if duplicate:raise ValueError(f'Duplicate booking exists for {proc.name} at {cursor.strftime("%H:%M")}.')
                appt=_rb.Appointment(patient_id=patient.id,branch_id=branch.id,procedure_id=proc.id,device_id=device.id,scheduled=cursor,
                    status='WAITING' if waiting else 'BOOKED',source='UNIFIED_CALENDAR',assignment_visit_id=visit_id,duration_min=duration,priority=priority,waiting_list=waiting,notes=notes,created_by=_rb.current_user().id)
                _rb.db.session.add(appt);_rb.db.session.flush()
                _rb.audit('APPOINTMENT_CREATE_UNIFIED','appointment',appt.id,f'{patient.patient_id}; device={device.id}; procedure={proc.id}; {cursor.isoformat()}; duration={duration}')
                created.append(appt);cursor+=_rb.timedelta(minutes=duration)
            _rb.db.session.commit()
        except Exception as exc:
            _rb.db.session.rollback();_rb.flash(str(exc),'danger');return _rb._rb_calendar_redirect(scheduled,branch.id,device.id)
        total=sum(int(a.duration_min or 0) for a in created)
        _rb.flash(f'Booked {len(created)} examination(s) for {patient.name}. Total duration: {total} min.','success')
        return _rb._rb_calendar_redirect(scheduled,branch.id,device.id)
    return schedule_book


def install_0419(_rb):
    @_rb.app.post('/orders/<int:order_id>/workflow-status')
    @_rb.require_perm('orders.status')
    def order_workflow_status(order_id):
        # Compatibility endpoint: lifecycle state is derived, never directly written.
        order=_rb.Order.query.get_or_404(order_id)
        target=(_rb.request.form.get('status') or '').strip().upper().replace(' ','_')
        report=getattr(order,'report',None)
        projected=_rb.canonical_display_state(
            order_status=order.status,
            exam_status=order.exam_status,
            report_status=(report.status if report else 'UNREPORTED'),
        )

        if target and target != projected:
            _rb.flash(
                f'Direct workflow status changes are disabled. Current canonical state: {projected}.',
                'warning',
            )
        else:
            _rb.flash(f'Canonical workflow state: {projected}.','info')

        return _rb.redirect(_rb.request.referrer or _rb.url_for('schedule_calendar'))
    return order_workflow_status


def install_0420(_rb):
    @_rb.app.route('/appointments', methods=['GET','POST'])
    @_rb.require_perm('appointments.manage')
    def appointments():
        from registration_policy import allowed_registration_branches,require_registration_branch
        allowed=allowed_registration_branches()
        if _rb.request.method=='POST':
            from legacy_booking import create_booking
            return create_booking()

        rows=_rb.Appointment.query.filter(_rb.Appointment.branch_id.in_(allowed) if allowed is not None else True).order_by(_rb.Appointment.scheduled.desc()).limit(500).all()
        return _rb.render_template(
            'appointments.html',
            rows=rows,
            patients=_rb.Patient.query.order_by(_rb.Patient.name).all(),
            branches=_rb.Branch.query.filter_by(active=True).filter(_rb.Branch.id.in_(allowed) if allowed is not None else True).order_by(_rb.Branch.name).all(),
            procedures=_rb.Procedure.query.filter_by(active=True).order_by(_rb.Procedure.modality,_rb.Procedure.name).all(),
            devices=_rb.Device.query.filter_by(active=True).filter(_rb.Device.branch_id.in_(allowed) if allowed is not None else True).order_by(_rb.Device.modality,_rb.Device.name).all()
        )
    return appointments


def install_0421(_rb):
    @_rb.app.route('/appointments/<int:appointment_id>/<action>', methods=['POST'])
    @_rb.require_perm('appointments.manage')
    def appointment_action(appointment_id, action):
        a=_rb.Appointment.query.filter_by(id=appointment_id).with_for_update().first_or_404()
        from registration_policy import require_registration_branch
        require_registration_branch(a.branch_id)
        if a.order_id:
            if action=='checkin': return _rb.redirect(_rb.url_for('order_detail',order_id=a.order_id))
            _rb.abort(409)
        if a.status not in ('BOOKED','CONFIRMED','WAITING'):
            _rb.abort(409)

        if action=='confirm':
            a.status='CONFIRMED'
            a.confirmed_at=_rb.datetime.utcnow()
        elif action=='cancel':
            a.status='CANCELLED'
            a.cancelled_at=_rb.datetime.utcnow()
        elif action=='noshow':
            a.status='NO_SHOW'
        elif action=='checkin':
            proc=a.procedure
            device=a.device or _rb.route_device(a.branch_id,proc.modality)
            if not device:
                _rb.flash(f'No active {proc.modality} device is configured for this branch.','danger')
                return _rb.redirect(_rb.url_for('appointments'))

            # Prevent accidental duplicate order from repeated Check-in.
            existing=_rb.Order.query.filter_by(patient_id=a.patient_id,procedure_id=a.procedure_id,scheduled=a.scheduled).first()
            if existing:
                a.order_id=existing.id
                a.status='ARRIVED'
                a.checked_in_at=a.checked_in_at or _rb.datetime.utcnow()
                _rb.db.session.commit()
                return _rb.redirect(_rb.url_for('order_detail',order_id=existing.id))

            gross,contract_price,patient_share,company_share,_=_rb.price_order(proc,None)
            order=_rb.Order(
                accession=_rb.new_accession(),
                patient_id=a.patient_id,
                assignment_visit_id=a.assignment_visit_id,
                assignment_special_code=a.assignment_special_code,
                procedure_id=proc.id,
                branch_id=a.branch_id,
                device_id=device.id,
                modality=proc.modality,
                procedure=proc.name,
                station_ae=device.ae_title,
                scheduled=a.scheduled,
                # RB_WORK_ORDER_GATE_V2
                # Check-in creates a registered clinical order only.
                # MWL waits for explicit Work Order conversion.
                status='REGISTERED',
                gross_price=gross,
                contract_price=contract_price,
                patient_share=patient_share,
                company_share=company_share,
                paid_amount=0,
                created_by=_rb.current_user().id
            )
            _rb.db.session.add(order)
            _rb.db.session.flush()

            from registration_policy import assign_reserved_visit
            try:
                a.order_id=order.id
                assign_reserved_visit(order)
            except ValueError as exc:
                _rb.db.session.rollback();_rb.flash(str(exc),'danger');return _rb.redirect(_rb.url_for('appointments'))

            # RB_WORK_ORDER_GATE_V2
            # Patient arrival is retained on the appointment,
            # while MWL creation is deferred to Convert to Work Order.
            a.status='ARRIVED'
            a.checked_in_at=_rb.datetime.utcnow()
            _rb.audit('APPOINTMENT_CHECKIN','appointment',a.id,order.accession)
            _rb.db.session.commit()
            _rb.flash(f'Patient checked in. Accession: {order.accession}','success')
            return _rb.redirect(_rb.url_for('order_detail',order_id=order.id))
        else:
            _rb.abort(400)

        _rb.audit('APPOINTMENT_'+action.upper(),'appointment',a.id,a.status)
        _rb.db.session.commit()
        _rb.flash('Appointment updated successfully.','success')
        return _rb.redirect(_rb.url_for('appointments'))
    return appointment_action


def install_0422(_rb):
    @_rb.app.route('/appointments/<int:appointment_id>/edit',methods=['GET','POST'])
    @_rb.require_perm('appointments.manage')
    def appointment_edit(appointment_id):
        a=_rb.Appointment.query.filter_by(id=appointment_id).with_for_update().first_or_404()
        from registration_policy import require_registration_branch
        require_registration_branch(a.branch_id)
        if a.order_id or a.status not in ('BOOKED','CONFIRMED','WAITING'): _rb.abort(409)
        patient=_rb.Patient.query.filter_by(id=a.patient_id).with_for_update().first_or_404()
        # Patient demographics are shared by visits: never rewrite a converted case.
        locked=_rb.Order.query.filter(_rb.Order.patient_id==patient.id,_rb.Order.status.notin_(['REGISTERED','CANCELLED'])).first() is not None
        error=''
        if _rb.request.method=='POST':
            savepoint=_rb.db.session.begin_nested()
            try:
                if locked: raise ValueError('Patient data is locked because a visit has already been converted to a Work Order.')
                resolution=_rb.resolve_patient_dob(_rb.request.form,prefix='')
                values={key:(_rb.request.form.get(key) or '').strip() for key in ('name','phone','national_id','address','email','nationality','sex')}
                values['dob']=resolution.dob
                from registration_policy import validate_patient_fields
                validate_patient_fields(values)
                if not values['name']:raise ValueError('Patient name is required.')
                scheduled=_rb.datetime.fromisoformat(_rb.request.form.get('scheduled',''))
                proc=_rb.Procedure.query.filter_by(id=_rb.request.form.get('procedure_id',type=int),active=True).first()
                device=_rb.Device.query.filter_by(id=_rb.request.form.get('device_id',type=int),active=True).first()
                if not proc or not device or device.branch_id!=a.branch_id or device.modality.upper()!=proc.modality.upper():
                    raise ValueError('Choose an active examination and matching device in this branch.')
                if not _rb.procedure_available_in_branch(proc.id,a.branch_id):raise ValueError('Examination is not available in this branch.')
                visit=_rb.AssignmentVisit.query.filter_by(id=a.assignment_visit_id).first() if a.assignment_visit_id else None
                if visit and scheduled.date()!=visit.visit_date:raise ValueError('Keep the linked visit date; create a separate visit for another date.')
                if visit and visit.assignment_mode=='MANUAL':
                    doctor=_rb.User.query.filter_by(id=visit.preferred_doctor_id,active=True).first()
                    profile=_rb.DoctorAssignmentProfile.query.filter_by(user_id=visit.preferred_doctor_id).first()
                    allowed={x.strip().upper() for x in (profile.modalities or '').split(',') if x.strip()} if profile else set()
                    if not doctor or (allowed and proc.modality.upper() not in allowed):raise ValueError('Reserved doctor is not qualified for this examination.')
                    from assignment_distribution import validate_special_doctor
                    validate_special_doctor(_rb.Order(modality=proc.modality,procedure=proc.name,priority=a.priority,assignment_special_code=a.assignment_special_code),doctor)
                reason=_rb.booking_restriction_reason(a.branch,proc,device,scheduled,proc.duration_min or 20,exclude_appointment_id=a.id)
                if reason:raise ValueError(reason)
                _rb.acquire_booking_slot_lock(device.id,scheduled)
                if _rb.appointment_overlap(device.id,scheduled,proc.duration_min or 20,exclude_id=a.id):raise ValueError('The selected time conflicts with another booking.')
                for key in ('name','phone','national_id','address','email','sex'):setattr(patient,key,values[key])
                patient.dob=resolution.dob;patient.dob_estimated=resolution.estimated
                patient.worklist_name=_rb.arabic_to_latin_name(patient.name)
                extra=_rb.PatientDemographicsExtra.query.filter_by(patient_id=patient.id).first()
                if not extra:extra=_rb.PatientDemographicsExtra(patient_id=patient.id);_rb.db.session.add(extra)
                extra.nationality=values['nationality']
                a.scheduled=scheduled;a.procedure_id=proc.id;a.device_id=device.id;a.duration_min=proc.duration_min or 20
                _rb.audit('BOOKING_EDIT','appointment',a.id,'Booking and patient data updated before work-order conversion')
                savepoint.commit()
                _rb.db.session.commit()
                _rb.flash('Booking updated. / تم تعديل الحجز.','success')
                return _rb.redirect(_rb.url_for('schedule_calendar',date=scheduled.date().isoformat()))
            except (ValueError,TypeError) as exc:
                savepoint.rollback();error=str(exc)
        extra=_rb.PatientDemographicsExtra.query.filter_by(patient_id=patient.id).first()
        return _rb.render_template('booking_edit.html',booking=a,patient=patient,extra=extra,locked=locked,error=error,
            procedures=_rb.Procedure.query.filter_by(active=True).order_by(_rb.Procedure.name).all(),
            devices=_rb.Device.query.filter_by(active=True,branch_id=a.branch_id).order_by(_rb.Device.name).all()),422 if error else 200
    return appointment_edit


def install_0423(_rb):
    @_rb.app.post('/appointments/<int:appointment_id>/reschedule')
    @_rb.require_perm('appointments.manage')
    def appointment_reschedule(appointment_id):
        a=_rb.Appointment.query.filter_by(id=appointment_id).with_for_update().first_or_404()
        from registration_policy import require_registration_branch
        require_registration_branch(a.branch_id)
        if a.order_id or a.status not in ('BOOKED','CONFIRMED','WAITING'):
            return _rb.jsonify({'ok':False,'error':'Clinical workflow already started'}),409
        try:new_time=_rb.datetime.fromisoformat(_rb.request.form.get('scheduled',''))
        except Exception:return _rb.jsonify({'ok':False,'error':'Invalid date/time'}),400
        device_id=_rb.request.form.get('device_id',type=int) or a.device_id
        device=_rb.Device.query.get_or_404(device_id)
        if device.branch_id!=a.branch_id or device.modality.upper()!=a.procedure.modality.upper():
            return _rb.jsonify({'ok':False,'error':'Device/branch/modality mismatch'}),400
        if a.assignment_visit_id:
            visit=_rb.AssignmentVisit.query.filter_by(id=a.assignment_visit_id).first()
            if visit and new_time.date()!=visit.visit_date:
                return _rb.jsonify({'ok':False,'error':'Keep the linked visit date. Register a separate visit for another date.'}),409
        reason=_rb.booking_restriction_reason(a.branch,a.procedure,device,new_time,a.duration_min or a.procedure.duration_min,exclude_appointment_id=a.id)
        if reason:return _rb.jsonify({'ok':False,'error':reason}),409
        _rb.acquire_booking_slot_lock(device.id,new_time)
        conflict=_rb.appointment_overlap(device.id,new_time,a.duration_min or a.procedure.duration_min,exclude_id=a.id)
        if conflict:return _rb.jsonify({'ok':False,'error':f'Conflicts with appointment #{conflict.id}'}),409
        old=a.scheduled
        a.scheduled=new_time;a.device_id=device.id
        _rb.audit('APPOINTMENT_RESCHEDULE','appointment',a.id,f'{old}->{new_time}; device={device.id}')
        _rb.db.session.commit()
        return _rb.jsonify({'ok':True})
    return appointment_reschedule


def install_0424(_rb):
    @_rb.app.post('/appointments/<int:appointment_id>/status')
    @_rb.require_perm('appointments.manage')
    def appointment_status(appointment_id):
        a=_rb.Appointment.query.get_or_404(appointment_id)
        from registration_policy import require_registration_branch
        require_registration_branch(a.branch_id)
        target=(_rb.request.form.get('status') or '').upper()
        allowed={'WAITING','BOOKED','CONFIRMED','CANCELLED','NO_SHOW'}
        if target not in allowed:_rb.abort(400)
        if a.order_id or a.status not in ('BOOKED','CONFIRMED','WAITING'):
            _rb.abort(409)
        a.status=target;a.waiting_list=(target=='WAITING')
        _rb.audit('APPOINTMENT_STATUS','appointment',a.id,target);_rb.db.session.commit()
        return _rb.redirect(_rb.request.referrer or _rb.url_for('schedule_calendar'))
    return appointment_status


def install_0425(_rb):
    @_rb.app.route('/schedule/maintenance',methods=['POST'])
    @_rb.require_perm('devices.manage')
    def schedule_maintenance():
        device=_rb.Device.query.get_or_404(_rb.request.form.get('device_id',type=int))
        try:
            start_at=_rb.datetime.fromisoformat(_rb.request.form['start_at'])
            end_at=_rb.datetime.fromisoformat(_rb.request.form['end_at'])
        except Exception:_rb.abort(400)
        if end_at<=start_at:
            _rb.flash('Maintenance end must be after start.','danger');return _rb.redirect(_rb.request.referrer or _rb.url_for('schedule_calendar'))
        row=_rb.DeviceBlock(device_id=device.id,start_at=start_at,end_at=end_at,
                        reason=(_rb.request.form.get('reason') or 'MAINTENANCE').strip())
        _rb.db.session.add(row);_rb.audit('DEVICE_MAINTENANCE_BLOCK','device',device.id,f'{start_at}->{end_at}');_rb.db.session.commit()
        _rb.flash('Maintenance block saved.','success')
        return _rb.redirect(_rb.url_for('schedule_calendar',date=start_at.date().isoformat(),device_id=device.id))
    return schedule_maintenance


def install_0426(_rb):
    @_rb.app.route('/schedule/v2')
    @_rb.require_perm('appointments.view')
    def schedule_v2():
        return _rb.redirect(_rb.url_for('schedule_calendar',date=(_rb.request.args.get('date') or ''),branch_id=_rb.request.args.get('branch_id',type=int),device_id=_rb.request.args.get('device_id',type=int)))
    return schedule_v2


def install_0427(_rb):
    @_rb.app.route('/schedule/v2/book')
    @_rb.require_perm('appointments.manage')
    def schedule_v2_book_form():
        return _rb.redirect(_rb.url_for('schedule_calendar',date=(_rb.request.args.get('scheduled') or '')[:10],device_id=_rb.request.args.get('device_id',type=int)))
    return schedule_v2_book_form


def install_0428(_rb):
    @_rb.app.post('/schedule/v2/book')
    @_rb.require_perm('appointments.manage')
    def schedule_v2_book_submit():
        # Legacy-compatible POST path.
        # Keep the central booking safety contract in place even though
        # the visible UI is now unified on /schedule/calendar.
        try:
            scheduled=_rb.datetime.fromisoformat(_rb.request.form.get('scheduled') or '')
        except Exception:
            _rb.flash('Invalid date/time.','danger')
            return _rb.redirect(_rb.url_for('schedule_calendar'))

        device=_rb.Device.query.get_or_404(_rb.request.form.get('device_id',type=int))
        proc=_rb.Procedure.query.get_or_404(_rb.request.form.get('procedure_id',type=int))
        branch=_rb.Branch.query.get_or_404(_rb.request.form.get('branch_id',type=int))

        duration=max(5,int(proc.duration_min or 20))

        reason=_rb.booking_restriction_reason(
            branch,
            proc,
            device,
            scheduled,
            duration
        )
        if reason:
            _rb.flash(f'Booking blocked: {reason}','danger')
            return _rb.redirect(_rb.url_for(
                'schedule_calendar',
                date=scheduled.date().isoformat(),
                branch_id=branch.id,
                device_id=device.id
            ))

        # Reuse the unified booking endpoint instead of maintaining
        # a second registration/booking implementation.
        return _rb.schedule_book()
    return schedule_v2_book_submit


def install_0429(_rb):
    @_rb.app.post('/devices/<int:device_id>/booking-status')
    @_rb.require_perm('devices.manage')
    def device_booking_status(device_id):
        device=_rb.Device.query.get_or_404(device_id)
        status=(_rb.request.form.get('operational_status') or 'ACTIVE').upper()
        if status not in _rb.DEVICE_BOOKING_STATUSES:
            _rb.abort(400)
        device.operational_status=status
        device.booking_enabled=_rb.request.form.get('booking_enabled')=='1'
        start=(_rb.request.form.get('workday_start') or device.workday_start or '08:00').strip()
        end=(_rb.request.form.get('workday_end') or device.workday_end or '22:00').strip()
        if _rb._hhmm_to_minutes(end,'22:00')<=_rb._hhmm_to_minutes(start,'08:00'):
            _rb.flash('Working hours are invalid.','danger')
            return _rb.redirect(_rb.request.referrer or _rb.url_for('schedule_v2'))
        device.workday_start=start;device.workday_end=end
        _rb.audit('DEVICE_BOOKING_STATUS','device',device.id,f'{status}; booking={device.booking_enabled}; {start}-{end}')
        _rb.db.session.commit()
        _rb.flash('Device booking status updated.','success')
        return _rb.redirect(_rb.request.referrer or _rb.url_for('schedule_v2'))
    return device_booking_status


def install_0430(_rb):
    @_rb.app.route('/admin/booking-availability',methods=['GET','POST'])
    @_rb.require_perm('devices.manage')
    def admin_booking_availability():
        if _rb.request.method=='POST':
            branch_id=_rb.request.form.get('branch_id',type=int)
            procedure_id=_rb.request.form.get('procedure_id',type=int)
            active=_rb.request.form.get('active')=='1'
            branch=_rb.Branch.query.get_or_404(branch_id)
            proc=_rb.Procedure.query.get_or_404(procedure_id)
            row=_rb.ProcedureBranch.query.filter_by(branch_id=branch.id,procedure_id=proc.id).first()
            if not row:
                row=_rb.ProcedureBranch(branch_id=branch.id,procedure_id=proc.id)
                _rb.db.session.add(row)
            row.active=active
            _rb.audit('BOOKING_AVAILABILITY_UPDATE','procedure_branch',row.id or '',
                  f'branch={branch.id}; procedure={proc.id}; active={active}')
            _rb.db.session.commit()
            _rb.flash('Booking availability updated.','success')
            return _rb.redirect(_rb.url_for('admin_booking_availability',branch_id=branch.id))

        branch_id=_rb.request.args.get('branch_id',type=int)
        branches=_rb.Branch.query.order_by(_rb.Branch.name).all()
        if not branch_id and branches:
            branch_id=branches[0].id

        rows=[]
        if branch_id:
            for p in _rb.Procedure.query.order_by(_rb.Procedure.modality,_rb.Procedure.name).all():
                mapping=_rb.ProcedureBranch.query.filter_by(branch_id=branch_id,procedure_id=p.id).first()
                rows.append({'procedure':p,'available':True if mapping is None else bool(mapping.active)})

        return _rb.render_template('admin_booking_availability.html',
            branches=branches,branch_id=branch_id,rows=rows)
    return admin_booking_availability


def install_0431(_rb):
    @_rb.app.get('/api/booking/smart-availability')
    @_rb.require_perm('appointments.view')
    def api_smart_booking_availability():
        branch_id=_rb.request.args.get('branch_id',type=int)
        procedure_id=_rb.request.args.get('procedure_id',type=int)
        requested_device_id=_rb.request.args.get('device_id',type=int)
        date_text=(_rb.request.args.get('date') or '').strip()

        if not branch_id:
            return _rb.jsonify({
                'ok':False,
                'error':'branch_id required'
            }),400

        if not procedure_id:
            return _rb.jsonify({
                'ok':False,
                'error':'procedure_id required'
            }),400

        branch=_rb.Branch.query.get(branch_id)
        procedure=_rb.Procedure.query.get(procedure_id)

        if not branch or not branch.active:
            return _rb.jsonify({
                'ok':False,
                'error':'branch unavailable'
            }),404

        if not procedure or not procedure.active:
            return _rb.jsonify({
                'ok':False,
                'error':'procedure unavailable'
            }),404

        if not _rb.procedure_available_in_branch(
            procedure.id,
            branch.id
        ):
            return _rb.jsonify({
                'ok':False,
                'error':'procedure not available in branch'
            }),409

        try:
            selected=(
                _rb.datetime.strptime(date_text,'%Y-%m-%d').date()
                if date_text
                else _rb.datetime.now().date()
            )
        except ValueError:
            return _rb.jsonify({
                'ok':False,
                'error':'invalid date'
            }),400

        modality=(procedure.modality or '').strip().upper()

        devices_q=_rb.Device.query.filter_by(
            branch_id=branch.id,
            active=True,
        )

        if modality:
            devices_q=devices_q.filter(
                _rb.db.func.upper(_rb.Device.modality)==modality
            )

        if requested_device_id:
            devices_q=devices_q.filter(
                _rb.Device.id==requested_device_id
            )

        devices=devices_q.order_by(
            _rb.Device.priority.asc(),
            _rb.Device.name.asc(),
            _rb.Device.id.asc(),
        ).all()

        duration=max(
            5,
            int(procedure.duration_min or 20)
        )

        results=[]

        for device in devices:

            operational=(
                getattr(device,'operational_status','ACTIVE')
                or 'ACTIVE'
            ).upper()

            booking_enabled=bool(
                getattr(device,'booking_enabled',True)
            )

            device_result={
                'id':device.id,
                'name':device.name,
                'room':device.room or '',
                'modality':device.modality or '',
                'priority':device.priority,
                'booking_enabled':booking_enabled,
                'operational_status':operational,
                'slots':[],
            }

            if (
                not booking_enabled
                or operational!='ACTIVE'
            ):
                results.append(device_result)
                continue

            slots=_rb.booking_v2_slots(
                selected,
                device,
                slot_minutes=15,
            )

            for slot in slots:

                reason=_rb.booking_restriction_reason(
                    branch,
                    procedure,
                    device,
                    slot,
                    duration,
                )

                if reason:
                    continue

                device_result['slots'].append({
                    'start':slot.isoformat(),
                    'time':slot.strftime('%H:%M'),
                    'duration_min':duration,
                })

            results.append(device_result)

        available=[
            item
            for item in results
            if item['slots']
        ]

        best=None

        if available:
            best=min(
                available,
                key=lambda item:(
                    item['slots'][0]['start'],
                    item['priority'],
                    item['id'],
                )
            )

        return _rb.jsonify({
            'ok':True,
            'branch':{
                'id':branch.id,
                'name':branch.name,
            },
            'procedure':{
                'id':procedure.id,
                'code':procedure.code,
                'name':procedure.name,
                'name_ar':procedure.name_ar,
                'modality':procedure.modality,
                'duration_min':duration,
            },
            'date':selected.isoformat(),
            'devices':results,
            'available_device_count':len(available),
            'best_device_id':best['id'] if best else None,
            'best_slot':(
                best['slots'][0]
                if best
                else None
            ),
        })
    return api_smart_booking_availability


def install_0432(_rb):
    @_rb.app.post('/admin/booking-availability/seed')
    @_rb.require_perm('devices.manage')
    def admin_booking_availability_seed():
        added=_rb.ensure_default_procedure_branch_mappings()
        _rb.audit('BOOKING_AVAILABILITY_SEED','procedure_branch','',f'added={added}')
        _rb.db.session.commit()
        _rb.flash(f'Default availability created for {added} branch/procedure combination(s).','success')
        return _rb.redirect(_rb.url_for('admin_booking_availability'))
    return admin_booking_availability_seed


def install_0437(_rb):
    @_rb.app.get('/admin/booking-control-center')
    @_rb.require_perm('devices.manage')
    def admin_booking_control_center():
        now=_rb.datetime.now()

        devices=_rb.Device.query.order_by(_rb.Device.modality,_rb.Device.name).all()
        active_devices=[d for d in devices if bool(getattr(d,'active',True))]
        booking_enabled_devices=[
            d for d in active_devices
            if bool(getattr(d,'booking_enabled',True))
        ]

        active_device_blocks=_rb.DeviceBlock.query.filter(
            _rb.DeviceBlock.start_at <= now,
            _rb.DeviceBlock.end_at > now
        ).all()

        active_booking_blocks=_rb.BookingBlock.query.filter_by(active=True).filter(
            _rb.BookingBlock.start_at <= now,
            _rb.BookingBlock.end_at > now
        ).all()

        today_start=_rb.datetime.combine(now.date(),_rb.datetime.min.time())
        tomorrow=today_start+_rb.timedelta(days=1)

        appointments_today=_rb.Appointment.query.filter(
            _rb.Appointment.scheduled >= today_start,
            _rb.Appointment.scheduled < tomorrow,
            _rb.Appointment.status.notin_(['CANCELLED','NO_SHOW'])
        ).count()

        device_rows=[]
        active_device_block_ids={b.device_id for b in active_device_blocks if b.device_id}

        for d in devices:
            status=(getattr(d,'operational_status','ACTIVE') or 'ACTIVE').upper()
            current_block=next(
                (b for b in active_device_blocks if b.device_id==d.id),
                None
            )

            device_rows.append({
                'id':d.id,
                'name':d.name,
                'modality':d.modality,
                'ae_title':d.ae_title,
                'room':getattr(d,'room','') or '',
                'branch':d.branch.name if getattr(d,'branch',None) else '',
                'active':bool(getattr(d,'active',True)),
                'booking_enabled':bool(getattr(d,'booking_enabled',True)),
                'operational_status':status,
                'workday_start':getattr(d,'workday_start','08:00') or '08:00',
                'workday_end':getattr(d,'workday_end','22:00') or '22:00',
                'blocked_now':d.id in active_device_block_ids,
                'block_reason':current_block.reason if current_block else '',
            })

        return _rb.render_template(
            'admin_booking_control_center.html',
            now=now,
            device_rows=device_rows,
            total_devices=len(devices),
            active_devices=len(active_devices),
            booking_enabled_devices=len(booking_enabled_devices),
            active_device_blocks=len(active_device_blocks),
            active_booking_blocks=len(active_booking_blocks),
            appointments_today=appointments_today,
        )
    return admin_booking_control_center


def install_0438(_rb):
    @_rb.app.route('/admin/booking-control',methods=['GET','POST'])
    @_rb.require_perm('devices.manage')
    def admin_booking_control():
        if _rb.request.method=='POST':
            try:
                start_at=_rb.datetime.fromisoformat(_rb.request.form.get('start_at') or '')
                end_at=_rb.datetime.fromisoformat(_rb.request.form.get('end_at') or '')
            except Exception:
                _rb.flash('Invalid date.','danger');return _rb.redirect(_rb.url_for('admin_booking_control'))
            block_type=(_rb.request.form.get('block_type') or 'OTHER').upper()
            branch_id=_rb.request.form.get('branch_id',type=int)
            device_id=_rb.request.form.get('device_id',type=int)
            procedure_id=_rb.request.form.get('procedure_id',type=int)
            user_id=_rb.request.form.get('user_id',type=int)
            validation_error=_rb.validate_booking_block_scope(
                block_type=block_type,branch_id=branch_id,device_id=device_id,
                procedure_id=procedure_id,user_id=user_id,
                start_at=start_at,end_at=end_at,
            )
            if validation_error:
                _rb.flash(validation_error,'danger');return _rb.redirect(_rb.url_for('admin_booking_control'))
            target_user=_rb.User.query.get(user_id) if user_id else None
            target_role=(target_user.role.code if target_user and target_user.role else '').upper()
            if block_type=='DOCTOR' and target_role not in ('DOCTOR','RADIOLOGIST'):
                _rb.flash('The selected user is not a doctor/radiologist.','danger');return _rb.redirect(_rb.url_for('admin_booking_control'))
            if block_type=='TECHNICIAN' and target_role!='TECHNICIAN':
                _rb.flash('The selected user is not a technician.','danger');return _rb.redirect(_rb.url_for('admin_booking_control'))
            row=_rb.BookingBlock(block_type=block_type,branch_id=branch_id,device_id=device_id,procedure_id=procedure_id,user_id=user_id,start_at=start_at,end_at=end_at,reason_code=(_rb.request.form.get('reason_code') or 'OTHER').upper(),reason_text=(_rb.request.form.get('reason_text') or '').strip(),active=True,created_by=_rb.current_user().id)
            _rb.db.session.add(row);_rb.db.session.commit();return _rb.redirect(_rb.url_for('admin_booking_control'))
        return _rb.render_template('admin_booking_control.html',rows=_rb.BookingBlock.query.order_by(_rb.BookingBlock.start_at.desc()).limit(500).all(),branches=_rb.Branch.query.order_by(_rb.Branch.name).all(),devices=_rb.Device.query.order_by(_rb.Device.modality,_rb.Device.name).all(),procedures=_rb.Procedure.query.order_by(_rb.Procedure.modality,_rb.Procedure.name).all(),users=_rb.User.query.filter_by(active=True).order_by(_rb.User.full_name).all(),reason_codes=_rb.BOOKING_BLOCK_REASONS)
    return admin_booking_control


def install_0439(_rb):
    @_rb.app.post('/admin/booking-control/<int:block_id>/deactivate')
    @_rb.require_perm('devices.manage')
    def admin_booking_control_deactivate(block_id):
        row=_rb.BookingBlock.query.get_or_404(block_id)
        if row.active:
            row.active=False
            _rb.audit('BOOKING_BLOCK_DEACTIVATE','booking_block',row.id,row.reason_text or row.reason_code)
            _rb.db.session.commit()
            _rb.flash('Booking block deactivated.','success')
        return _rb.redirect(_rb.url_for('admin_booking_control'))
    return admin_booking_control_deactivate


def install_0445(_rb):
    @_rb.app.post('/orders/<int:order_id>/journey/<stage>')
    @_rb.require_perm('workflow.override')
    def order_journey_stage(order_id,stage):
        # Legacy endpoint retained for links; Journey itself is read-only/derived.
        o=_rb.Order.query.get_or_404(order_id)
        requested=(stage or '').upper()
        if requested not in _rb.JOURNEY_STAGES:
            _rb.abort(400)

        projected=_rb.journey_snapshot(o)['stage']
        _rb.flash(
            f'Patient Journey is derived from clinical state. Current stage: {projected}.',
            'info' if requested==projected else 'warning',
        )
        return _rb.redirect(_rb.request.referrer or _rb.url_for('operations_journey'))
    return order_journey_stage


def install_0446(_rb):
    @_rb.app.get('/operations/booking-board')
    @_rb.require_perm('appointments.manage')
    def operations_booking_board():
        try:day=_rb.datetime.fromisoformat(_rb.request.args.get('date')).date() if _rb.request.args.get('date') else _rb.datetime.now().date()
        except Exception:day=_rb.datetime.now().date()
        bid=_rb.request.args.get('branch_id',type=int)
        return _rb.render_template('operations_booking_board.html',day=day,cards=_rb.smart_booking_cards(day,bid),branches=_rb.Branch.query.filter_by(active=True).order_by(_rb.Branch.name).all(),branch_id=bid)
    return operations_booking_board


def install_0454(_rb):
    @_rb.app.route('/patients/<int:patient_id>/documents',methods=['GET','POST'])
    @_rb.login_required
    def patient_documents(patient_id):
        patient=_rb.Patient.query.get_or_404(patient_id)
        if _rb.request.method=='POST':
            f=_rb.request.files.get('file')
            dtype=(_rb.request.form.get('document_type') or 'OTHER').upper()
            if dtype not in _rb.DOCUMENT_TYPES or not f or not f.filename:
                _rb.flash('Document type and file are required.','danger')
                return _rb.redirect(_rb.url_for('patient_documents',patient_id=patient.id))
            ext=_rb.os.path.splitext(f.filename)[1].lower()
            if ext not in ('.pdf','.jpg','.jpeg','.png','.doc','.docx','.txt'):
                _rb.flash('Unsupported document type.','danger')
                return _rb.redirect(_rb.url_for('patient_documents',patient_id=patient.id))
            folder=_rb.os.path.join(_rb.ATTACHMENT_DIR,'patient-documents',str(patient.id))
            _rb.os.makedirs(folder,exist_ok=True)
            stored_name=_rb.generated_attachment_filename(_rb.intake.id,dtype,f.filename)
            path=_rb.os.path.join(folder,stored_name)
            f.save(path)
            order_id=_rb.request.form.get('order_id',type=int)
            text,status=_rb.extract_document_text_basic(path)
            meta=_rb.DOCUMENT_TYPES[dtype]
            doc=_rb.PatientDocument(
              patient_id=patient.id,order_id=order_id,document_type=dtype,category=meta[2],
              reference_no=(_rb.request.form.get('reference_no') or '').strip(),
              file_path=path,original_name=f.filename,extracted_text=text,
              extraction_status=status,uploaded_by=_rb.current_user().id
            )
            _rb.db.session.add(doc);_rb.db.session.flush()
            _rb.build_document_matches(doc)
            _rb.audit('PATIENT_DOCUMENT_UPLOAD','patient',patient.id,f'{dtype}:{doc.id}')
            _rb.db.session.commit()
            _rb.flash('Document uploaded.','success')
            return _rb.redirect(_rb.url_for('patient_documents',patient_id=patient.id))
        docs=_rb.PatientDocument.query.filter_by(patient_id=patient.id).order_by(_rb.PatientDocument.created_at.desc()).all()
        orders=_rb.Order.query.filter_by(patient_id=patient.id).order_by(_rb.Order.id.desc()).all()
        return _rb.render_template('patient_documents.html',patient=patient,documents=docs,orders=orders,document_types=_rb.DOCUMENT_TYPES)
    return patient_documents


def install_0455(_rb):
    @_rb.app.get('/patients/<int:patient_id>/timeline')
    @_rb.login_required
    def patient_timeline(patient_id):
        patient=_rb.Patient.query.get_or_404(patient_id)
        return _rb.render_template('patient_timeline.html',patient=patient,events=_rb.document_timeline(patient))
    return patient_timeline


def install_0474(_rb):
    @_rb.app.get('/orders/<int:order_id>/attachments')
    @_rb.require_perm('orders.view')
    def order_attachments(order_id):
        order=_rb.Order.query.get_or_404(order_id)
        attachments=_rb.Attachment.query.filter_by(order_id=order.id).order_by(
            _rb.Attachment.created_at.desc(), _rb.Attachment.id.desc()
        ).all()
        return _rb.render_template('order_attachments.html', order=order, attachments=attachments)
    return order_attachments


def install_0475(_rb):
    @_rb.app.route('/orders/<int:order_id>/sticker')
    @_rb.require_perm('orders.view')
    def order_sticker(order_id):
        order=_rb.Order.query.get_or_404(order_id)
        template=_rb.get_default_sticker_template();profile=_rb.get_company_profile()
        portal_url=_rb._portal_url_for_order(order);_rb.db.session.commit()
        from reportlab.lib.units import mm
        from reportlab.lib.utils import ImageReader
        width=float(template.width_mm or 70)*mm;height=float(template.height_mm or 45)*mm
        buf=_rb.io.BytesIO();c=_rb.canvas.Canvas(buf,pagesize=(width,height));c.setTitle(f"Sticker {order.accession}")
        c.setFont('Helvetica-Bold',8);c.drawString(4*mm,height-6*mm,(profile.name_en or 'RIS')[:38])
        fields=_rb._sticker_fields(template);labels=_rb._sticker_labels(template);top=height-12*mm;line=4.2*mm
        for idx,key in enumerate(fields[:7]):
            y=top-idx*line;c.setFont('Helvetica-Bold',5.5);c.drawString(4*mm,y,(labels.get(key) or {}).get('en',key)+':')
            c.setFont('Helvetica',6.4);c.drawString(22*mm,y,_rb._sticker_value(order,key)[:30])
        if template.show_qr:
            qr=_rb.qrcode.QRCode(version=3,box_size=4,border=1);qr.add_data(portal_url);qr.make(fit=True)
            img=qr.make_image(fill_color="black",back_color="white");qbuf=_rb.io.BytesIO();img.save(qbuf,format='PNG');qbuf.seek(0)
            size=min(21*mm,height-15*mm);c.drawImage(ImageReader(qbuf),width-size-3*mm,10*mm,size,size,mask='auto')
        if template.show_barcode:
            bc=_rb.code128.Code128(order.accession,barHeight=6*mm,barWidth=.22*mm);bc.drawOn(c,4*mm,3*mm)
        c.setFont('Helvetica',5);c.drawRightString(width-3*mm,3*mm,'Scan QR for Results & Images')
        c.showPage();c.save();buf.seek(0)
        return _rb.send_file(buf,as_attachment=False,download_name=f'{order.accession}-sticker.pdf',mimetype='application/pdf')
    return order_sticker


def install_0476(_rb):
    @_rb.app.route('/orders/<int:order_id>/sticker/preview')
    @_rb.require_perm('orders.view')
    def order_sticker_preview(order_id):
        order=_rb.Order.query.get_or_404(order_id);template=_rb.get_default_sticker_template()
        portal_url=_rb._portal_url_for_order(order);_rb.db.session.commit()
        return _rb.render_template('sticker_preview.html',order=order,template=template,fields=_rb._sticker_fields(template),
          labels=_rb._sticker_labels(template),portal_url=portal_url,company=_rb.get_company_profile())
    return order_sticker_preview


def install_0492(_rb):
    @_rb.app.get('/api/command-center/case/<int:order_id>/graph-v3')
    @_rb.require_perm('audit.view')
    def api_command_center_case_graph_v3(order_id):
        order = _rb.Order.query.get_or_404(order_id)

        def iso(value):
            return value.isoformat() if value else None

        def val(obj, name, default=None):
            return getattr(obj, name, default) if obj is not None else default

        def resolution(code):
            code = str(code or '').upper()

            if code in (
                'MISSING_PACS',
                'INCOMPLETE_IMAGES',
                'MISSING_SERIES',
                'WRONG_PROTOCOL',
                'MOTION_ARTIFACT',
                'ADDITIONAL_IMAGING',
            ):
                return {
                    'owner_role': 'TECHNICIAN',
                    'url': _rb.url_for(
                        'technician_case_workspace',
                        order_id=order.id
                    ),
                }

            if code in (
                'REVIEW_REQUIRED',
                'UNMATCHED',
                'DEMOGRAPHIC_MISMATCH',
                'PACS_DEMOGRAPHIC_REVIEW_REQUIRED',
            ):
                return {
                    'owner_role': 'RECEPTION',
                    'url': _rb.url_for('pacs_reconciliation'),
                }

            if code in (
                'MISSING_HISTORY',
                'MISSING_DOCUMENTS',
                'MISSING_ATTACHMENTS',
                'MISSING_REFERRAL',
            ):
                return {
                    'owner_role': 'RECEPTION',
                    'url': _rb.url_for('order_detail', order_id=order.id),
                }

            if code in (
                'NO_CANDIDATE',
                'TIMEOUT',
                'ASSIGNMENT_TIMEOUT',
            ):
                return {
                    'owner_role': 'ASSIGNMENT',
                    'url': _rb.url_for('assignment_dashboard'),
                }

            if code.startswith('REPORT_') or code.startswith('ONLYOFFICE_'):
                return {
                    'owner_role': 'DOCTOR',
                    'url': _rb.url_for('report_editor', order_id=order.id),
                }

            return {
                'owner_role': '',
                'url': _rb.url_for('order_detail', order_id=order.id),
            }

        readiness = None
        if 'CaseReadiness' in _rb.namespace():
            readiness = (
                _rb.CaseReadiness.query
                .filter_by(order_id=order.id)
                .order_by(_rb.CaseReadiness.id.desc())
                .first()
            )

        pacs_inbox = None
        if 'PacsStudyInbox' in _rb.namespace():
            q = _rb.PacsStudyInbox.query
            if hasattr(_rb.PacsStudyInbox, 'order_id'):
                pacs_inbox = (
                    q.filter_by(order_id=order.id)
                    .order_by(_rb.PacsStudyInbox.id.desc())
                    .first()
                )

        pacs_match = None
        if 'PacsStudyMatch' in _rb.namespace():
            q = _rb.PacsStudyMatch.query
            if hasattr(_rb.PacsStudyMatch, 'order_id'):
                pacs_match = (
                    q.filter_by(order_id=order.id)
                    .order_by(_rb.PacsStudyMatch.id.desc())
                    .first()
                )

        assignment = (
            _rb.CaseAssignment.query
            .filter_by(order_id=order.id, active=True)
            .order_by(_rb.CaseAssignment.id.desc())
            .first()
        )

        doctor = val(assignment, 'doctor')
        doctor_presence = None
        if doctor is not None:
            st = (
                _rb.DoctorAvailabilityState.query
                .filter_by(user_id=doctor.id)
                .first()
            )

            effective_state = val(
                st,
                'state',
                'UNKNOWN'
            )

            busy_until = val(
                st,
                'busy_until'
            )

            if (
                effective_state == 'BUSY'
                and busy_until
                and busy_until <= _rb.datetime.utcnow()
            ):
                effective_state = 'AVAILABLE'

            last_seen_at = val(
                st,
                'last_seen_at'
            )

            online = bool(
                last_seen_at
                and last_seen_at
                    >= _rb.datetime.utcnow() - _rb.timedelta(minutes=5)
                and effective_state != 'OFFLINE'
            )

            doctor_presence = {
                'user_id': doctor.id,
                'username': val(
                    doctor,
                    'username',
                    ''
                ),
                'full_name': val(
                    doctor,
                    'full_name',
                    ''
                ),
                'state': effective_state,
                'last_seen_at': iso(
                    last_seen_at
                ),
                'online': online,
                'online_window_minutes': 5,
            }

        blockers = []

        blocker_fields = (
            ('missing_pacs', 'MISSING_PACS'),
            ('incomplete_images', 'INCOMPLETE_IMAGES'),
            ('missing_series', 'MISSING_SERIES'),
            ('missing_history', 'MISSING_HISTORY'),
            ('missing_attachments', 'MISSING_ATTACHMENTS'),
            ('missing_documents', 'MISSING_DOCUMENTS'),
        )

        for field, code in blocker_fields:
            if bool(val(readiness, field, False)):
                target = resolution(code)
                blockers.append({
                    'code': code,
                    'owner_role': target['owner_role'],
                    'resolution_url': target['url'],
                })

        workflow_events = (
            _rb.CaseWorkflowEvent.query
            .filter_by(order_id=order.id)
            .order_by(_rb.CaseWorkflowEvent.created_at.asc())
            .all()
        )

        event_rows = []
        for ev in workflow_events:
            code = (
                val(ev, 'reason_code', '')
                or val(ev, 'event_type', '')
            )
            target = resolution(code)

            event_rows.append({
                'id': ev.id,
                'event_type': val(ev, 'event_type', ''),
                'reason_code': val(ev, 'reason_code', ''),
                'owner_role': (
                    val(ev, 'owner_role', '')
                    or target['owner_role']
                ),
                'note': val(ev, 'note', ''),
                'created_at': iso(val(ev, 'created_at')),
                'resolution_url': target['url'],
            })

        report = val(order, 'report')

        pacs_state = (
            val(pacs_inbox, 'state')
            or val(order, 'pacs_status')
            or 'WAITING'
        )

        match_state = (
            val(pacs_match, 'status')
            or val(pacs_match, 'state')
            or val(pacs_inbox, 'match_method')
            or 'WAITING'
        )

        readiness_state = 'READY'
        if readiness is None:
            readiness_state = 'NOT_CHECKED'
        elif blockers:
            readiness_state = 'BLOCKED'

        assignment_state = (
            'ASSIGNED'
            if assignment is not None
            else 'UNASSIGNED'
        )

        report_state = (
            val(report, 'status', 'UNREPORTED')
            if report is not None
            else 'UNREPORTED'
        )

        nodes = [
            {
                'key': 'ORDER',
                'state': val(order, 'status', 'REGISTERED'),
                'resolution_url': _rb.url_for(
                    'order_detail',
                    order_id=order.id
                ),
            },
            {
                'key': 'MWL',
                'state': (
                    'ERROR'
                    if str(val(order, 'status', '')).upper()
                    in ('MWL_ERROR', 'ROUTING_ERROR')
                    else 'REQUESTED'
                ),
                'resolution_url': _rb.url_for(
                    'order_detail',
                    order_id=order.id
                ),
            },
            {
                'key': 'EXAM',
                'state': val(order, 'exam_status', 'WAITING'),
                'resolution_url': _rb.url_for(
                    'technician_case_workspace',
                    order_id=order.id
                ),
            },
            {
                'key': 'PACS',
                'state': pacs_state,
                'details': {
                    'image_count': int(
                        val(order, 'pacs_image_count', 0) or 0
                    ),
                    'study_id': val(order, 'pacs_study_id', ''),
                    'last_seen_at': iso(
                        val(order, 'pacs_last_seen_at')
                    ),
                },
                'resolution_url': _rb.url_for(
                    'pacs_case_actions',
                    order_id=order.id
                ),
            },
            {
                'key': 'MATCHING',
                'state': match_state,
                'resolution_url': _rb.url_for('pacs_reconciliation'),
            },
            {
                'key': 'READINESS',
                'state': readiness_state,
                'blockers': blockers,
                'resolution_url': _rb.url_for(
                    'case_readiness_dashboard'
                ),
            },
            {
                'key': 'ASSIGNMENT',
                'state': assignment_state,
                'details': {
                    'assignment_type': val(
                        assignment,
                        'assignment_type',
                        ''
                    ),
                    'assigned_at': iso(
                        val(assignment, 'assigned_at')
                    ),
                    'doctor': doctor_presence,
                },
                'resolution_url': _rb.url_for(
                    'assignment_dashboard'
                ),
            },
            {
                'key': 'REPORTING',
                'state': report_state,
                'details': {
                    'radiologist': val(report, 'radiologist', ''),
                    'verified_at': iso(
                        val(report, 'verified_at')
                    ),
                    'finalized_at': iso(
                        val(report, 'finalized_at')
                    ),
                },
                'resolution_url': _rb.url_for(
                    'report_editor',
                    order_id=order.id
                ),
            },
        ]

        return _rb.jsonify({
            'schema': 'radbridge.command_center.case_graph.v3',
            'read_only': True,
            'order': {
                'id': order.id,
                'accession': val(order, 'accession', ''),
                'modality': val(order, 'modality', ''),
                'procedure': val(order, 'procedure', ''),
                'status': val(order, 'status', ''),
            },
            'nodes': nodes,
            'blockers': blockers,
            'events': event_rows,
            'assigned_doctor': doctor_presence,
        })
    return api_command_center_case_graph_v3


def install_0523(_rb):
    @_rb.app.route('/orders/<int:order_id>/delivery/<item_type>',methods=['POST'])
    @_rb.require_perm('delivery.manage')
    def mark_delivery(order_id,item_type):
        from delivery_policy import METHODS,delivery_readiness
        from registration_policy import require_registration_branch
        o=_rb.Order.query.filter_by(id=order_id).with_for_update().first_or_404()
        require_registration_branch(o.branch_id)
        item=item_type.upper()
        if item not in METHODS:_rb.abort(400)
        method=(_rb.request.form.get('delivery_method') or '').strip().upper()
        recipient=(_rb.request.form.get('recipient_name') or '').strip()
        if method not in METHODS[item]:_rb.abort(400,description='Invalid delivery method')
        if len(recipient)>160 or len(_rb.request.form.get('recipient_phone',''))>40 or len(_rb.request.form.get('notes',''))>500:_rb.abort(400,description='Delivery details are too long')
        if not recipient:
            _rb.flash('Recipient name is required. / اسم المستلم مطلوب.','danger')
            return _rb.redirect(_rb.url_for('order_detail',order_id=o.id)),303
        if getattr(o,item.lower()+'_delivered',False):
            _rb.flash('This item has already been recorded as delivered. / تم تسجيل تسليم هذا العنصر بالفعل.','warning')
            return _rb.redirect(_rb.url_for('order_detail',order_id=o.id)),303
        _rb.Report.query.filter_by(order_id=o.id).with_for_update().all()
        allowed,reason=delivery_readiness(o,item,live=True)
        if not allowed:
            _rb.flash(reason,'danger')
            return _rb.redirect(_rb.url_for('order_detail',order_id=o.id)),303
        ev=_rb.DeliveryEvent(order_id=o.id,item_type=item,delivery_method=method,
            recipient_name=recipient,recipient_phone=(_rb.request.form.get('recipient_phone') or '').strip(),
            delivered_by=_rb.current_user().id,notes=(_rb.request.form.get('notes') or '').strip())
        _rb.db.session.add(ev)
        now=_rb.datetime.utcnow()
        if item=='REPORT':o.report_delivered=True;o.report_delivered_at=now
        else:o.images_delivered=True;o.images_delivered_at=now
        _rb.audit('DELIVERY_'+item,'order',o.id,method)
        _rb.db.session.commit()
        _rb.flash('Delivery recorded. / تم تسجيل التسليم.','success')
        return _rb.redirect(_rb.url_for('order_detail',order_id=o.id)),303
    return mark_delivery


def install_0552(_rb):
    @_rb.app.route('/admin/device-schedules', methods=['GET','POST'])
    @_rb.require_perm('devices.manage')
    def admin_device_schedules():
        if _rb.request.method == 'POST':
            device_id = int(_rb.request.form['device_id'])
            weekday = int(_rb.request.form['weekday'])
            row = _rb.DeviceSchedule.query.filter_by(device_id=device_id, weekday=weekday).first()
            if not row:
                row = _rb.DeviceSchedule(device_id=device_id, weekday=weekday)
                _rb.db.session.add(row)
            row.start_time = _rb.request.form.get('start_time','09:00')
            row.end_time = _rb.request.form.get('end_time','21:00')
            row.break_start = _rb.request.form.get('break_start','')
            row.break_end = _rb.request.form.get('break_end','')
            row.active = True
            _rb.db.session.commit()
            _rb.audit('DEVICE_SCHEDULE_SAVE','device',device_id,f'weekday={weekday}')
            _rb.db.session.commit()
            _rb.flash('Device schedule saved.','success')
            return _rb.redirect(_rb.url_for('admin_device_schedules'))
        rows = _rb.DeviceSchedule.query.order_by(_rb.DeviceSchedule.device_id,_rb.DeviceSchedule.weekday).all()
        blocks = _rb.DeviceBlock.query.order_by(_rb.DeviceBlock.start_at.desc()).limit(200).all()
        devices = _rb.Device.query.order_by(_rb.Device.modality,_rb.Device.name).all()
        return _rb.render_template('admin_device_schedules.html',rows=rows,blocks=blocks,devices=devices)
    return admin_device_schedules


def install_0553(_rb):
    @_rb.app.route('/admin/device-blocks', methods=['POST'])
    @_rb.require_perm('devices.manage')
    def admin_device_blocks():
        device_id = int(_rb.request.form['device_id'])
        start_at = _rb.datetime.fromisoformat(_rb.request.form['start_at'])
        end_at = _rb.datetime.fromisoformat(_rb.request.form['end_at'])
        if end_at <= start_at:
            _rb.flash('Block end time must be after start time.','danger')
            return _rb.redirect(_rb.url_for('admin_device_schedules'))
        b = _rb.DeviceBlock(
            device_id=device_id,
            start_at=start_at,
            end_at=end_at,
            reason=_rb.request.form.get('reason','Maintenance').strip() or 'Maintenance'
        )
        _rb.db.session.add(b)
        _rb.audit('DEVICE_BLOCK_CREATE','device',device_id,b.reason)
        _rb.db.session.commit()
        _rb.flash('Device time blocked.','success')
        return _rb.redirect(_rb.url_for('admin_device_schedules'))
    return admin_device_blocks


def install_0559(_rb):
    @_rb.app.route('/admin/devices/<int:device_id>/edit',methods=['POST'])
    @_rb.require_perm('devices.manage')
    def admin_device_edit(device_id):
        d=_rb.Device.query.get_or_404(device_id)
        d.name=_rb.request.form['name'].strip(); d.ae_title=_rb.request.form['ae_title'].strip().upper()
        d.ip=_rb.request.form.get('ip','').strip(); d.port=int(_rb.request.form.get('port') or 104)
        d.priority=int(_rb.request.form.get('priority') or 100); d.active=_rb.request.form.get('active')=='1'
        _rb.audit('DEVICE_EDIT','device',d.id,f'{d.name} {d.ae_title}'); _rb.db.session.commit(); _rb.flash('Device updated.','success')
        return _rb.redirect(_rb.url_for('admin_devices'))
    return admin_device_edit


def install_0560(_rb):
    @_rb.app.route('/admin/procedures',methods=['GET','POST'])
    @_rb.require_perm('procedures.view')
    def admin_procedures():
        if _rb.request.method=='POST':
            if not _rb.has_perm('*') and not _rb.has_perm('contracts.manage'): _rb.abort(403)
            p=_rb.Procedure(code=_rb.request.form['code'].strip().upper(),name=_rb.request.form['name'].strip(),name_ar=_rb.request.form.get('name_ar','').strip(),category=_rb.request.form.get('category','').strip(),modality=_rb.request.form['modality'],
                        body_part=_rb.request.form.get('body_part',''),base_price=float(_rb.request.form.get('base_price') or 0),
                        duration_min=int(_rb.request.form.get('duration_min') or 20),contrast=_rb.request.form.get('contrast')=='1',active=True)
            _rb.db.session.add(p); _rb.audit('PROCEDURE_CREATE','procedure','',p.code); _rb.db.session.commit(); _rb.flash('Procedure added.','success')
        return _rb.render_template('admin_procedures.html',procedures=_rb.Procedure.query.order_by(_rb.Procedure.modality,_rb.Procedure.name).all())
    return admin_procedures


def install_0561(_rb):
    @_rb.app.route('/admin/contracts',methods=['GET','POST'])
    @_rb.require_perm('contracts.manage')
    def admin_contracts():
        if _rb.request.method=='POST':
            c=_rb.Contract(code=_rb.request.form['code'].strip().upper(),name=_rb.request.form['name'].strip(),
                       patient_share_percent=float(_rb.request.form.get('patient_share_percent') or 0),
                       discount_percent=float(_rb.request.form.get('discount_percent') or 0),
                       approval_required=_rb.request.form.get('approval_required')=='1',active=True)
            _rb.db.session.add(c); _rb.audit('CONTRACT_CREATE','contract','',c.code); _rb.db.session.commit(); _rb.flash('Contract added.','success')
        return _rb.render_template('admin_contracts.html',contracts=_rb.Contract.query.order_by(_rb.Contract.name).all())
    return admin_contracts


def install_0562(_rb):
    @_rb.app.route('/admin/contracts/<int:contract_id>/prices',methods=['GET','POST'])
    @_rb.require_perm('contracts.manage')
    def admin_contract_prices(contract_id):
        c=_rb.Contract.query.get_or_404(contract_id)
        if _rb.request.method=='POST':
            pid=int(_rb.request.form['procedure_id']); cp=_rb.ContractPrice.query.filter_by(contract_id=c.id,procedure_id=pid).first()
            if not cp: cp=_rb.ContractPrice(contract_id=c.id,procedure_id=pid); _rb.db.session.add(cp)
            cp.price=float(_rb.request.form['price']); sp=_rb.request.form.get('patient_share_percent','').strip()
            cp.patient_share_percent=float(sp) if sp else None
            _rb.audit('CONTRACT_PRICE_SET','contract',c.id,f'procedure={pid} price={cp.price}'); _rb.db.session.commit(); _rb.flash('Contract price saved.','success')
        return _rb.render_template('admin_contract_prices.html',contract=c,prices=_rb.ContractPrice.query.filter_by(contract_id=c.id).all(),procedures=_rb.Procedure.query.filter_by(active=True).order_by(_rb.Procedure.modality,_rb.Procedure.name).all())
    return admin_contract_prices


def install_0581(_rb):
    @_rb.app.post(
        '/admin/cancellation-center/order/<int:order_id>/delete-images'
    )
    @_rb.require_perm('data.cancel.case')
    def granular_delete_order_images_only(order_id):
        order=_rb.Order.query.get_or_404(order_id)

        reason=(_rb.request.form.get('reason') or '').strip()
        typed_accession=(
            _rb.request.form.get('confirm_accession')
            or ''
        ).strip()

        return _rb.granular_delete_images_only_execute(
            order,
            typed_accession,
            reason,
        )
    return granular_delete_order_images_only


def install_0597(_rb):
    @_rb.app.get(
        '/admin/cancellation-center/order/<int:order_id>/preview'
    )
    @_rb.require_perm('data.cancel.case')
    def granular_delete_order_preview(order_id):
        order = _rb.Order.query.get_or_404(order_id)

        snapshot = _rb.granular_delete_order_preview_snapshot(
            order
        )

        if (
            _rb.request.args.get('format', '').strip().lower()
            == 'json'
        ):
            return _rb.jsonify(snapshot)

        return _rb.render_template(
            'admin_cancellation_preview.html',
            preview=snapshot,
        )
    return granular_delete_order_preview


def install_0599(_rb):
    @_rb.app.post(
        '/admin/cancellation-center/order/<int:order_id>/delete-ris-case-data'
    )
    @_rb.require_perm('data.cancel.case')
    def granular_delete_order_ris_case_data_only(order_id):
        order=_rb.Order.query.get_or_404(order_id)
        user=_rb.current_user()
        if not _rb._delete_reports_only_is_super_admin(user):
            _rb.abort(403)
        reason=(_rb.request.form.get('reason') or '').strip()
        typed_accession=(_rb.request.form.get('confirm_accession') or '').strip()
        return _rb.granular_delete_ris_case_only_execute(order,typed_accession,reason)
    return granular_delete_order_ris_case_data_only


def install_0604(_rb):
    @_rb.app.post(
        '/admin/cancellation-center/order/<int:order_id>/delete-full-case'
    )
    @_rb.require_perm('data.cancel.case')
    def granular_delete_order_full_case(order_id):
        order=_rb.Order.query.get_or_404(order_id)
        user=_rb.current_user()
        if not _rb._delete_reports_only_is_super_admin(user):
            _rb.abort(403)
        reason=(_rb.request.form.get('reason') or '').strip()
        typed_accession=(_rb.request.form.get('confirm_accession') or '').strip()
        return _rb.granular_delete_full_case_orchestration_execute(
            order,typed_accession,reason
        )
    return granular_delete_order_full_case


def install_0605(_rb):
    @_rb.app.get(
        '/admin/cancellation-center/patient/<int:patient_id>/preview'
    )
    @_rb.require_perm('data.cancel.case')
    def granular_delete_patient_preview(patient_id):
        patient = _rb.Patient.query.get_or_404(patient_id)

        snapshot = (
            _rb.granular_delete_patient_preview_snapshot(
                patient
            )
        )

        if (
            _rb.request.args.get('format', '').strip().lower()
            == 'json'
        ):
            return _rb.jsonify(snapshot)

        return _rb.render_template(
            'admin_cancellation_preview.html',
            preview=snapshot,
        )
    return granular_delete_patient_preview


def install_0622(_rb):
    @_rb.app.route('/correction-center/orders/<int:order_id>/demographics',methods=['GET','POST'])
    @_rb.require_perm('correction.request')
    def patient_demographics_correction(order_id):
        from patient_correction_policy import FIELDS,current_value,snapshot,impact,normalize,submit
        order=_rb.Order.query.filter_by(id=order_id).with_for_update().first_or_404()
        if not _rb.correction_branch_allowed(order):_rb.abort(403)
        patient=_rb.Patient.query.filter_by(id=order.patient_id).with_for_update().first_or_404()
        field=(_rb.request.form.get('field_name') if _rb.request.method=='POST' else _rb.request.args.get('field_name')) or 'name'
        if field not in FIELDS:_rb.abort(400)
        if _rb.request.method=='POST':
            try:row=submit(order,field,_rb.request.form.get('proposed_value',''),_rb.request.form.get('reason',''),_rb.request.form.get('snapshot_hash',''))
            except ValueError as exc:
                _rb.db.session.rollback();_rb.flash(str(exc),'danger')
                return _rb.redirect(_rb.url_for('patient_demographics_correction',order_id=order_id,field_name=field))
            _rb.db.session.commit();_rb.flash('Structured correction request submitted. / تم إرسال طلب التصحيح.','success')
            return _rb.redirect(_rb.url_for('patient_demographics_correction_view',request_id=row.id))
        return _rb.render_template('patient_demographics_correction.html',order=order,fields=FIELDS,field=field,current=current_value(patient,field),snapshot_hash=snapshot(patient),impact=impact(patient,field))
    return patient_demographics_correction


def install_0623(_rb):
    @_rb.app.get('/correction-center/requests/<int:request_id>/demographics')
    @_rb.login_required
    def patient_demographics_correction_view(request_id):
        from patient_correction_policy import snapshot,impact,FIELDS
        row=_rb.CorrectionRequest.query.get_or_404(request_id)
        if not (_rb.correction_can_request() or _rb.correction_can_review()):_rb.abort(403)
        if not _rb.correction_branch_allowed(row.order):_rb.abort(403)
        if row.requested_by!=_rb.current_user().id and not _rb.correction_can_review():_rb.abort(403)
        detail=row.demographic_detail
        if not detail:_rb.abort(404)
        patient=_rb.Patient.query.get_or_404(detail.patient_id)
        return _rb.render_template('patient_demographics_correction_view.html',row=row,detail=detail,fields=FIELDS,impact=_rb.json.loads(detail.impact_json),current_impact=impact(patient,detail.field_name),stale=snapshot(patient)!=detail.snapshot_hash)
    return patient_demographics_correction_view


def install_0638(_rb):
    @_rb.app.post('/admin/cancellation-center/appointments/<int:appointment_id>/cancel')
    @_rb.require_perm('data.cancel.case')
    def admin_cancel_appointment(appointment_id):
        row=_rb.Appointment.query.get_or_404(appointment_id);reason=_rb.cancellation_reason();previous=row.status
        row.status='CANCELLED';row.cancelled_at=_rb.datetime.utcnow()
        _rb.audit('APPOINTMENT_CANCELLED_ADMIN','appointment',row.id,f'reason={reason};previous_status={previous};order_id={row.order_id or ""}')
        _rb.db.session.commit();_rb.flash('Appointment cancelled and audited.','success')
        return _rb.redirect(_rb.url_for('admin_cancellation_center',q=_rb.request.form.get('return_q','')))
    return admin_cancel_appointment


def install_0639(_rb):
    @_rb.app.post('/admin/cancellation-center/orders/<int:order_id>/cancel')
    @_rb.require_perm('data.cancel.case')
    def admin_cancel_order(order_id):
        order=_rb.Order.query.get_or_404(order_id);reason=_rb.cancellation_reason()
        report=getattr(order,'report',None);report_status=str(getattr(report,'status','') or '').upper()
        if str(order.status or '').upper()=='FINAL' or report_status in ('FINAL','FINALIZED','VERIFIED'):
            _rb.audit('ORDER_CANCEL_BLOCKED_FINAL','order',order.id,f'reason={reason};report_status={report_status}')
            _rb.db.session.commit();_rb.abort(409,'Final or verified reports require a dedicated audited amendment workflow.')
        previous=f'order={order.status};exam={getattr(order,"exam_status","")}'
        order.status='CANCELLED'
        if hasattr(order,'exam_status'):order.exam_status='CANCELLED'
        if order.appointment:order.appointment.status='CANCELLED';order.appointment.cancelled_at=_rb.datetime.utcnow()
        for assignment in _rb.CaseAssignment.query.filter_by(order_id=order.id,active=True).all():
            assignment.active=False;assignment.unassigned_at=_rb.datetime.utcnow()
        for offer in _rb.AssignmentOffer.query.filter_by(order_id=order.id,status='PENDING').all():
            offer.status='CANCELLED';offer.responded_at=_rb.datetime.utcnow()
        _rb.audit('ORDER_CANCELLED_ADMIN','order',order.id,f'reason={reason};previous={previous};accession={order.accession}')
        _rb.db.session.commit();_rb.flash('Order cancelled and downstream assignment stopped.','success')
        return _rb.redirect(_rb.url_for('admin_cancellation_center',q=_rb.request.form.get('return_q','')))
    return admin_cancel_order


def install_0640(_rb):
    @_rb.app.post('/admin/cancellation-center/orders/<int:order_id>/remove-referral')
    @_rb.require_perm('data.cancel.case')
    def admin_remove_order_referral(order_id):
        order=_rb.Order.query.get_or_404(order_id);reason=_rb.cancellation_reason();previous=order.referring_doctor_id
        if not previous:_rb.abort(409,'This order has no referral to remove.')
        order.referring_doctor_id=None
        _rb.audit('ORDER_REFERRAL_REMOVED','order',order.id,f'reason={reason};previous_referring_doctor_id={previous};accession={order.accession}')
        _rb.db.session.commit();_rb.flash('Referral removed and audited.','success')
        return _rb.redirect(_rb.url_for('admin_cancellation_center',q=_rb.request.form.get('return_q','')))
    return admin_remove_order_referral


def install_0644(_rb):
    @_rb.app.route('/admin/devices/<int:device_id>',methods=['GET','POST'])
    @_rb.require_perm('devices.manage')
    def admin_device_page(device_id):
        d=_rb.Device.query.get_or_404(device_id)
        if _rb.request.method=='POST':
            d.branch_id=int(_rb.request.form['branch_id']); d.name=_rb.request.form['name'].strip(); d.modality=_rb.request.form['modality']
            d.ae_title=_rb.request.form['ae_title'].strip().upper(); d.ip=_rb.request.form.get('ip','').strip()
            d.port=int(_rb.request.form.get('port') or 104); d.room=_rb.request.form.get('room','').strip()
            d.priority=int(_rb.request.form.get('priority') or 100); d.active=_rb.request.form.get('active')=='1'
            _rb.audit('DEVICE_EDIT','device',d.id,f'{d.name} {d.ae_title}'); _rb.db.session.commit(); _rb.flash('Device updated.','success')
            return _rb.redirect(_rb.url_for('admin_devices'))
        return _rb.render_template('admin_device_edit.html',device=d,branches=_rb.Branch.query.order_by(_rb.Branch.name).all())
    return admin_device_page


def install_0647(_rb):
    @_rb.app.post('/my/registration-style')
    @_rb.login_required
    def my_registration_style():
        style=(_rb.request.form.get('style_key') or 'MODERN').upper()
        if style not in ('MODERN','CLASSIC','COMPACT'): _rb.abort(400)
        row=_rb.UserRegistrationPreference.query.filter_by(user_id=_rb.current_user().id).first()
        if not row: row=_rb.UserRegistrationPreference(user_id=_rb.current_user().id); _rb.db.session.add(row)
        row.style_key=style; _rb.db.session.commit()
        return _rb.redirect(_rb.request.referrer or _rb.url_for('new_order'))
    return my_registration_style


def install_0649(_rb):
    @_rb.app.route('/patients/<int:patient_id>/alerts',methods=['GET','POST'])
    @_rb.login_required
    def patient_alerts(patient_id):
        patient=_rb.Patient.query.get_or_404(patient_id)
        if _rb.request.method=='POST':
            row=_rb.PatientAlert(patient_id=patient.id,alert_type=(_rb.request.form.get('alert_type') or 'OTHER').upper(),
              title=(_rb.request.form.get('title') or '').strip(),notes=(_rb.request.form.get('notes') or '').strip(),
              amount=_rb.request.form.get('amount',type=float),branch_id=_rb.request.form.get('branch_id',type=int),
              created_by=_rb.current_user().id,status='OPEN')
            _rb.db.session.add(row); _rb.db.session.commit(); return _rb.redirect(_rb.url_for('patient_alerts',patient_id=patient.id))
        return _rb.render_template('patient_alerts.html',patient=patient,
          alerts=_rb.PatientAlert.query.filter_by(patient_id=patient.id).order_by(_rb.PatientAlert.created_at.desc()).all(),
          branches=_rb.Branch.query.order_by(_rb.Branch.name).all())
    return patient_alerts


def install_0650(_rb):
    @_rb.app.post('/patient-alerts/<int:alert_id>/resolve')
    @_rb.login_required
    def patient_alert_resolve(alert_id):
        row=_rb.PatientAlert.query.get_or_404(alert_id); row.status='RESOLVED'; row.resolved_by=_rb.current_user().id; row.resolved_at=_rb.datetime.utcnow()
        _rb.db.session.commit(); return _rb.redirect(_rb.request.referrer or _rb.url_for('patient_alerts',patient_id=row.patient_id))
    return patient_alert_resolve


def install_0665(_rb):
    @_rb.app.route('/patients/<int:patient_id>/external-priors',methods=['GET','POST'])
    @_rb.login_required
    def patient_external_priors(patient_id):
        patient=_rb.Patient.query.get_or_404(patient_id)
        if _rb.request.method=='POST':
            f=_rb.request.files.get('file')
            if not f or not f.filename: _rb.abort(400)
            ext=_rb.os.path.splitext(f.filename)[1].lower()
            if ext not in ('.dcm','.dicom','.zip','.jpg','.jpeg','.png','.pdf'): _rb.abort(400)
            folder=_rb.os.path.join(_rb.ATTACHMENT_DIR,'external-priors',str(patient.id));_rb.os.makedirs(folder,exist_ok=True)
            safe=_rb.re.sub(r'[^A-Za-z0-9._-]','_',f.filename);path=_rb.os.path.join(folder,f'{int(_rb.datetime.utcnow().timestamp())}_{safe}');f.save(path)
            source='DICOM' if ext in ('.dcm','.dicom') else ('ZIP' if ext=='.zip' else ('PDF' if ext=='.pdf' else 'IMAGE'))
            meta=_rb.safe_dicom_metadata(path) if source=='DICOM' else {}
            score,status=_rb.score_prior_match(patient,meta)
            study_date=None
            if meta.get('study_date'):
                try: study_date=_rb.datetime.strptime(meta['study_date'][:8],'%Y%m%d').date()
                except Exception: pass
            row=_rb.ExternalPriorStudy(patient_id=patient.id,linked_order_id=_rb.request.form.get('linked_order_id',type=int),
              source_type=source,study_date=study_date,modality=(meta.get('modality') or _rb.request.form.get('modality') or '').upper(),
              study_description=(meta.get('study_description') or _rb.request.form.get('study_description') or '').strip(),
              external_patient_name=meta.get('patient_name',''),external_patient_id=meta.get('patient_id',''),
              external_dob=meta.get('dob',''),file_path=path,original_name=f.filename,
              dicom_metadata_json=_rb.json.dumps(meta,ensure_ascii=False),match_status=status,match_score=score,uploaded_by=_rb.current_user().id)
            _rb.db.session.add(row);_rb.db.session.commit()
            return _rb.redirect(_rb.url_for('patient_external_priors',patient_id=patient.id))
        return _rb.render_template('patient_external_priors.html',patient=patient,
          rows=_rb.ExternalPriorStudy.query.filter_by(patient_id=patient.id).order_by(_rb.ExternalPriorStudy.created_at.desc()).all(),
          orders=_rb.Order.query.filter_by(patient_id=patient.id).order_by(_rb.Order.id.desc()).limit(50).all())
    return patient_external_priors


def install_0737(_rb):
    @_rb.app.get('/orders/<int:order_id>/actions')
    @_rb.login_required
    def order_actions(order_id):
        order=_rb.Order.query.get_or_404(order_id)
        return _rb.render_template('order_actions.html',order=order,ctx=_rb.order_action_context(order),visual=_rb.order_visual_state(order),lifecycle=_rb.CASE_LIFECYCLE)
    return order_actions


def install_0738(_rb):
    @_rb.app.get('/orders/<int:order_id>/label-print')
    @_rb.login_required
    def order_label_print(order_id):
        order=_rb.Order.query.get_or_404(order_id)
        tpl=_rb.default_label_template(order)
        layout={}
        if tpl:
            try: layout=_rb.json.loads(tpl.layout_json or '{}')
            except Exception: layout={}
        return _rb.render_template('label_print.html',order=order,template=tpl,layout=layout)
    return order_label_print


def install_0743(_rb):
    @_rb.app.route('/intake/smart',methods=['GET','POST'])
    @_rb.require_perm('patients.create')
    def smart_intake_start():
        if _rb.request.method=='POST':
            import secrets
            row=_rb.SmartIntakeSession(session_key=secrets.token_urlsafe(24),created_by=_rb.current_user().id)
            _rb.db.session.add(row);_rb.db.session.commit()
            return _rb.redirect(_rb.url_for('smart_intake_workspace',intake_id=row.id))
        recent=_rb.SmartIntakeSession.query.filter_by(created_by=_rb.current_user().id).order_by(_rb.SmartIntakeSession.updated_at.desc()).limit(20).all()
        return _rb.render_template('smart_intake_start.html',recent=recent)
    return smart_intake_start


def install_0744(_rb):
    @_rb.app.get('/intake/smart/<int:intake_id>')
    @_rb.require_perm('patients.create')
    def smart_intake_workspace(intake_id):
        row=_rb.SmartIntakeSession.query.get_or_404(intake_id)
        docs=_rb.SmartIntakeDocument.query.filter_by(intake_id=row.id).order_by(_rb.SmartIntakeDocument.document_type,_rb.SmartIntakeDocument.created_at).all()
        if row.status!='COMPLETED':
            extracted,identity_validation,match_context=_rb.rebuild_intake_summary(row)
        else:
            try: extracted=_rb.json.loads(row.extracted_json or '{}')
            except Exception: extracted={}
            identity_validation=_rb.validate_intake_identity(_rb._intake_final_identity(row,extracted))
            match_context=_rb._intake_match_context(identity_validation['normalized'])
        field_reviews={x.field_key:x for x in _rb.SmartIntakeFieldReview.query.filter_by(intake_id=row.id).all()}
        document_classifications={}
        document_payloads={}
        for doc in docs:
            try:
                payload=_rb.json.loads(doc.extracted_json or '{}')
                if not isinstance(payload,dict): payload={}
            except Exception:
                payload={}
            document_payloads[doc.id]=payload
            classification=payload.get('_document_classification') or {}
            document_classifications[doc.id]=classification if isinstance(classification,dict) else {}
        return _rb.render_template('smart_intake_workspace.html',intake=row,docs=docs,
          document_types=_rb.SMART_DOCUMENT_TYPES,extracted=extracted,
          document_classifications=document_classifications,
          document_payloads=document_payloads,
          matched_patient=_rb.Patient.query.get(row.matched_patient_id) if row.matched_patient_id else None,
          suggested_procedure=_rb.Procedure.query.get(row.suggested_procedure_id) if row.suggested_procedure_id else None,
          suggested_contract=_rb.Contract.query.get(row.suggested_contract_id) if row.suggested_contract_id else None,
          ocr_provider=_rb.enabled_ocr_provider(),field_reviews=field_reviews,
          identity_validation=identity_validation,match_context=match_context,
          core_fields=_rb.OCR_INTAKE_CORE_FIELDS,
          procedures=_rb.Procedure.query.filter_by(active=True).order_by(_rb.Procedure.modality,_rb.Procedure.name).all(),
          contracts=_rb.Contract.query.filter_by(active=True).order_by(_rb.Contract.name).all(),
          visit_review=extracted.get('visit_review') or {},
          pending_docs=[doc for doc in docs if doc.status not in ('APPROVED','REJECTED')],
          approved_identity_docs=[doc for doc in docs if doc.document_type=='IDENTITY' and doc.status=='APPROVED'])
    return smart_intake_workspace


def install_0745(_rb):
    @_rb.app.get('/intake/smart/<int:intake_id>/document/<int:doc_id>/file')
    @_rb.require_perm('patients.create')
    def smart_intake_document_file(intake_id,doc_id):
        doc=_rb.SmartIntakeDocument.query.filter_by(id=doc_id,intake_id=intake_id).first_or_404()
        if not _rb.os.path.isfile(doc.file_path): _rb.abort(404)
        return _rb.send_file(doc.file_path,mimetype=doc.mime_type or 'application/octet-stream',
          download_name=doc.original_name or f'intake-document-{doc.id}',
          as_attachment=_rb.request.args.get('download')=='1')
    return smart_intake_document_file


def install_0746(_rb):
    @_rb.app.post('/intake/smart/<int:intake_id>/upload')
    @_rb.require_perm('patients.create')
    def smart_intake_upload(intake_id):
        intake=_rb.SmartIntakeSession.query.get_or_404(intake_id)
        if intake.status=='COMPLETED':
            _rb.abort(409)

        dtype=(_rb.request.form.get('document_type') or 'OTHER').upper()
        auto_ocr=_rb.request.form.get('auto_ocr')=='1'

        files=_rb.request.files.getlist('files')
        if not files:
            _rb.abort(400)

        allowed={x[0] for x in _rb.SMART_DOCUMENT_TYPES}
        if dtype not in allowed:
            _rb.abort(400)

        allowed_ext={'.pdf','.png','.jpg','.jpeg','.tif','.tiff','.webp','.bmp','.dcm'}
        folder=_rb.smart_intake_dir(intake.id)

        new_docs=[]
        uploaded_count=0
        duplicate_count=0

        for f in files:
            if not f or not f.filename:
                continue

            ext=_rb.os.path.splitext(f.filename)[1].lower()

            if ext not in allowed_ext:
                _rb.flash(f'Unsupported document type: {ext or "unknown"}.','danger')
                continue

            safe=_rb.re.sub(r'[^A-Za-z0-9._-]','_',f.filename)[:180]
            path=_rb.os.path.join(folder,f'{_rb.uuid.uuid4().hex}_{safe}')
            f.save(path)

            digest=_rb._intake_file_sha256(path)

            if _rb.SmartIntakeDocument.query.filter_by(
                    intake_id=intake.id,
                    content_sha256=digest).first():
                _rb.os.remove(path)
                duplicate_count+=1
                continue

            doc=_rb.SmartIntakeDocument(
                intake_id=intake.id,
                document_type=dtype,
                original_name=f.filename,
                file_path=path,
                mime_type=f.mimetype or '',
                status='UPLOADED',
                content_sha256=digest
            )

            _rb.db.session.add(doc)
            _rb.db.session.flush()

            new_docs.append(doc)
            uploaded_count+=1

            _rb.audit(
                'SMART_INTAKE_DOCUMENT_UPLOAD',
                'smart_intake_session',
                intake.id,
                f'document_id={doc.id} document_type={dtype} '
                f'auto_ocr={1 if auto_ocr else 0} sha256={digest[:16]}'
            )

        intake.status='UPLOADING'
        _rb.db.session.commit()

        if duplicate_count:
            _rb.flash(f'{duplicate_count} duplicate document(s) skipped.','warning')

        # Unified intake: OCR each newly uploaded document immediately.
        if auto_ocr and new_docs:
            cfg=_rb.enabled_ocr_provider()

            provider_ready=bool(
                cfg and
                cfg.validation_status in ('READY','READY_WITH_WARNINGS') and
                cfg.validation_config_hash==_rb.ocr_configuration_hash(cfg)
            )

            if not provider_ready:
                _rb.flash(
                    'Documents uploaded, but automatic OCR was not started because '
                    'the OCR provider is not enabled and validated.',
                    'warning'
                )
                return _rb._intake_redirect(intake.id,'documents')

            success_count=0
            failed_count=0

            for doc in new_docs:
                result,error=_rb.call_ocr_provider(doc)

                if result:
                    classification=_rb._apply_smart_intake_ocr_result(doc,result)

                    _rb.audit(
                        'SMART_INTAKE_OCR_EXTRACTED',
                        'smart_intake_document',
                        doc.id,
                        f'intake_id={intake.id} provider={doc.ocr_provider_key} '
                        f'confidence={doc.confidence:.3f} '
                        f'declared_type={doc.document_type} '
                        f'suggested_type={classification.get("suggested_type","OTHER")} '
                        f'classification_status={classification.get("status","UNCLASSIFIED")} '
                        f'auto_ocr=1'
                    )

                    success_count+=1

                else:
                    doc.status='OCR_FAILED'
                    doc.ocr_error=(error or 'OCR failed')[:500]

                    _rb.audit(
                        'SMART_INTAKE_OCR_FAILED',
                        'smart_intake_document',
                        doc.id,
                        f'intake_id={intake.id} '
                        f'error_code={(error or "").split(":",1)[0][:80]} '
                        f'auto_ocr=1'
                    )

                    failed_count+=1

                _rb.db.session.flush()

            _rb.db.session.commit()
            _rb.rebuild_intake_summary(intake)

            if success_count:
                _rb.flash(
                    f'{success_count} document(s) uploaded and read automatically. '
                    'Review the detected types before approval.',
                    'success'
                )

            if failed_count:
                _rb.flash(
                    f'OCR failed for {failed_count} document(s). '
                    'They remain available for manual review or retry.',
                    'warning'
                )

        elif uploaded_count:
            _rb.flash(f'{uploaded_count} document(s) uploaded.','success')

        return _rb._intake_redirect(intake.id,'documents')
    return smart_intake_upload


def install_0748(_rb):
    @_rb.app.post('/intake/smart/<int:intake_id>/ocr/<int:doc_id>')
    @_rb.require_perm('patients.create')
    def smart_intake_run_ocr(intake_id,doc_id):
        intake=_rb.SmartIntakeSession.query.get_or_404(intake_id)
        if intake.status=='COMPLETED': _rb.abort(409)
        doc=_rb.SmartIntakeDocument.query.filter_by(id=doc_id,intake_id=intake.id).first_or_404()
        result,error=_rb.call_ocr_provider(doc)
        if not result:
            doc.status='OCR_FAILED';doc.ocr_error=(error or 'OCR failed')[:500]
            _rb.audit('SMART_INTAKE_OCR_FAILED','smart_intake_document',doc.id,
              f'intake_id={intake.id} error_code={(error or "").split(":",1)[0][:80]}')
            _rb.db.session.commit()
            _rb.flash('OCR failed: '+error,'danger')
            return _rb._intake_redirect(intake.id,f'document-{doc.id}')
        classification=_rb._apply_smart_intake_ocr_result(doc,result)
        _rb.audit('SMART_INTAKE_OCR_EXTRACTED','smart_intake_document',doc.id,
          f'intake_id={intake.id} provider={doc.ocr_provider_key} '
          f'confidence={doc.confidence:.3f} declared_type={doc.document_type} '
          f'suggested_type={classification.get("suggested_type","OTHER")} '
          f'classification_status={classification.get("status","UNCLASSIFIED")}')
        _rb.db.session.commit();_rb.rebuild_intake_summary(intake)
        return _rb._intake_redirect(intake.id,f'document-{doc.id}')
    return smart_intake_run_ocr


def install_0749(_rb):
    @_rb.app.post('/intake/smart/<int:intake_id>/ocr-all')
    @_rb.require_perm('patients.create')
    def smart_intake_run_all_ocr(intake_id):
        intake=_rb.SmartIntakeSession.query.get_or_404(intake_id)
        if intake.status=='COMPLETED': _rb.abort(409)
        docs=_rb.SmartIntakeDocument.query.filter_by(intake_id=intake.id).all()
        for doc in docs:
            if doc.status in ('APPROVED','REJECTED'): continue
            result,error=_rb.call_ocr_provider(doc)
            if result:
                classification=_rb._apply_smart_intake_ocr_result(doc,result)
                _rb.audit('SMART_INTAKE_OCR_EXTRACTED','smart_intake_document',doc.id,
                  f'intake_id={intake.id} provider={doc.ocr_provider_key} '
                  f'confidence={doc.confidence:.3f} declared_type={doc.document_type} '
                  f'suggested_type={classification.get("suggested_type","OTHER")} '
                  f'classification_status={classification.get("status","UNCLASSIFIED")}')
            else:
                doc.status='OCR_FAILED';doc.ocr_error=(error or 'OCR failed')[:500]
                _rb.audit('SMART_INTAKE_OCR_FAILED','smart_intake_document',doc.id,
                  f'intake_id={intake.id} error_code={(error or "").split(":",1)[0][:80]}')
            _rb.db.session.flush()
        _rb.db.session.commit();_rb.rebuild_intake_summary(intake)
        return _rb._intake_redirect(intake.id,'documents')
    return smart_intake_run_all_ocr


def install_0750(_rb):
    @_rb.app.post('/intake/smart/<int:intake_id>/document/<int:doc_id>/review')
    @_rb.require_perm('patients.create')
    def smart_intake_document_review(intake_id,doc_id):
        intake=_rb.SmartIntakeSession.query.get_or_404(intake_id)
        if intake.status=='COMPLETED': _rb.abort(409)
        doc=_rb.SmartIntakeDocument.query.filter_by(id=doc_id,intake_id=intake.id).first_or_404()
        action=(_rb.request.form.get('action') or '').upper()
        if action not in ('APPROVED','REJECTED','REVIEW_REQUIRED'): _rb.abort(400)
        notes=(_rb.request.form.get('review_notes') or '').strip()[:1000]

        submitted_type=(_rb.request.form.get('document_type') or doc.document_type or 'OTHER').upper()
        allowed_types={x[0] for x in _rb.SMART_DOCUMENT_TYPES}
        if submitted_type not in allowed_types:
            _rb.abort(400)

        old_type=doc.document_type
        if submitted_type != old_type:
            doc.document_type=submitted_type
            _rb.audit(
              'SMART_INTAKE_DOCUMENT_TYPE_CHANGED',
              'smart_intake_document',
              doc.id,
              f'intake_id={intake.id} old_type={old_type} new_type={submitted_type}'
            )

        if action=='APPROVED' and doc.status=='UPLOADED':
            _rb.flash('Run OCR or explicitly reject the unread document before continuing.','danger')
            return _rb._intake_redirect(intake.id,f'document-{doc.id}')
        if action=='APPROVED' and doc.status=='OCR_FAILED' and len(notes)<3:
            _rb.flash('A review note is required to approve a document after OCR failure.','danger')
            return _rb._intake_redirect(intake.id,f'document-{doc.id}')
        if action=='REJECTED' and len(notes)<3:
            _rb.flash('Enter a rejection reason.','danger')
            return _rb._intake_redirect(intake.id,f'document-{doc.id}')
        doc.status=action;doc.reviewed_by=_rb.current_user().id;doc.reviewed_at=_rb.datetime.utcnow()
        doc.review_notes=notes
        _rb.audit('SMART_INTAKE_DOCUMENT_'+action,'smart_intake_document',doc.id,
          f'intake_id={intake.id} document_type={doc.document_type}')
        _rb.db.session.commit();_rb.rebuild_intake_summary(intake)
        return _rb._intake_redirect(intake.id,f'document-{doc.id}')
    return smart_intake_document_review


def install_0755(_rb):
    @_rb.app.post('/intake/smart/<int:intake_id>/review-save')
    @_rb.require_perm('patients.create')
    def smart_intake_review_save(intake_id):
        intake=_rb.SmartIntakeSession.query.filter_by(id=intake_id).with_for_update().first_or_404()
        if intake.status=='COMPLETED' and intake.patient_id:
            return _rb.redirect(_rb.url_for('new_order',patient=intake.patient_id,intake=intake.id))
        action=(_rb.request.form.get('registration_action') or 'SAVE_DRAFT').upper()
        if action not in ('SAVE_DRAFT','LINK_EXISTING','CREATE_NEW'): _rb.abort(400)
        submitted={key:_rb.request.form.get(key,'') for key in _rb.OCR_INTAKE_CORE_FIELDS}
        submitted['review_notes']=_rb.request.form.get('review_notes','')
        validation=_rb.validate_intake_identity(submitted)
        _rb._save_intake_review_fields(intake,submitted,validation)
        visit_review=_rb._save_intake_visit_review(intake,_rb.request.form)

        if action=='SAVE_DRAFT':
            draft_match=_rb._intake_match_context(validation['normalized'])
            if not validation['ok']: intake.status='IDENTITY_REVIEW'
            elif draft_match['resolution'] in ('CONFLICT','AMBIGUOUS'): intake.status='MATCH_REVIEW'
            else: intake.status='READY_TO_COMMIT'
            _rb.audit('SMART_INTAKE_REVIEW_DRAFT','smart_intake_session',intake.id,
              f'validation_ok={validation["ok"]} invalid_count={len(validation["invalid_fields"])} procedure_id={visit_review.get("procedure_id") or ""} contract_id={visit_review.get("contract_id") or ""}')
            _rb.db.session.commit();_rb.flash('Review draft saved. No patient or order was created.','success')
            return _rb._intake_redirect(intake.id,'identity')

        docs=_rb.SmartIntakeDocument.query.filter_by(intake_id=intake.id).all()
        if not validation['ok']:
            return _rb._block_intake_registration(intake,'IDENTITY_REVIEW',
              'Correct invalid identity fields and provide a reliable identifier before registration.','IDENTITY_INVALID')
        if _rb.request.form.get('identity_confirmed')!='1':
            return _rb._block_intake_registration(intake,'IDENTITY_REVIEW',
              'Confirm that the final patient identity was checked against the available source or the patient.','IDENTITY_NOT_CONFIRMED')

        identity=validation['normalized'];match=_rb._intake_match_context(identity)
        top=match.get('top')
        intake.match_resolution=match.get('resolution') or 'NO_MATCH'
        intake.matched_patient_score=float(top.get('score') if top else 0)
        patient=None
        if action=='LINK_EXISTING':
            selected_id=_rb.request.form.get('selected_patient_id',type=int)
            selected=next((item for item in match['candidates'] if item['patient_id']==selected_id),None)
            if not selected or selected['score']<85:
                return _rb._block_intake_registration(intake,'MATCH_REVIEW',
                  'Select a strong reviewed patient match before linking.','MATCH_NOT_SELECTED')
            if selected.get('hard_conflict') or match.get('resolution')=='AMBIGUOUS':
                reason=(_rb.request.form.get('override_reason') or '').strip()
                if not (_rb.has_perm('workflow.override') and len(reason)>=8):
                    return _rb._block_intake_registration(intake,'MATCH_REVIEW',
                      'Conflict or ambiguous duplicate requires supervisor override and a written reason.','MATCH_CONFLICT_OR_AMBIGUOUS')
                intake.review_notes=((intake.review_notes or '')+'\nSupervisor match override: '+reason).strip()[:2000]
            patient=_rb.Patient.query.get_or_404(selected_id)
            intake.matched_patient_id=patient.id
        else:
            exact=next((item for item in match['candidates'] if item['score']==100),None)
            if exact:
                return _rb._block_intake_registration(intake,'MATCH_REVIEW',
                  'A patient with this National ID already exists. Link the existing record.','EXACT_DUPLICATE')
            strong=next((item for item in match['candidates'] if item['score']>=85),None)
            if strong:
                reason=(_rb.request.form.get('override_reason') or '').strip()
                if not (_rb.has_perm('workflow.override') and _rb.request.form.get('confirm_create_new')=='1' and len(reason)>=8):
                    return _rb._block_intake_registration(intake,'MATCH_REVIEW',
                      'A strong possible duplicate exists. Supervisor override and reason are required to create a new patient.','STRONG_DUPLICATE')
                intake.review_notes=((intake.review_notes or '')+'\nSupervisor duplicate override: '+reason).strip()[:2000]

            lock_value=identity.get('national_id') or (identity.get('phone','')+identity.get('dob',''))
            if _rb.db.engine.dialect.name=='postgresql':
                _rb.db.session.execute(_rb.text('SELECT pg_advisory_xact_lock(hashtext(:key))'),{'key':'OCR_REG:'+lock_value})
            post_lock_match=_rb._intake_match_context(identity)
            if any(item['score']==100 for item in post_lock_match['candidates']):
                return _rb._block_intake_registration(intake,'MATCH_REVIEW',
                  'Another registration created this patient. Link the existing record.','CONCURRENT_DUPLICATE')
            patient=_rb.Patient(
              patient_id=_rb.next_patient_id(),name=identity['name'],phone=identity['phone'],
              national_id=identity['national_id'],sex=identity['sex'],dob=identity['dob'],
              address=identity['address'])
            _rb.db.session.add(patient);_rb.db.session.flush()
            intake.matched_patient_id=None

        approved_docs=[doc for doc in docs if doc.status=='APPROVED']
        hashes=[doc.content_sha256 for doc in approved_docs if doc.content_sha256]
        commit_key=_rb.intake_registration_fingerprint(intake.id,identity,hashes)
        _rb._attach_intake_documents(intake,patient)
        intake.patient_id=patient.id;intake.commit_key=commit_key;intake.commit_action=action
        intake.committed_by=_rb.current_user().id;intake.committed_at=_rb.datetime.utcnow()
        intake.completed_at=_rb.datetime.utcnow();intake.status='COMPLETED'
        _rb.audit('SMART_INTAKE_'+action,'smart_intake_session',intake.id,
          f'patient_id={patient.id} match_resolution={match["resolution"]} approved_documents={len(approved_docs)} excluded_documents={len(docs)-len(approved_docs)} procedure_id={visit_review.get("procedure_id") or ""} contract_id={visit_review.get("contract_id") or ""}')
        _rb.db.session.commit()
        _rb.flash('Patient registration completed. Review the order details before creating the order.','success')
        return _rb.redirect(_rb.url_for('new_order',patient=patient.id,intake=intake.id))
    return smart_intake_review_save


def install_0764(_rb):
    @_rb.app.get('/orders/<int:order_id>/print-center')
    @_rb.login_required
    def order_print_center(order_id):
        order=_rb.Order.query.get_or_404(order_id)
        ctx=_rb.order_action_context(order)
        workstation=(_rb.request.args.get('workstation') or '').strip()
        profiles={k:_rb.resolve_printer_profile(order,k,workstation) for k in ('RECEIPT','LABEL','REPORT','A4')}
        return _rb.render_template('order_print_center.html',order=order,ctx=ctx,profiles=profiles)
    return order_print_center


def install_0765(_rb):
    @_rb.app.route('/my/registration-defaults',methods=['GET','POST'])
    @_rb.login_required
    def my_registration_defaults():
        row=_rb.RegistrationDefault.query.filter_by(user_id=_rb.current_user().id,active=True).order_by(_rb.RegistrationDefault.id.desc()).first()
        if _rb.request.method=='POST':
            if not row:
                row=_rb.RegistrationDefault(user_id=_rb.current_user().id,is_global=False,active=True)
                _rb.db.session.add(row)
            row.default_branch_id=_rb.request.form.get('default_branch_id',type=int)
            row.default_department=(_rb.request.form.get('default_department') or '').strip()
            row.default_procedure_id=_rb.request.form.get('default_procedure_id',type=int)
            row.default_contract_id=_rb.request.form.get('default_contract_id',type=int)
            row.default_referrer_id=_rb.request.form.get('default_referrer_id',type=int)
            row.default_priority=(_rb.request.form.get('default_priority') or 'ROUTINE').upper()
            row.default_payment_method=(_rb.request.form.get('default_payment_method') or '').upper()
            row.default_patient_mode=(_rb.request.form.get('default_patient_mode') or 'existing').lower()
            row.updated_by=_rb.current_user().id
            _rb.db.session.commit()
            _rb.flash('Registration defaults saved.','success')
            return _rb.redirect(_rb.url_for('my_registration_defaults'))
        return _rb.render_template('registration_defaults.html',row=row,title='My Registration Defaults',
            branches=_rb.Branch.query.filter_by(active=True).order_by(_rb.Branch.name).all(),
            procedures=_rb.Procedure.query.filter_by(active=True).order_by(_rb.Procedure.modality,_rb.Procedure.name).all(),
            contracts=_rb.Contract.query.filter_by(active=True).order_by(_rb.Contract.name).all(),
            referrers=_rb.ReferringDoctor.query.filter_by(active=True).order_by(_rb.ReferringDoctor.name).all())
    return my_registration_defaults


def install_0766(_rb):
    @_rb.app.route('/admin/registration-defaults',methods=['GET','POST'])
    @_rb.require_perm('users.view')
    def admin_registration_defaults():
        user_id=_rb.request.args.get('user_id',type=int) or _rb.request.form.get('user_id',type=int)
        scope=(_rb.request.form.get('scope') or _rb.request.args.get('scope') or 'USER').upper()
        is_global=(scope=='GLOBAL')
        row=None
        if is_global:
            row=_rb.RegistrationDefault.query.filter_by(is_global=True,active=True).order_by(_rb.RegistrationDefault.id.desc()).first()
        elif user_id:
            row=_rb.RegistrationDefault.query.filter_by(user_id=user_id,active=True).order_by(_rb.RegistrationDefault.id.desc()).first()

        if _rb.request.method=='POST':
            if not is_global and not user_id:
                _rb.flash('Select a user or choose Global Defaults.','danger')
                return _rb.redirect(_rb.url_for('admin_registration_defaults'))
            if not row:
                row=_rb.RegistrationDefault(user_id=None if is_global else user_id,is_global=is_global,active=True)
                _rb.db.session.add(row)
            row.user_id=None if is_global else user_id
            row.is_global=is_global
            row.default_branch_id=_rb.request.form.get('default_branch_id',type=int)
            row.default_department=(_rb.request.form.get('default_department') or '').strip()
            row.default_procedure_id=_rb.request.form.get('default_procedure_id',type=int)
            row.default_contract_id=_rb.request.form.get('default_contract_id',type=int)
            row.default_referrer_id=_rb.request.form.get('default_referrer_id',type=int)
            row.default_priority=(_rb.request.form.get('default_priority') or 'ROUTINE').upper()
            row.default_payment_method=(_rb.request.form.get('default_payment_method') or '').upper()
            row.default_patient_mode=(_rb.request.form.get('default_patient_mode') or 'existing').lower()
            row.updated_by=_rb.current_user().id
            _rb.db.session.commit()
            _rb.audit('REGISTRATION_DEFAULTS_UPDATE','user',user_id or 0,'GLOBAL' if is_global else 'USER')
            _rb.flash('Registration defaults saved.','success')
            return _rb.redirect(_rb.url_for('admin_registration_defaults',scope='GLOBAL' if is_global else 'USER',user_id=user_id))

        return _rb.render_template('admin_registration_defaults.html',row=row,selected_user_id=user_id,scope=scope,
            users=_rb.User.query.filter_by(active=True).order_by(_rb.User.full_name).all(),
            branches=_rb.Branch.query.filter_by(active=True).order_by(_rb.Branch.name).all(),
            procedures=_rb.Procedure.query.filter_by(active=True).order_by(_rb.Procedure.modality,_rb.Procedure.name).all(),
            contracts=_rb.Contract.query.filter_by(active=True).order_by(_rb.Contract.name).all(),
            referrers=_rb.ReferringDoctor.query.filter_by(active=True).order_by(_rb.ReferringDoctor.name).all())
    return admin_registration_defaults


def install_0779(_rb):
    @_rb.app.route('/orders/<int:order_id>/performing-doctor',methods=['POST'])
    @_rb.require_perm('orders.status')
    def set_performing_doctor(order_id):
        order=_rb.Order.query.get_or_404(order_id)
        doctor_id=_rb.request.form.get('doctor_user_id',type=int)
        if not doctor_id:
            _rb.flash('Select performing doctor.','danger')
            return _rb.redirect(_rb.request.referrer or _rb.url_for('order_detail',order_id=order.id))
        doctor=_rb.User.query.get_or_404(doctor_id)
        row=_rb.OrderPerformingDoctor.query.filter_by(order_id=order.id).first()
        if not row:
            row=_rb.OrderPerformingDoctor(order_id=order.id,doctor_user_id=doctor.id,assigned_by=_rb.current_user().id)
            _rb.db.session.add(row)
        else:
            row.doctor_user_id=doctor.id;row.assigned_by=_rb.current_user().id;row.assigned_at=_rb.datetime.utcnow()
        row.notes=(_rb.request.form.get('notes') or '').strip()
        _rb.db.session.commit()
        _rb.audit('PERFORMING_DOCTOR_SET','order',order.id,f'doctor={doctor.id}')
        return _rb.redirect(_rb.request.referrer or _rb.url_for('order_detail',order_id=order.id))
    return set_performing_doctor


def install_0805(_rb):
    @_rb.app.post('/admin/data-management/export-patient')
    @_rb.require_perm('data.export')
    def admin_export_patient():
        q=(_rb.request.form.get('patient_key') or '').strip()
        patient=None
        if q.isdigit():
            patient=_rb.Patient.query.filter((_rb.Patient.id==int(q)) | (_rb.Patient.patient_id==q)).first()
        if not patient:
            patient=_rb.Patient.query.filter(_rb.Patient.patient_id==q).first()
        if not patient:
            _rb.flash('Patient not found.','danger');return _rb.redirect(_rb.url_for('admin_data_management'))

        manifest=_rb.patient_export_manifest(patient)
        mem=_rb.io.BytesIO()
        with _rb.zipfile.ZipFile(mem,'w',_rb.zipfile.ZIP_DEFLATED) as z:
            z.writestr('manifest.json',_rb.json.dumps(manifest,ensure_ascii=False,indent=2))
            z.writestr('patient.json',_rb.json.dumps(manifest['patient'],ensure_ascii=False,indent=2))
            out=_rb.io.StringIO();w=_rb.csv.DictWriter(out,fieldnames=['id','accession','procedure','status','created_at'])
            w.writeheader();w.writerows(manifest['orders']);z.writestr('orders.csv',out.getvalue())

            # Copy only files whose database records are actually associated with this patient's orders.
            order_ids=[o['id'] for o in manifest['orders']]
            if order_ids and 'Attachment' in _rb.namespace():
                try:
                    aq=_rb.Attachment.query.filter(_rb.Attachment.order_id.in_(order_ids)).all()
                    for a in aq:
                        path=getattr(a,'path',None) or getattr(a,'file_path',None)
                        if path and _rb.os.path.isfile(path):
                            z.write(path,'attachments/'+_rb.safe_export_name(_rb.os.path.basename(path)))
                except Exception:
                    pass
            if order_ids and 'Report' in _rb.namespace():
                try:
                    rq=_rb.Report.query.filter(_rb.Report.order_id.in_(order_ids)).all()
                    for r in rq:
                        for attr in ('pdf_path','docx_path','file_path'):
                            path=getattr(r,attr,None)
                            if path and _rb.os.path.isfile(path):
                                z.write(path,'reports/'+_rb.safe_export_name(_rb.os.path.basename(path)))
                except Exception:
                    pass

        mem.seek(0)
        _rb.audit('PATIENT_DATA_EXPORT','patient',patient.id,f'patient_id={getattr(patient,"patient_id","")}')
        return _rb.send_file(mem,as_attachment=True,download_name=f'patient-{_rb.safe_export_name(getattr(patient,"patient_id",patient.id))}.zip',
                         mimetype='application/zip')
    return admin_export_patient


def install_0807(_rb):
    @_rb.app.post('/admin/data-management/anonymize-patient')
    @_rb.require_perm('data.anonymize')
    def admin_anonymize_patient():
        patient_id=_rb.request.form.get('patient_id',type=int)
        patient=_rb.Patient.query.get_or_404(patient_id)
        expected=_rb.destructive_confirmation_token('ANONYMIZE PATIENT',1)
        if (_rb.request.form.get('confirmation') or '').strip()!=expected:
            _rb.flash(f'Confirmation mismatch. Type exactly: {expected}','danger')
            return _rb.redirect(_rb.url_for('admin_data_management'))
        original=getattr(patient,'patient_id',str(patient.id))
        if hasattr(patient,'name'):patient.name=f'ANON-{patient.id:08d}'
        if hasattr(patient,'phone'):patient.phone=None
        for attr in ('mobile','national_id','email','address'):
            if hasattr(patient,attr):setattr(patient,attr,None)
        _rb.db.session.commit()
        _rb.audit('PATIENT_ANONYMIZED','patient',patient.id,f'original_patient_id={original}')
        _rb.flash('Patient demographics anonymized. Clinical/order records were preserved.','success')
        return _rb.redirect(_rb.url_for('admin_data_management'))
    return admin_anonymize_patient


def install_0808(_rb):
    @_rb.app.post('/admin/data-management/delete-patient')
    @_rb.require_perm('data.delete.patient')
    def admin_delete_patient():
        patient_id=_rb.request.form.get('patient_id',type=int)
        patient=_rb.Patient.query.get_or_404(patient_id)
        orders=_rb.Order.query.filter_by(patient_id=patient.id).all()
        # Safety gate: refuse deletion while dependent clinical records exist.
        if orders:
            _rb.flash(f'Deletion blocked: patient has {len(orders)} order(s). Export/archive or remove dependent records through an approved retention workflow first.','danger')
            _rb.audit('PATIENT_DELETE_BLOCKED','patient',patient.id,f'orders={len(orders)}')
            return _rb.redirect(_rb.url_for('admin_data_management'))
        expected=_rb.destructive_confirmation_token('DELETE PATIENT',1)
        if (_rb.request.form.get('confirmation') or '').strip()!=expected:
            _rb.flash(f'Confirmation mismatch. Type exactly: {expected}','danger')
            return _rb.redirect(_rb.url_for('admin_data_management'))
        _rb.db.session.delete(patient);_rb.db.session.commit()
        _rb.audit('PATIENT_DELETED','patient',patient_id,'no dependent orders')
        _rb.flash('Patient record deleted.','success')
        return _rb.redirect(_rb.url_for('admin_data_management'))
    return admin_delete_patient


def install_0810(_rb):
    @_rb.app.post('/admin/data-management/backup-all-patients')
    @_rb.require_perm('backup.all_patients')
    def admin_backup_all_patients():
        password=_rb.request.form.get('password') or ''
        if not _rb.verify_current_user_password(password):
            _rb.audit('BACKUP_ALL_PATIENTS_REAUTH_FAILED','backup','',f'user={getattr(_rb.current_user(),"id","")}')
            _rb.db.session.commit()
            _rb.flash('Incorrect password. No backup was created.','danger')
            return _rb.redirect(_rb.url_for('admin_data_management'))
        try:
            path,digest=_rb.create_all_patient_backup()
            _rb.audit('BACKUP_ALL_PATIENTS','backup','',f'file={_rb.os.path.basename(path)} sha256={digest}')
            _rb.db.session.commit()
            _rb.flash(f'All-patient backup created: {_rb.os.path.basename(path)}','success')
        except Exception as e:
            _rb.db.session.rollback()
            _rb.flash(f'Backup failed: {e}','danger')
        return _rb.redirect(_rb.url_for('admin_data_management'))
    return admin_backup_all_patients


def install_0811(_rb):
    @_rb.app.post('/admin/data-management/delete-all-patients')
    @_rb.require_perm('data.delete.all_patients')
    def admin_delete_all_patients():
        password=_rb.request.form.get('password') or ''
        if not _rb.verify_current_user_password(password):
            _rb.audit('DELETE_ALL_PATIENTS_REAUTH_FAILED','patient','ALL',f'user={getattr(_rb.current_user(),"id","")}')
            _rb.db.session.commit()
            _rb.flash('Incorrect password. No data was changed.','danger')
            return _rb.redirect(_rb.url_for('admin_data_management'))

        before={'patients':_rb.Patient.query.count(),'orders':_rb.Order.query.count()}
        try:
            result=_rb.delete_all_patient_operational_data()
            _rb.audit('DELETE_ALL_PATIENT_DATA','patient','ALL',
                  f"patients={before['patients']} orders={before['orders']} files_quarantined={result['files_moved']} quarantine={result['quarantine']}")
            _rb.db.session.commit()
            _rb.flash(f"Patient operational data cleared. {before['patients']} patient(s), {before['orders']} order(s). "
                  f"{result['files_moved']} file(s) moved to quarantine.",'success')
        except Exception as e:
            _rb.db.session.rollback()
            _rb.flash(f'Delete-all operation failed and database changes were rolled back: {e}','danger')
        return _rb.redirect(_rb.url_for('admin_data_management'))
    return admin_delete_all_patients
