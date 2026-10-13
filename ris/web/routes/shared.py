"""Runtime-bound web.routes.shared; dependencies are supplied at composition.

Legacy behavior is preserved; new policies belong in the independent domain layer.
"""

def install_0000(_rb):
    @_rb.app.before_request
    def _same_origin_unsafe_request_guard():
        """Reject explicit cross-origin browser writes for authenticated sessions.

    This is a compatibility-safe CSRF hardening layer for the legacy form estate.
    Requests without an Origin header are left to existing auth/token controls.
    """
        if _rb.request.method not in ('POST', 'PUT', 'PATCH', 'DELETE'):
            return None
        if not _rb.session.get('uid'):
            return None
        origin = (_rb.request.headers.get('Origin') or '').rstrip('/')
        if not origin:
            return None

        # Some same-origin browser form navigations can serialize an opaque
        # origin as the literal value "null".  Do not trust "null" globally:
        # accept it only when Fetch Metadata confirms a same-origin request.
        if origin == 'null':
            fetch_site = (_rb.request.headers.get('Sec-Fetch-Site') or '').strip().lower()
            if fetch_site == 'same-origin':
                return None
            _rb.abort(403)

        allowed = {_rb.request.host_url.rstrip('/'), _rb.RIS_PUBLIC_URL.rstrip('/') if 'RIS_PUBLIC_URL' in _rb.namespace() else ''}
        configured = _rb.os.getenv('RADBRIDGE_TRUSTED_ORIGINS', '')
        allowed.update(x.strip().rstrip('/') for x in configured.split(',') if x.strip())
        if origin not in allowed:
            _rb.abort(403)
        return None
    return _same_origin_unsafe_request_guard


def install_0139(_rb):
    @_rb.app.context_processor
    def template_globals():
        lang=_rb.current_ui_language()
        u=_rb.current_user()
        profile=_rb.get_user_profile(u) if u else None
        return {
            'me':u,
            'has_perm':_rb.has_perm,
            'pacs_online':_rb.orthanc_ok(),
            'ris_public_url':_rb.RIS_PUBLIC_URL,
            'procedure_name':_rb.procedure_display_name,
            'company':_rb.get_company_profile(),
            't':_rb.ui_text,
            'status_label':_rb.status_text,
            'ui_lang':lang,
            'ui_phrase':lambda text, language=None: __import__('ui_localization').translate(text, language or lang),
            'ui_role':lambda role: __import__('ui_localization').role_label(role, lang),
            'ui_client_catalog':__import__('ui_localization').client_catalog(lang),
            'ui_dir':'rtl' if lang=='ar' else 'ltr',
            'worklist_name_map':_rb.ARABIC_NAME_MAP,
            'user_profile':profile,
            'ribbon_actions':_rb.ribbon_actions_for_user(u,'GLOBAL') if u else [],
            'unread_chat_count':_rb.unread_chat_count(u) if u else 0,
            'role_quick_actions':_rb.role_quick_actions(u) if u else [],
            'quick_action_role':_rb.quick_action_role(u) if u else 'MANAGEMENT',
            'safe_url_for_endpoint':_rb.safe_url_for_endpoint
        }
    return template_globals


def install_0141(_rb):
    @_rb.app.route('/lang/<code>')
    @_rb.login_required
    def set_language(code):
        if code in ('en','ar'):
            p=_rb.UserProfile.query.filter_by(user_id=_rb.current_user().id).first()
            if not p:
                p=_rb.UserProfile(user_id=_rb.current_user().id)
                _rb.db.session.add(p)
            p.ui_language=code
            _rb.session['ui_lang']=code
            _rb.session['lang']=code
            _rb.db.session.commit()
        return _rb.redirect(_rb.request.referrer or _rb.url_for('dashboard'))
    return set_language


def install_0142(_rb):
    @_rb.app.errorhandler(401)
    def friendly_401(error):
        return _rb.render_template(
            "error.html",
            error_code="401",
            error_id=_rb._error_id(),
            title="Authentication Required",
            message="Your session or authorization is no longer valid. Please return to RadBridge RIS and open the page again."
        ), 401
    return friendly_401


def install_0143(_rb):
    @_rb.app.errorhandler(403)
    def friendly_403(error):
        return _rb.render_template(
            "error.html",
            error_code="403",
            error_id=_rb._error_id(),
            title="Access Not Permitted",
            message="Your account does not have permission to perform this action. Please return to RadBridge RIS or contact your system administrator."
        ), 403
    return friendly_403


def install_0144(_rb):
    @_rb.app.errorhandler(404)
    def friendly_404(error):
        return _rb.render_template('error.html',
            error_code='404',
            error_id=_rb._error_id(),
            title='Page not found',
            message='The requested page or item could not be found. It may have been moved, removed, or the link may no longer be valid. Use the Error ID below when reporting the problem.'), 404
    return friendly_404


def install_0145(_rb):
    @_rb.app.errorhandler(500)
    def friendly_500(error):
        eid=_rb._error_id()

        try:
            _rb.db.session.rollback()
        except Exception:
            pass

        _rb.app.logger.exception('Internal error %s', eid)

        try:
            return _rb.render_template(
                'error.html',
                error_code='500',
                error_id=eid,
                title='Internal Server Error',
                message='An internal error occurred. Use the Error ID below when reporting the problem.'
            ), 500
        except Exception:
            return (
                f'Internal Server Error - Error ID: {eid}',
                500,
                {'Content-Type':'text/plain; charset=utf-8'}
            )
    return friendly_500


def install_0149(_rb):
    @_rb.app.route('/')
    @_rb.login_required
    def dashboard():
        today = _rb.date.today()
        all_orders = _rb.Order.query.all()

        def scheduled_today(order):
            return bool(
                order.scheduled
                and order.scheduled.date() == today
            )

        stats = {
            'patients': _rb.Patient.query.count(),
            'orders': len(all_orders),
            'today': sum(
                1 for order in all_orders
                if scheduled_today(order)
            ),
            'waiting': sum(
                1 for order in all_orders
                if (order.exam_status or 'ORDERED').upper()
                in ('BOOKED', 'ORDERED')
                and order.status not in ('FINAL', 'CANCELLED')
            ),
            'in_progress': sum(
                1 for order in all_orders
                if (order.exam_status or '').upper() == 'IN_PROGRESS'
            ),
            'completed': sum(
                1 for order in all_orders
                if (order.exam_status or '').upper() == 'EXAM_COMPLETED'
            ),
            'images_received': sum(
                1 for order in all_orders
                if int(order.pacs_image_count or 0) > 0
            ),
            'reporting': sum(
                1 for order in all_orders
                if order.status == 'REPORTING'
            ),
            'final': sum(
                1 for order in all_orders
                if order.status == 'FINAL'
            ),
            'unassigned': sum(
                1 for order in all_orders
                if not order.assigned_doctor_id
                and int(order.pacs_image_count or 0) > 0
                and order.status not in ('FINAL', 'CANCELLED')
            ),
            'mwl_errors': sum(
                1 for order in all_orders
                if order.status in ('MWL_ERROR', 'ROUTING_ERROR')
            ),
            'revenue': round(
                sum(float(order.paid_amount or 0) for order in all_orders),
                2,
            ),
        }

        recent = (
            _rb.Order.query
            .order_by(_rb.Order.id.desc())
            .limit(12)
            .all()
        )

        return _rb.render_template(
            'dashboard.html',
            stats=stats,
            recent=recent,
        )
    return dashboard


def install_0152(_rb):
    @_rb.app.route('/orders')
    @_rb.require_perm('orders.view')
    def orders():
        q=_rb.request.args.get('q','').strip(); status=_rb.request.args.get('status','').strip()
        query=_rb.Order.query.join(_rb.Patient)
        if q: query=query.filter(_rb.or_(_rb.Order.accession.ilike(f'%{q}%'),_rb.Order.procedure.ilike(f'%{q}%'),_rb.Patient.name.ilike(f'%{q}%'),_rb.Patient.patient_id.ilike(f'%{q}%')))
        if status: query=query.filter(_rb.Order.status==status)
        return _rb.render_template('orders.html',orders=query.order_by(_rb.Order.id.desc()).limit(400).all(),q=q,status=status)
    return orders


def install_0153(_rb):
    @_rb.app.route('/orders/new',methods=['GET','POST'])
    @_rb.require_perm('orders.create')
    def new_order():
        # v5.46.2: one visible registration workflow.
        if _rb.request.method == 'GET':
            kw={'open_registration':'1'}
            patient_arg=_rb.request.args.get('patient',type=int)
            intake_arg=_rb.request.args.get('intake',type=int)
            if patient_arg: kw['patient']=patient_arg
            if intake_arg: kw['intake']=intake_arg
            return _rb.redirect(_rb.url_for('schedule_calendar',**kw))

        plist=_rb.Patient.query.order_by(_rb.Patient.name).all()
        branches=_rb.Branch.query.filter_by(active=True).order_by(_rb.Branch.name).all()
        procedures=_rb.Procedure.query.filter_by(active=True).order_by(_rb.Procedure.modality,_rb.Procedure.name).all()
        contracts=_rb.Contract.query.filter_by(active=True).order_by(_rb.Contract.name).all()
        referrers=_rb.ReferringDoctor.query.filter_by(active=True).order_by(_rb.ReferringDoctor.name).all()
        selected=_rb.request.args.get('patient',type=int)
        intake_id=_rb.request.args.get('intake',type=int)

        if _rb.request.method=='POST':
            patient_mode=(_rb.request.form.get('patient_mode') or 'existing').strip()

            if patient_mode=='new':
                name=(_rb.request.form.get('new_name') or '').strip()
                phone=(_rb.request.form.get('new_phone') or '').strip()
                national_id=(_rb.request.form.get('new_national_id') or '').strip()
                nationality=(_rb.request.form.get('new_nationality') or '').strip()
                rules=_rb.registration_rule_map()
                for key,value in [
                    ('patient.name',name),
                    ('patient.phone',phone),
                    ('patient.national_id',national_id),
                    ('patient.nationality',nationality),
                    ('patient.email',(_rb.request.form.get('new_email') or '').strip()),
                    ('patient.address',(_rb.request.form.get('new_address') or '').strip())
                ]:
                    ok,msg=_rb.validate_registration_value(rules.get(key),value)
                    if not ok:
                        return _rb.registration_validation_error(msg,_rb.request.form)
                if not name:
                    return _rb.registration_validation_error('Patient name is required.',_rb.request.form)

                try:
                    dob_resolution=_rb.resolve_patient_dob(
                        _rb.request.form,
                        prefix='new_',
                    )
                except ValueError as exc:
                    return _rb.registration_validation_error(
                        str(exc),
                        _rb.request.form,
                    )
                dob=dob_resolution.dob
                from registration_policy import validate_patient_fields
                try:
                    validate_patient_fields(dict(name=name,phone=phone,national_id=national_id,
                        dob=dob,sex=_rb.request.form.get('new_sex',''),nationality=nationality,
                        email=_rb.request.form.get('new_email',''),address=_rb.request.form.get('new_address','')))
                except ValueError as exc:
                    return _rb.registration_validation_error(str(exc),_rb.request.form)
                duplicates=_rb.find_duplicate_patients(name,dob,phone,national_id)

                if duplicates and _rb.request.form.get('confirm_duplicate')!='1':
                    _rb.flash(f'Possible duplicate: {duplicates[0].patient_id} — {duplicates[0].name}. Search and use existing patient, or confirm duplicate creation.','warning')
                    return _rb.render_registration_form(
                        form_data=_rb.request.form,
                        selected_patient=None,
                        duplicate_patients=duplicates,
                        status=409
                    )

                p=_rb.Patient(
                    patient_id='TMP'+_rb.secrets.token_hex(8),
                    name=name,
                    dob=dob,
                    dob_estimated=dob_resolution.estimated,
                    sex=(_rb.request.form.get('new_sex') or '').strip(),
                    phone=phone,
                    national_id=national_id,
                    address=(_rb.request.form.get('new_address') or '').strip(),
                    email=(_rb.request.form.get('new_email') or '').strip(),
                    worklist_name=_rb.normalized_worklist_name(name,_rb.request.form.get('new_worklist_name',''))
                )
                _rb.db.session.add(p);_rb.db.session.flush()
                extra=_rb.PatientDemographicsExtra.query.filter_by(patient_id=p.id).first()
                if not extra:
                    extra=_rb.PatientDemographicsExtra(patient_id=p.id)
                    _rb.db.session.add(extra)
                extra.nationality=nationality
                extra.id_type=(_rb.request.form.get('new_id_type') or 'NATIONAL_ID').strip().upper()
                extra.other_id=(_rb.request.form.get('new_other_id') or '').strip()
                p.patient_id=_rb.next_patient_id()
                _rb.audit('PATIENT_CREATE_FROM_EASY_REGISTRATION','patient',p.id,p.patient_id)
            else:
                pid=_rb.request.form.get('patient',type=int)
                if not pid:
                    return _rb.registration_validation_error(
                        'Select an existing patient or choose New Patient.',
                        _rb.request.form
                    )
                p=_rb.Patient.query.get_or_404(pid)
                from registration_policy import validate_patient
                try: validate_patient(p)
                except ValueError as exc:
                    return _rb.registration_validation_error(str(exc),_rb.request.form)

            proc_id=_rb.request.form.get('procedure_id',type=int)
            branch_id=_rb.request.form.get('branch_id',type=int)
            proc=_rb.Procedure.query.get(proc_id) if proc_id else None
            branch=_rb.Branch.query.get(branch_id) if branch_id else None
            if not branch:
                return _rb.registration_validation_error('Select branch.',_rb.request.form,rollback=(patient_mode=='new'))
            if not proc:
                return _rb.registration_validation_error('Select examination.',_rb.request.form,rollback=(patient_mode=='new'))
            contract=_rb.Contract.query.get(_rb.request.form.get('contract_id',type=int)) if _rb.request.form.get('contract_id') else None

            try:
                scheduled=_rb.datetime.fromisoformat(_rb.request.form['scheduled'])
            except Exception:
                return _rb.registration_validation_error(
                    'Invalid visit date/time.',
                    _rb.request.form,
                    rollback=(patient_mode=='new')
                )

            if not _rb.procedure_available_in_branch(proc.id,branch.id):
                return _rb.registration_validation_error(
                    'This examination is not available in the selected branch.',
                    _rb.request.form,
                    rollback=(patient_mode=='new')
                )

            device=_rb.route_device(branch.id,proc.modality)
            if not device:
                return _rb.registration_validation_error(
                    'No available device is configured for this examination in the selected branch.',
                    _rb.request.form,
                    rollback=(patient_mode=='new')
                )

            restriction=_rb.booking_restriction_reason(branch,proc,device,scheduled,int(proc.duration_min or 20))
            if restriction:
                return _rb.registration_validation_error(
                    f'Cannot register this examination now: {restriction}',
                    _rb.request.form,
                    rollback=(patient_mode=='new')
                )

            # Insurance approval selection
            approval_required=bool(contract and contract.approval_required)
            approval_method=(_rb.request.form.get('approval_method') or '').strip().upper()
            approval_no=(_rb.request.form.get('approval_no') or '').strip()

            if approval_required:
                if approval_method not in ('AUTO','MANUAL','ALREADY_APPROVED'):
                    approval_method='AUTO'

                if approval_method=='ALREADY_APPROVED' and not approval_no:
                    return _rb.registration_validation_error(
                        'Approval number is required when approval is already available.',
                        _rb.request.form,
                        rollback=(patient_mode=='new')
                    )
            else:
                approval_method=''
                approval_no=''

            gross,effective,patient_share,company_share,share_pct=_rb.price_order(proc,contract)
            order=_rb.Order(
                accession=_rb.new_accession(),patient=p,modality=proc.modality,procedure=proc.name,
                procedure_id=proc.id,branch_id=branch.id,device_id=device.id,
                station_ae=device.ae_title,contract_id=(contract.id if contract else None),
                referring_doctor_id=(_rb.request.form.get('referring_doctor_id',type=int) or None),
                scheduled=scheduled,status='REGISTERED',gross_price=gross,contract_price=effective,
                patient_share=patient_share,company_share=company_share,
                approval_no=approval_no,
                created_by=_rb.current_user().id,
                priority=(_rb.request.form.get('priority') or 'ROUTINE').upper()
            )
            _rb.db.session.add(order);_rb.db.session.flush()

            # Create insurance approval tracking without changing Order.status.
            if approval_required:
                approval_status = (
                    'APPROVED'
                    if approval_method=='ALREADY_APPROVED'
                    else ('PENDING' if approval_method=='AUTO' else 'REQUIRED')
                )

                approval_row=_rb.InsuranceApprovalRequest(
                    order_id=order.id,
                    method=approval_method,
                    status=approval_status,
                    approval_no=approval_no,
                    payer_name=(contract.name if contract else ''),
                    requested_at=_rb.datetime.utcnow(),
                    decided_at=(_rb.datetime.utcnow() if approval_status=='APPROVED' else None),
                    created_by=_rb.current_user().id
                )

                _rb.db.session.add(approval_row)
                _rb.db.session.flush()

                _rb.db.session.add(_rb.InsuranceApprovalEvent(
                    approval_request_id=approval_row.id,
                    event_type='CREATED_FROM_REGISTRATION',
                    old_status='',
                    new_status=approval_status,
                    message=f'method={approval_method}',
                    user_id=_rb.current_user().id
                ))

                _rb.audit(
                    'INSURANCE_APPROVAL_CREATE',
                    'order',
                    order.id,
                    f'method={approval_method}; status={approval_status}'
                )

            _rb.ensure_journey(order,'REGISTERED')

            # Initial clinical note from registration screen.
            note_text=(_rb.request.form.get('clinical_note') or '').strip()
            if note_text:
                _rb.db.session.add(_rb.ClinicalNote(
                    order_id=order.id,author_user_id=_rb.current_user().id,
                    note_type='RECEPTION',visibility='CLINICAL_TEAM',text=note_text
                ))

            # Default consumables.
            for pc in _rb.ProcedureConsumable.query.filter_by(procedure_id=proc.id).all():
                _rb.db.session.add(_rb.OrderConsumable(
                    order_id=order.id,consumable_id=pc.consumable_id,
                    qty=pc.qty,source='DEFAULT',created_by=_rb.current_user().id
                ))

            # Optional first payment: requires explicit payment permission.
            pay_amount=float(_rb.request.form.get('payment_amount') or 0)
            pay_method=(_rb.request.form.get('payment_method') or '').strip().upper()
            if pay_amount>0:
                if not _rb.has_perm('payments.create'):
                    _rb.db.session.rollback()
                    _rb.abort(403)
                if not pay_method:
                    return _rb.registration_validation_error(
                        'Select payment method.',
                        _rb.request.form,
                        rollback=True
                    )
                payment=_rb.Payment(
                    order_id=order.id,amount=pay_amount,method=pay_method,
                    reference=(_rb.request.form.get('payment_reference') or '').strip(),
                    created_by=_rb.current_user().id
                )
                _rb.db.session.add(payment)
                order.paid_amount=pay_amount
                _rb.audit('PAYMENT_CREATE','order',order.id,f'{pay_amount} {pay_method}')

            # Optional MULTI attachments in the same registration screen.
            attachment_files=_rb.request.files.getlist('attachment_files')
            attachment_categories=_rb.request.form.getlist('attachment_categories')
            attachment_notes=_rb.request.form.getlist('attachment_notes')
            saved_attachment_paths=[]
            valid_files=[f for f in attachment_files if f and f.filename]
            if valid_files:
                if not _rb.has_perm('attachments.upload'):
                    _rb.db.session.rollback();_rb.abort(403)
                allowed_exts=('.pdf','.jpg','.jpeg','.png','.doc','.docx','.odt','.dcm','.dicom','.zip')
                folder=_rb.os.path.join(_rb.ATTACHMENT_DIR,str(p.id),str(order.id))
                _rb.os.makedirs(folder,exist_ok=True)
                for idx,f in enumerate(attachment_files):
                    if not f or not f.filename:
                        continue
                    ext=_rb.os.path.splitext(f.filename)[1].lower()
                    if ext not in allowed_exts:
                        return _rb.registration_validation_error(
                            f'Unsupported attachment type: {f.filename}',
                            _rb.request.form,
                            rollback=True
                        )
                    category=(attachment_categories[idx] if idx<len(attachment_categories) else 'OTHER').upper()
                    notes=(attachment_notes[idx] if idx<len(attachment_notes) else '').strip()
                    stored_name=_rb.generated_attachment_filename(order.id,category,f.filename)
                    path=_rb.os.path.join(folder,stored_name)
                    f.save(path)
                    saved_attachment_paths.append(path)
                    _rb.db.session.add(_rb.Attachment(
                        patient_id=p.id,order_id=order.id,
                        category=category,original_name=f.filename,stored_path=path,
                        mime_type=f.mimetype or '',notes=notes,uploaded_by=_rb.current_user().id
                    ))
                    _rb.audit('ATTACHMENT_UPLOAD','order',order.id,f'{category}:{f.filename}')

            # Persist the complete RIS transaction before any external side effect.
            # This prevents an MWL/assignment from existing for an order that failed to commit.
            _rb.audit('EASY_REGISTRATION_CREATE','order',order.id,
                  f'{order.accession} {proc.name} Branch={branch.name} Device={device.name}')
            # RB_WORK_ORDER_GATE_V3
            # Registration must not create an MWL event.
            # MWL is created only by explicit Work Order conversion.
            try:
                _rb.db.session.commit()
            except Exception:
                _rb.db.session.rollback()
                for saved_path in saved_attachment_paths:
                    try:
                        if _rb.os.path.isfile(saved_path):
                            _rb.os.remove(saved_path)
                    except Exception:
                        _rb.app.logger.exception('Failed to clean attachment after registration rollback: %s',saved_path)
                raise

            order_id=order.id

            # RB_WORK_ORDER_GATE_V3
            # Registration is complete, but the case intentionally remains
            # REGISTERED until financial clearance and explicit Work Order conversion.
            _rb.flash(
                f'Visit {order.accession} registered. Complete financial clearance, then convert to Work Order.',
                'success'
            )

            return _rb.redirect(_rb.url_for(
                'order_detail',
                order_id=order.id,
                created=1
            ))

        initial_form={}
        if intake_id and selected:
            source_intake=_rb.SmartIntakeSession.query.filter_by(
              id=intake_id,patient_id=selected,status='COMPLETED').first()
            if source_intake:
                try: source_summary=_rb.json.loads(source_intake.extracted_json or '{}')
                except Exception: source_summary={}
                visit=(source_summary.get('visit_review') or {}) if isinstance(source_summary,dict) else {}
                if source_intake.suggested_procedure_id:
                    initial_form['procedure_id']=str(source_intake.suggested_procedure_id)
                if source_intake.suggested_contract_id:
                    initial_form['contract_id']=str(source_intake.suggested_contract_id)
                if visit.get('approval_no'):
                    initial_form['approval_method']='ALREADY_APPROVED'
                    initial_form['approval_no']=str(visit['approval_no'])
                initial_form['smart_intake_id']=str(source_intake.id)

        return _rb.render_registration_form(
            form_data=initial_form,
            selected_patient=selected,
            duplicate_patients=[],
            status=200
        )
    return new_order


def install_0435(_rb):
    @_rb.app.route('/my/profile',methods=['GET','POST'])
    @_rb.login_required
    def my_profile():
        p=_rb.get_user_profile()

        if _rb.request.method=='POST':

            requested_theme = (
                _rb.request.form.get('theme')
                if 'theme' in _rb.request.form
                else None
            )

            if (
                requested_theme is not None
                and requested_theme not in (
                    'light-soft',
                    'light',
                    'dim',
                    'dark',
                    'midnight',
                    'auto',
                )
            ):
                _rb.abort(400)

            requested_accent = (
                _rb.request.form.get('accent')
                if 'accent' in _rb.request.form
                else None
            )

            if (
                requested_accent is not None
                and requested_accent not in (
                    'default',
                    'teal',
                    'violet',
                    'green',
                    'amber',
                    'rose',
                )
            ):
                _rb.abort(400)

            for k in [
                'department',
                'specialty',
                'default_workspace',
                'ui_language',
                'theme',
                'accent',
                'density',
                'font_scale',
                'sidebar_mode'
            ]:
                if k in _rb.request.form:
                    setattr(
                        p,
                        k,
                        (_rb.request.form.get(k) or '').strip()
                    )

            if 'preferred_image_viewer' in _rb.request.form:
                if not _rb.doctor_workspace_user(_rb.current_user()):
                    _rb.abort(403)
                _rb.save_image_viewer_preference(p,_rb.request.form['preferred_image_viewer'])
            prefs=_rb.set_user_reporting_preferences(
                p,
                _rb.request.form.get('preferred_editor'),
                _rb.request.form.get('preferred_layout'),
                _rb.request.form.get('preferred_display')
            )

            _rb.audit(
                'USER_REPORTING_PREFERENCES_SAVE',
                'user_profile',
                p.id or '',
                (
                    'editor=' +
                    prefs['preferred_editor'] +
                    '; layout=' +
                    prefs['preferred_layout'] +
                    '; display=' + prefs['preferred_display']
                )
            )

            _rb.db.session.commit()

            _rb.flash(
                'Profile and reporting preferences saved.',
                'success'
            )

            return _rb.redirect(
                _rb.url_for('my_profile')
            )

        return _rb.render_template(
            'my_profile.html',
            profile=p,
            preferred_image_viewer=_rb.image_viewer_preference(p),
            reporting_preferences=(
                _rb.user_reporting_preferences(p)
            )
        )
    return my_profile


def install_0440(_rb):
    @_rb.app.post('/ui/language')
    @_rb.login_required
    def ui_language_switch():
        lang=(_rb.request.form.get('language') or 'en').lower()
        if lang not in ('ar','en'):
            _rb.abort(400)
        p=_rb.UserProfile.query.filter_by(user_id=_rb.current_user().id).first()
        if not p:
            p=_rb.UserProfile(user_id=_rb.current_user().id)
            _rb.db.session.add(p)
        p.ui_language=lang
        _rb.session['ui_lang']=lang
        _rb.session['lang']=lang
        _rb.db.session.commit()
        return _rb.redirect(_rb.request.referrer or _rb.url_for('dashboard'))
    return ui_language_switch


def install_0442(_rb):
    @_rb.app.route('/my/ribbon',methods=['GET','POST'])
    @_rb.login_required
    def my_ribbon():
        u=_rb.current_user()
        if _rb.request.method=='POST':
            action_id=_rb.request.form.get('action_id',type=int)
            action=_rb.RibbonAction.query.get_or_404(action_id)
            if action.required_permission and not _rb.has_perm(action.required_permission):
                _rb.abort(403)
            row=_rb.UserRibbonAction.query.filter_by(
                user_id=u.id,ribbon_action_id=action.id
            ).first()
            if not row:
                row=_rb.UserRibbonAction(user_id=u.id,ribbon_action_id=action.id)
                _rb.db.session.add(row)
            row.visible=_rb.request.form.get('visible')=='1'
            row.order_no=_rb.request.form.get('order_no',type=int) or action.order_no or 100
            _rb.db.session.commit()
            _rb.flash('Ribbon updated.','success')
            return _rb.redirect(_rb.url_for('my_ribbon'))

        actions=_rb.RibbonAction.query.filter_by(active=True).order_by(
            _rb.RibbonAction.context,_rb.RibbonAction.order_no
        ).all()
        custom={x.ribbon_action_id:x for x in _rb.UserRibbonAction.query.filter_by(user_id=u.id).all()}
        return _rb.render_template('my_ribbon.html',actions=actions,custom=custom)
    return my_ribbon


def install_0444(_rb):
    @_rb.app.get('/operations/journey')
    @_rb.require_perm('orders.view')
    def operations_journey():
        q=(_rb.request.args.get('q') or '').strip();query=_rb.Order.query.join(_rb.Patient)
        if q:query=query.filter(_rb.or_(_rb.Order.accession.ilike(f'%{q}%'),_rb.Patient.patient_id.ilike(f'%{q}%'),_rb.Patient.name.ilike(f'%{q}%'),_rb.Patient.phone.ilike(f'%{q}%')))
        rows=[{'order':o,'journey':_rb.journey_snapshot(o)} for o in query.order_by(_rb.Order.id.desc()).limit(250).all()]
        return _rb.render_template('operations_journey.html',rows=rows,q=q,stages=_rb.JOURNEY_STAGES)
    return operations_journey


def install_0447(_rb):
    @_rb.app.get('/operations/dashboard')
    @_rb.require_perm('orders.view')
    def operations_dashboard():
        kind=_rb.role_dashboard_kind();today=_rb.datetime.now().date();start=_rb.datetime.combine(today,_rb.datetime.min.time());end=start+_rb.timedelta(days=1)
        orders=_rb.Order.query.filter(_rb.Order.scheduled>=start,_rb.Order.scheduled<end).all();waiting=[];delayed=[];unreported=[]
        for o in orders:
            snap=_rb.journey_snapshot(o);st=snap['stage']
            if st in ('WAITING','NURSING','TECHNICIAN'):waiting.append(o)
            if st in ('EXAM_DONE','PACS_RECEIVED','REPORTING'):unreported.append(o)
            if snap.get('entered_at') and (_rb.datetime.utcnow()-snap['entered_at']).total_seconds()>3600:delayed.append(o)
        cash=refund=0.0
        if kind in ('CASHIER','MANAGEMENT'):
            cash=sum(float(x.amount or 0) for x in _rb.Payment.query.filter(_rb.Payment.created_at>=start,_rb.Payment.created_at<end).all())
            refund=sum(float(x.amount or 0) for x in _rb.PaymentRefund.query.filter(_rb.PaymentRefund.created_at>=start,_rb.PaymentRefund.created_at<end).all())
        return _rb.render_template('operations_dashboard.html',kind=kind,today_orders=orders,waiting=waiting,delayed=delayed,unreported=unreported,cash_total=cash,refund_total=refund,unread_chat=_rb.unread_chat_count())
    return operations_dashboard


def install_0456(_rb):
    @_rb.app.get('/documents/<int:document_id>/review')
    @_rb.login_required
    def document_review(document_id):
        doc=_rb.PatientDocument.query.get_or_404(document_id)
        matches=_rb.DocumentMatch.query.filter_by(document_id=doc.id).all()
        return _rb.render_template('document_review.html',doc=doc,matches=matches,statuses=_rb.DOCUMENT_REVIEW_STATUSES)
    return document_review


def install_0457(_rb):
    @_rb.app.post('/documents/<int:document_id>/review')
    @_rb.login_required
    def document_review_save(document_id):
        doc=_rb.PatientDocument.query.get_or_404(document_id)
        status=(_rb.request.form.get('review_status') or 'REVIEWED').upper()
        if status not in _rb.DOCUMENT_REVIEW_STATUSES: _rb.abort(400)
        doc.review_status=status
        doc.review_notes=(_rb.request.form.get('review_notes') or '').strip()
        doc.reviewer_id=_rb.current_user().id
        doc.reviewed_at=_rb.datetime.utcnow()
        _rb.audit('PATIENT_DOCUMENT_REVIEW','patient',doc.patient_id,f'{doc.id}:{status}')
        _rb.db.session.commit()
        return _rb.redirect(_rb.url_for('document_review',document_id=doc.id))
    return document_review_save


def install_0470(_rb):
    @_rb.app.route('/attachments/upload',methods=['POST'])
    @_rb.require_perm('attachments.upload')
    def attachment_upload():
        files=_rb.request.files.getlist('files') or _rb.request.files.getlist('file')
        files=[f for f in files if f and f.filename]
        if not files:
            _rb.flash('Choose one or more files.','danger')
            return _rb.redirect(_rb.request.referrer or _rb.url_for('dashboard'))
        patient_id=_rb.request.form.get('patient_id',type=int)
        order_id=_rb.request.form.get('order_id',type=int)
        appointment_id=_rb.request.form.get('appointment_id',type=int)
        category=(_rb.request.form.get('category') or 'OTHER').upper()
        notes=(_rb.request.form.get('notes') or '').strip()
        folder=_rb.os.path.join(_rb.ATTACHMENT_DIR,str(patient_id or 'general'),str(order_id or appointment_id or 'misc'))
        _rb.os.makedirs(folder,exist_ok=True)
        allowed_exts=('.pdf','.jpg','.jpeg','.png','.doc','.docx','.odt','.dcm','.dicom','.zip')
        saved=0
        for idx,f in enumerate(files):
            ext=_rb.os.path.splitext(f.filename)[1].lower()
            if ext not in allowed_exts:
                _rb.flash(f'Unsupported attachment type: {f.filename}','danger')
                continue
            stored_name=_rb.generated_attachment_filename(order_id,category,f.filename)
            path=_rb.os.path.join(folder,stored_name)
            f.save(path)
            a=_rb.Attachment(patient_id=patient_id,order_id=order_id,appointment_id=appointment_id,
                category=category,original_name=f.filename,stored_path=path,
                mime_type=f.mimetype or '',notes=notes,uploaded_by=_rb.current_user().id)
            _rb.db.session.add(a); _rb.audit('ATTACHMENT_UPLOAD','attachment','',f'{category}:{f.filename}')
            saved+=1
        _rb.db.session.commit()
        _rb.flash(f'{saved} attachment(s) uploaded.','success')
        return _rb.redirect(_rb.request.referrer or _rb.url_for('dashboard'))
    return attachment_upload


def install_0471(_rb):
    @_rb.app.route('/attachments/<int:attachment_id>')
    @_rb.require_perm('attachments.view')
    def attachment_download(attachment_id):
        a=_rb.Attachment.query.get_or_404(attachment_id)
        return _rb.send_file(a.stored_path,as_attachment=True,download_name=a.original_name)
    return attachment_download


def install_0472(_rb):
    @_rb.app.route('/attachments/<int:attachment_id>/preview')
    @_rb.require_perm('attachments.view')
    def attachment_preview(attachment_id):
        a=_rb.Attachment.query.get_or_404(attachment_id)
        if not a.stored_path or not _rb.os.path.exists(a.stored_path):
            _rb.abort(404)
        return _rb.send_file(a.stored_path,as_attachment=False,download_name=a.original_name)
    return attachment_preview


def install_0473(_rb):
    @_rb.app.post('/attachments/<int:attachment_id>/delete')
    @_rb.require_perm('attachments.upload')
    def attachment_delete(attachment_id):
        a=_rb.Attachment.query.get_or_404(attachment_id)
        order_id=a.order_id
        patient_id=a.patient_id
        try:
            if a.stored_path and _rb.os.path.exists(a.stored_path):
                _rb.os.remove(a.stored_path)
        except Exception:
            _rb.app.logger.exception('Attachment file delete failed: %s',a.id)
        _rb.audit('ATTACHMENT_DELETE','attachment',a.id,f'{a.category}:{a.original_name}')
        _rb.db.session.delete(a);_rb.db.session.commit()
        _rb.flash('Attachment deleted.','success')
        return _rb.redirect(_rb.request.referrer or (_rb.url_for('orders') if order_id else _rb.url_for('patients')))
    return attachment_delete


def install_0477(_rb):
    @_rb.app.route('/scan',methods=['GET','POST'])
    @_rb.require_perm('orders.view')
    def barcode_scan():
        code=(_rb.request.values.get('code') or '').strip()
        if code:
            order=_rb.Order.query.filter_by(accession=code).first()
            if order:return _rb.redirect(_rb.url_for('order_detail',order_id=order.id))
            patient=_rb.Patient.query.filter_by(patient_id=code).first()
            if patient:return _rb.redirect(_rb.url_for('new_order',patient=patient.id))
            _rb.flash('Barcode / Patient ID not found.','warning')
        return _rb.render_template('barcode_scan.html',code=code)
    return barcode_scan


def install_0479(_rb):
    @_rb.app.route('/company/logo')
    def company_logo():
        profile=_rb.get_company_profile()
        if not profile.logo_path or not _rb.os.path.exists(profile.logo_path):_rb.abort(404)
        return _rb.send_file(profile.logo_path)
    return company_logo


def install_0497(_rb):
    @_rb.app.get('/api/command-center/control')
    @_rb.require_perm('audit.view')
    def api_command_center_control_get():

        return _rb.jsonify(
            _rb.command_center_control_state()
        )
    return api_command_center_control_get


def install_0498(_rb):
    @_rb.app.post('/api/command-center/control')
    @_rb.login_required
    def api_command_center_control_set():

        user = _rb.current_user()

        role_code = (
            user.role.code.upper()
            if (
                user
                and user.role
                and user.role.code
            )
            else ''
        )

        if role_code not in (
            'SUPER_ADMIN',
            'ADMIN'
        ):
            _rb.abort(403)

        data = _rb.request.get_json(
            silent=True
        ) or {}

        ok, result = \
            _rb._command_center_write_control_state(
                mode=data.get('mode'),
                normal_interval_seconds=data.get(
                    'normal_interval_seconds'
                ),
                live_interval_seconds=data.get(
                    'live_interval_seconds'
                ),
                updated_by=(
                    user.username
                    if user
                    else ''
                ),
            )

        if not ok:
            status = (
                503
                if result
                == 'CONTROL_STORAGE_NOT_CONFIGURED'
                else 400
            )

            return _rb.jsonify({
                'ok': False,
                'error': result,
            }), status

        _rb.audit(
            'COMMAND_CENTER_MODE_CHANGED',
            'system',
            'command-center',
            (
                'mode='
                + str(result.get('mode'))
                + '; normal_interval='
                + str(
                    result.get(
                        'normal_interval_seconds'
                    )
                )
                + '; live_interval='
                + str(
                    result.get(
                        'live_interval_seconds'
                    )
                )
            )
        )

        _rb.db.session.commit()

        return _rb.jsonify({
            'ok': True,
            'control': result,
        })
    return api_command_center_control_set


def install_0510(_rb):
    @_rb.app.get('/api/command-center/resources')
    @_rb.require_perm('audit.view')
    def api_command_center_resources():

        control = _rb.command_center_control_state()

        host_metrics = _rb._rb_host_metrics()
        container_metrics = _rb._rb_cgroup_metrics()

        auto_protection = _rb._rb_auto_protection_evaluate(
            host_metrics,
            container_metrics,
        )

        return _rb.jsonify({
            'schema':
                'radbridge.command_center.resources.v1',

            'read_only':
                True,

            'timestamp':
                _rb.datetime.utcnow().isoformat()
                + 'Z',

            'monitoring': {
                'mode':
                    control.get('mode'),

                'normal_interval_seconds':
                    control.get(
                        'normal_interval_seconds'
                    ),

                'live_interval_seconds':
                    control.get(
                        'live_interval_seconds'
                    ),

                'storage_configured':
                    control.get(
                        'storage_configured'
                    ),
            },

            'host':
                host_metrics,

            'container':
                container_metrics,

            'auto_protection':
                auto_protection,

            'services': {
                'ris': {
                    'status': 'HEALTHY',
                },

                'database':
                    _rb._rb_db_health(),

                'pacs':
                    _rb._rb_pacs_health(),
            },
        })
    return api_command_center_resources


def install_0511(_rb):
    @_rb.app.get('/api/command-center/events/stream')
    @_rb.require_perm('audit.view')
    def command_center_events_stream():

        from flask import Response, stream_with_context
        import inspect
        import time

        initial_control = _rb.command_center_control_state()

        if initial_control.get('mode') == 'OFF':
            return Response(
                status=204
            )

        @stream_with_context
        def generate():

            last_keys=set()

            while True:

                control = _rb.command_center_control_state()

                monitoring_mode = str(
                    control.get('mode')
                    or 'LIVE'
                ).upper()

                if monitoring_mode == 'OFF':

                    yield (
                        'event: monitoring_state\n'
                        'data: {"mode":"OFF"}\n\n'
                    )

                    return

                interval_seconds = (
                    int(
                        control.get(
                            'normal_interval_seconds'
                        )
                        or 15
                    )
                    if monitoring_mode == 'NORMAL'
                    else int(
                        control.get(
                            'live_interval_seconds'
                        )
                        or 2
                    )
                )

                view=_rb.app.view_functions.get(
                    'command_center_events'
                )

                if not view:
                    yield (
                        'event: error\n'
                        'data: {"error":"EVENT_API_NOT_FOUND"}\n\n'
                    )
                    time.sleep(5)
                    continue

                raw=inspect.unwrap(view)

                with _rb.app.test_request_context(
                    '/api/command-center/events?limit=100'
                ):
                    rv=raw()
                    response=(
                        rv[0]
                        if isinstance(rv,tuple)
                        else rv
                    )
                    data=response.get_json() or {}

                events=data.get('events') or []

                current_keys=set()

                for event in reversed(events):

                    key=str(
                        event.get('event_key') or ''
                    )

                    if not key:
                        continue

                    current_keys.add(key)

                    if key in last_keys:
                        continue

                    payload=_rb.json.dumps(
                        event,
                        ensure_ascii=False,
                        default=str
                    )

                    yield (
                        f'id: {key}\n'
                        f'event: workflow_event\n'
                        f'data: {payload}\n\n'
                    )

                last_keys=current_keys

                heartbeat_payload = _rb.json.dumps(
                    {
                        'status': 'alive',
                        'mode': monitoring_mode,
                        'interval_seconds':
                            interval_seconds,
                    },
                    separators=(',', ':')
                )

                yield (
                    'event: heartbeat\n'
                    f'data: {heartbeat_payload}\n\n'
                )

                time.sleep(
                    interval_seconds
                )

        response=Response(
            generate(),
            mimetype='text/event-stream'
        )

        response.headers['Cache-Control']='no-cache'
        response.headers['X-Accel-Buffering']='no'
        response.headers['Connection']='keep-alive'

        return response
    return command_center_events_stream


def install_0512(_rb):
    @_rb.app.route('/operations/live-command-center')
    @_rb.require_perm('audit.view')
    def live_command_center():
        return _rb.render_template('live_command_center.html')
    return live_command_center


def install_0513(_rb):
    @_rb.app.route('/api/command-center/events')
    @_rb.require_perm('audit.view')
    def command_center_events():

        limit=_rb.request.args.get(
            'limit',
            100,
            type=int
        )

        limit=max(1,min(limit or 100,200))

        order_filter=_rb.request.args.get(
            'order_id',
            type=int
        )

        events=[]
        order_cache={}

        def timestamp_value(value):
            if not value:
                return ''

            try:
                text=value.isoformat()
                if getattr(value,'tzinfo',None) is None:
                    text += 'Z'
                return text
            except Exception:
                return str(value)

        def order_context(order_id):
            try:
                oid=int(order_id)
            except Exception:
                return {
                    'order_id':None,
                    'accession':'',
                    'correlation_id':''
                }

            if oid not in order_cache:
                order_cache[oid]=_rb.db.session.get(
                    _rb.Order,
                    oid
                )

            order=order_cache[oid]

            return {
                'order_id':oid,
                'accession':(
                    order.accession
                    if order else ''
                ) or '',
                'correlation_id':f'order:{oid}'
            }

        def append_event(
            source,
            source_id,
            event_type,
            stage,
            status,
            timestamp,
            order_id=None,
            details='',
            payload=None
        ):
            ctx=order_context(order_id)

            events.append({
                'event_key':f'{source}:{source_id}',
                'source':source,
                'source_id':source_id,
                'event_type':str(
                    event_type or ''
                ).upper(),
                'stage':stage,
                'status':status,
                'timestamp':timestamp_value(
                    timestamp
                ),
                'order_id':ctx['order_id'],
                'accession':ctx['accession'],
                'correlation_id':ctx[
                    'correlation_id'
                ],
                'details':str(
                    details or ''
                )[:1000],
                'payload':payload or {}
            })

        def outbox_stage(event_type,payload):
            event_type=str(
                event_type or ''
            ).upper()

            if event_type=='ORDER_MWL_CREATE':
                return 'MWL','SUCCESS'

            if event_type=='ORDER_SMART_ASSIGNMENT':
                return 'ASSIGNMENT','REQUESTED'

            if event_type in (
                'EXAM_STATUS_CHANGED',
                'EXAM_STATUS_OVERRIDE'
            ):
                new_state=str(
                    payload.get('to') or ''
                ).upper()

                if new_state=='IN_PROGRESS':
                    return 'EXAM','RUNNING'

                if new_state=='EXAM_COMPLETED':
                    return 'EXAM','SUCCESS'

                if new_state=='REPORTING':
                    return 'REPORTING','RUNNING'

                return 'EXAM','INFO'

            return 'ORDER','INFO'

        def assignment_status(event_type):
            event_type=str(
                event_type or ''
            ).upper()

            mapping={
                'OFFERED':'RUNNING',
                'STRATEGY_SELECTED':'RUNNING',
                'ACCEPTED':'SUCCESS',
                'TIMEOUT':'FAILED',
                'NO_CANDIDATE':'FAILED',
                'READINESS_BLOCK':'BLOCKED',
                'REJECTED':'FAILED',
                'BUSY':'WAITING',
                'CANCELLED':'CANCELLED',
            }

            return mapping.get(
                event_type,
                'INFO'
            )

        def workflow_status(event_type):
            event_type=str(
                event_type or ''
            ).upper()

            if event_type.endswith('_FAILED'):
                return 'FAILED'

            if event_type=='RETURNED':
                return 'BLOCKED'

            if event_type in (
                'RESOLVED',
                'READY_FOR_REREVIEW'
            ):
                return 'SUCCESS'

            return 'INFO'

        # --------------------------------------------------------
        # EventOutbox
        # --------------------------------------------------------

        q=_rb.EventOutbox.query.filter(
            _rb.EventOutbox.entity_type=='order'
        )

        if order_filter is not None:
            q=q.filter(
                _rb.EventOutbox.entity_id==
                str(order_filter)
            )

        outbox_rows=(
            q.order_by(
                _rb.EventOutbox.id.desc()
            )
            .limit(limit)
            .all()
        )

        for row in outbox_rows:

            try:
                payload=_rb.json.loads(
                    row.payload_json or '{}'
                )
            except Exception:
                payload={}

            stage,status=outbox_stage(
                row.event_type,
                payload
            )

            append_event(
                source='OUTBOX',
                source_id=row.id,
                event_type=row.event_type,
                stage=stage,
                status=status,
                timestamp=getattr(
                    row,
                    'created_at',
                    None
                ),
                order_id=row.entity_id,
                details='',
                payload=payload
            )

        # --------------------------------------------------------
        # PACS / DICOM receipt
        # RB_LIVE_COMMAND_CENTER_PACS_MATCHING_EVENTS_V1
        # --------------------------------------------------------

        q=_rb.PacsStudyInbox.query

        if order_filter is not None:
            q=q.filter(
                _rb.PacsStudyInbox.order_id==order_filter
            )

        inbox_rows=(
            q.order_by(
                _rb.PacsStudyInbox.id.desc()
            )
            .limit(limit)
            .all()
        )

        for row in inbox_rows:

            append_event(
                source='PACS_INBOX',
                source_id=f'{row.id}:received',
                event_type='PACS_STUDY_RECEIVED',
                stage='PACS',
                status=(
                    'SUCCESS'
                    if int(row.image_count or 0)>0
                    else 'WAITING'
                ),
                timestamp=(
                    row.first_seen_at
                    or row.last_seen_at
                ),
                order_id=row.order_id,
                details=(
                    f'state={row.state or ""}; '
                    f'images={int(row.image_count or 0)}; '
                    f'source_ae={row.source_ae or ""}'
                ),
                payload={
                    'orthanc_study_id':
                        row.orthanc_study_id or '',
                    'study_instance_uid':
                        row.study_instance_uid or '',
                    'pacs_accession':
                        row.accession or '',
                    'modality':
                        row.modality or '',
                    'source_ae':
                        row.source_ae or '',
                    'image_count':
                        int(row.image_count or 0),
                    'inbox_state':
                        row.state or '',
                }
            )

            inbox_state=str(
                row.state or ''
            ).upper()

            if inbox_state=='REVIEW_REQUIRED':
                append_event(
                    source='PACS_INBOX',
                    source_id=f'{row.id}:matching',
                    event_type='PACS_MATCH_REVIEW_REQUIRED',
                    stage='MATCHING',
                    status='BLOCKED',
                    timestamp=(
                        row.last_seen_at
                        or row.first_seen_at
                    ),
                    order_id=row.order_id,
                    details=(
                        row.error_text
                        or row.match_method
                        or 'PACS matching review required'
                    ),
                    payload={
                        'orthanc_study_id':
                            row.orthanc_study_id or '',
                        'study_instance_uid':
                            row.study_instance_uid or '',
                        'match_method':
                            row.match_method or '',
                        'inbox_state':
                            row.state or '',
                    }
                )

            elif inbox_state=='ERROR':
                append_event(
                    source='PACS_INBOX',
                    source_id=f'{row.id}:matching',
                    event_type='PACS_MATCH_ERROR',
                    stage='MATCHING',
                    status='FAILED',
                    timestamp=(
                        row.last_seen_at
                        or row.first_seen_at
                    ),
                    order_id=row.order_id,
                    details=(
                        row.error_text
                        or 'PACS inbox error'
                    ),
                    payload={
                        'orthanc_study_id':
                            row.orthanc_study_id or '',
                        'study_instance_uid':
                            row.study_instance_uid or '',
                        'match_method':
                            row.match_method or '',
                        'inbox_state':
                            row.state or '',
                    }
                )

        # --------------------------------------------------------
        # Confirmed PACS matches
        # --------------------------------------------------------

        q=_rb.PacsStudyMatch.query

        if order_filter is not None:
            q=q.filter(
                _rb.PacsStudyMatch.order_id
                ==order_filter
            )

        match_rows=(
            q.order_by(
                _rb.PacsStudyMatch.id.desc()
            )
            .limit(limit)
            .all()
        )

        for row in match_rows:

            append_event(
                source='PACS_MATCH',
                source_id=row.id,
                event_type='PACS_MATCH_CONFIRMED',
                stage='MATCHING',
                status='SUCCESS',
                timestamp=row.confirmed_at,
                order_id=row.order_id,
                details=(
                    f'method={row.match_method or ""}; '
                    f'confidence={row.confidence or ""}; '
                    f'current={bool(row.is_current)}'
                ),
                payload={
                    'orthanc_study_id':
                        row.orthanc_study_id or '',
                    'match_method':
                        row.match_method or '',
                    'confidence':
                        row.confidence or '',
                    'is_current':
                        bool(row.is_current),
                    'pacs_accession':
                        row.pacs_accession or '',
                }
            )

        # --------------------------------------------------------
        # PACS reconciliation / resolution history
        # --------------------------------------------------------

        q=_rb.PacsResolutionEvent.query

        if order_filter is not None:
            q=q.filter(
                _rb.PacsResolutionEvent.order_id
                ==order_filter
            )

        resolution_rows=(
            q.order_by(
                _rb.PacsResolutionEvent.id.desc()
            )
            .limit(limit)
            .all()
        )

        for row in resolution_rows:

            resolution_type=str(
                row.event_type or ''
            ).upper()

            resolution_status=(
                'SUCCESS'
                if resolution_type in (
                    'PRIMARY_LINK_CHANGED',
                    'MATCH_CONFIRMED',
                    'RESOLVED'
                )
                else 'INFO'
            )

            append_event(
                source='PACS_RESOLUTION',
                source_id=row.id,
                event_type=row.event_type,
                stage='MATCHING',
                status=resolution_status,
                timestamp=row.created_at,
                order_id=row.order_id,
                details=row.reason,
                payload={
                    'old_orthanc_study_id':
                        row.old_orthanc_study_id or '',
                    'new_orthanc_study_id':
                        row.new_orthanc_study_id or '',
                    'old_study_instance_uid':
                        row.old_study_instance_uid or '',
                    'new_study_instance_uid':
                        row.new_study_instance_uid or '',
                }
            )

        # --------------------------------------------------------
        # Assignment Events
        # --------------------------------------------------------

        q=_rb.AssignmentEscalationEvent.query

        if order_filter is not None:
            q=q.filter(
                _rb.AssignmentEscalationEvent.order_id
                ==order_filter
            )

        assignment_rows=(
            q.order_by(
                _rb.AssignmentEscalationEvent.id.desc()
            )
            .limit(limit)
            .all()
        )

        for row in assignment_rows:

            append_event(
                source='ASSIGNMENT',
                source_id=row.id,
                event_type=row.event_type,
                stage='ASSIGNMENT',
                status=assignment_status(
                    row.event_type
                ),
                timestamp=row.created_at,
                order_id=row.order_id,
                details=row.details,
                payload={
                    'offer_id':row.offer_id
                }
            )

        # --------------------------------------------------------
        # Case Workflow Events
        # --------------------------------------------------------

        q=_rb.CaseWorkflowEvent.query

        if order_filter is not None:
            q=q.filter(
                _rb.CaseWorkflowEvent.order_id
                ==order_filter
            )

        workflow_rows=(
            q.order_by(
                _rb.CaseWorkflowEvent.id.desc()
            )
            .limit(limit)
            .all()
        )

        for row in workflow_rows:

            append_event(
                source='WORKFLOW',
                source_id=row.id,
                event_type=row.event_type,
                stage='READINESS',
                status=workflow_status(
                    row.event_type
                ),
                timestamp=row.created_at,
                order_id=row.order_id,
                details=getattr(
                    row,
                    'details',
                    ''
                )
            )

        # --------------------------------------------------------
        # Order-specific reporting audit
        # --------------------------------------------------------

        reporting_actions=[
            'OHIF_REPORT_OPENED',
            'ONLYOFFICE_EDITOR_OPENED',
            'REPORT_EDIT_LEASE_ACQUIRED',
            'REPORT_EDIT_LEASE_RELEASED',
            'REPORT_FINALIZED',
            'REPORT_VERIFIED',
            'REPORT_SAVED',
        ]

        q=_rb.AuditLog.query.filter(
            _rb.AuditLog.entity=='order',
            _rb.AuditLog.action.in_(
                reporting_actions
            )
        )

        if order_filter is not None:
            q=q.filter(
                _rb.AuditLog.entity_id==
                str(order_filter)
            )

        audit_rows=(
            q.order_by(
                _rb.AuditLog.id.desc()
            )
            .limit(limit)
            .all()
        )

        for row in audit_rows:

            action=str(
                row.action or ''
            ).upper()

            if 'FINAL' in action:
                status='SUCCESS'
            elif 'OPENED' in action:
                status='RUNNING'
            elif 'ACQUIRED' in action:
                status='RUNNING'
            elif 'RELEASED' in action:
                status='INFO'
            else:
                status='INFO'

            append_event(
                source='AUDIT',
                source_id=row.id,
                event_type=row.action,
                stage='REPORTING',
                status=status,
                timestamp=row.created_at,
                order_id=row.entity_id,
                details=row.details
            )

        # Sort normalized events using real timestamps.
        events.sort(
            key=lambda x:(
                x.get('timestamp') or '',
                x.get('event_key') or ''
            ),
            reverse=True
        )

        events=events[:limit]

        return _rb.jsonify({
            'schema':
                'radbridge.command_center.events.v1',
            'generated_at':
                _rb.datetime.utcnow().isoformat()+'Z',
            'order_filter':order_filter,
            'count':len(events),
            'events':events
        })
    return command_center_events


def install_0514(_rb):
    @_rb.app.route('/api/command-center/snapshot')
    @_rb.require_perm('audit.view')
    def command_center_snapshot():
        """
    Read-only monitoring snapshot.

    This endpoint must not become part of the clinical workflow.
    It reads existing RadBridge operational state only.
    """

        def grouped_counts(model, column):
            rows = (
                _rb.db.session.query(
                    column,
                    _rb.db.func.count(model.id)
                )
                .group_by(column)
                .all()
            )

            return {
                str(value or 'UNKNOWN').upper(): int(count or 0)
                for value, count in rows
            }

        # --------------------------------------------------------
        # Orders / Exam
        # --------------------------------------------------------

        order_status = grouped_counts(
            _rb.Order,
            _rb.Order.status
        )

        exam_status = grouped_counts(
            _rb.Order,
            _rb.Order.exam_status
        )

        pacs_status = grouped_counts(
            _rb.Order,
            _rb.Order.pacs_status
        )

        # --------------------------------------------------------
        # PACS / Matching
        # --------------------------------------------------------

        pacs_inbox_state = grouped_counts(
            _rb.PacsStudyInbox,
            _rb.PacsStudyInbox.state
        )

        unmatched_studies = (
            _rb.PacsStudyInbox.query
            .filter(_rb.PacsStudyInbox.order_id.is_(None))
            .count()
        )

        current_matches = (
            _rb.PacsStudyMatch.query
            .filter(_rb.PacsStudyMatch.is_current.is_(True))
            .count()
        )

        # --------------------------------------------------------
        # Case Readiness
        # --------------------------------------------------------

        readiness_status = grouped_counts(
            _rb.CaseReadiness,
            _rb.CaseReadiness.status
        )

        readiness_blockers = {
            'MISSING_PACS': (
                _rb.CaseReadiness.query
                .filter(_rb.CaseReadiness.missing_pacs.is_(True))
                .count()
            ),
            'INCOMPLETE_IMAGES': (
                _rb.CaseReadiness.query
                .filter(_rb.CaseReadiness.incomplete_images.is_(True))
                .count()
            ),
            'MISSING_SERIES': (
                _rb.CaseReadiness.query
                .filter(_rb.CaseReadiness.missing_series.is_(True))
                .count()
            ),
            'MISSING_HISTORY': (
                _rb.CaseReadiness.query
                .filter(_rb.CaseReadiness.missing_history.is_(True))
                .count()
            ),
            'MISSING_ATTACHMENTS': (
                _rb.CaseReadiness.query
                .filter(_rb.CaseReadiness.missing_attachments.is_(True))
                .count()
            ),
            'MISSING_DOCUMENTS': (
                _rb.CaseReadiness.query
                .filter(_rb.CaseReadiness.missing_documents.is_(True))
                .count()
            ),
        }

        # --------------------------------------------------------
        # Assignment
        # --------------------------------------------------------

        assignment_offers = grouped_counts(
            _rb.AssignmentOffer,
            _rb.AssignmentOffer.status
        )

        active_assignments = (
            _rb.CaseAssignment.query
            .filter(_rb.CaseAssignment.active.is_(True))
            .count()
        )

        ready_unassigned = (
            _rb.db.session.query(_rb.Order.id)
            .join(
                _rb.CaseReadiness,
                _rb.CaseReadiness.order_id == _rb.Order.id
            )
            .outerjoin(
                _rb.CaseAssignment,
                _rb.db.and_(
                    _rb.CaseAssignment.order_id == _rb.Order.id,
                    _rb.CaseAssignment.active.is_(True)
                )
            )
            .filter(
                _rb.Order.exam_status == 'EXAM_COMPLETED',
                _rb.Order.pacs_status == 'IMAGES_COMPLETE',
                _rb.CaseAssignment.id.is_(None)
            )
            .count()
        )

        # --------------------------------------------------------
        # Reporting
        # --------------------------------------------------------

        report_status = grouped_counts(
            _rb.Report,
            _rb.Report.status
        )

        # --------------------------------------------------------
        # Event / Error visibility
        # --------------------------------------------------------

        outbox_status = grouped_counts(
            _rb.EventOutbox,
            _rb.EventOutbox.status
        )

        return _rb.jsonify({
            'schema': 'radbridge.command_center.snapshot.v1',
            'generated_at': _rb.datetime.utcnow().isoformat() + 'Z',

            'orders': {
                'status': order_status,
                'exam_status': exam_status,
            },

            'pacs': {
                'order_pacs_status': pacs_status,
                'inbox_state': pacs_inbox_state,
                'unmatched_studies': int(unmatched_studies),
                'current_matches': int(current_matches),
            },

            'readiness': {
                'status': readiness_status,
                'blockers': readiness_blockers,
            },

            'assignment': {
                'offer_status': assignment_offers,
                'active_assignments': int(active_assignments),
                'ready_unassigned': int(ready_unassigned),
            },

            'reporting': {
                'status': report_status,
            },

            'events': {
                'outbox_status': outbox_status,
            },
        })
    return command_center_snapshot


def install_0519(_rb):
    @_rb.app.route('/accounting/receivables')
    @_rb.require_perm('receivables.view')
    def receivables():
        q=_rb.Order.query
        branch_id=_rb.request.args.get('branch_id',type=int)
        contract_id=_rb.request.args.get('contract_id',type=int)
        if branch_id: q=q.filter(_rb.Order.branch_id==branch_id)
        if contract_id: q=q.filter(_rb.Order.contract_id==contract_id)
        rows=[]
        for o in q.order_by(_rb.Order.scheduled.desc()).limit(5000).all():
            bal=_rb.order_balance(o)
            if bal>0.009:
                rows.append((o,bal))
        total=sum(x[1] for x in rows)
        return _rb.render_template('receivables.html',rows=rows,total=total,
            branches=_rb.Branch.query.order_by(_rb.Branch.name).all(),
            contracts=_rb.Contract.query.order_by(_rb.Contract.name).all())
    return receivables


def install_0520(_rb):
    @_rb.app.route('/accounting/receivables.csv')
    @_rb.require_perm('export.view')
    def receivables_csv():
        s=_rb.io.StringIO(); w=_rb.csv.writer(s)
        w.writerow(['Accession','Patient ID','Patient','Date','Branch','Procedure','Payer','Patient Share','Paid','Balance'])
        for o in _rb.Order.query.order_by(_rb.Order.scheduled.desc()).all():
            bal=_rb.order_balance(o)
            if bal>0.009:
                w.writerow([o.accession,o.patient.patient_id,o.patient.name,o.scheduled.isoformat(sep=' '),
                    o.branch.name if o.branch else '',o.proc.name if o.proc else o.procedure,
                    o.contract.name if o.contract else 'Cash / Private',o.patient_share or o.contract_price or o.gross_price or 0,
                    o.paid_amount or 0,bal])
        return _rb.send_file(_rb.io.BytesIO(s.getvalue().encode('utf-8-sig')),as_attachment=True,
            download_name='patient-receivables.csv',mimetype='text/csv; charset=utf-8')
    return receivables_csv


def install_0621(_rb):
    @_rb.app.get('/correction-center')
    @_rb.login_required
    def correction_center():
        if not (_rb.correction_can_request() or _rb.correction_can_review()):
            _rb.abort(403)
        u=_rb.current_user()
        term=(_rb.request.args.get('q') or '').strip()
        orders=_rb.correction_search_orders(term,u)
        my_requests=_rb.CorrectionRequest.query.filter_by(requested_by=u.id).order_by(_rb.CorrectionRequest.id.desc()).limit(50).all()
        pending_count=0
        if _rb.correction_can_review():
            rq=_rb.CorrectionRequest.query.filter(_rb.CorrectionRequest.status.in_(('NEW','UNDER_REVIEW','NEED_INFO','APPROVED')))
            if u.branch_id and not (u.role and u.role.code=='SUPER_ADMIN'):
                rq=rq.filter(_rb.db.or_(_rb.CorrectionRequest.branch_id==u.branch_id,_rb.CorrectionRequest.branch_id.is_(None)))
            pending_count=rq.count()
        return _rb.render_template(
            'correction_center.html',q=term,orders=orders,my_requests=my_requests,
            request_types=_rb.CORRECTION_REQUEST_TYPES,can_review=_rb.correction_can_review(),
            pending_count=pending_count,
        )
    return correction_center


def install_0624(_rb):
    @_rb.app.post('/correction-center/request')
    @_rb.require_perm('correction.request')
    def correction_request_submit():
        u=_rb.current_user()
        order_id=_rb.request.form.get('order_id',type=int)
        request_type=(_rb.request.form.get('request_type') or '').strip().upper()
        reason=(_rb.request.form.get('reason') or '').strip()
        if not order_id:
            _rb.abort(400,'Order is required.')
        if request_type not in _rb.CORRECTION_REQUEST_TYPE_CODES:
            _rb.abort(400,'Invalid correction request type.')
        if request_type=='WRONG_DEMOGRAPHICS':
            return _rb.redirect(_rb.url_for('patient_demographics_correction',order_id=order_id))
        if len(reason)<5:
            _rb.abort(400,'Correction reason must contain at least 5 characters.')
        order=_rb.Order.query.get_or_404(order_id)
        if not _rb.correction_branch_allowed(order,u):
            _rb.abort(403)
        duplicate=_rb.CorrectionRequest.query.filter(
            _rb.CorrectionRequest.order_id==order.id,
            _rb.CorrectionRequest.request_type==request_type,
            _rb.CorrectionRequest.status.in_(_rb.CORRECTION_OPEN_STATUSES),
        ).first()
        if duplicate:
            _rb.abort(409,f'An active {request_type} request already exists for this order.')
        row=_rb.CorrectionRequest(
            order_id=order.id,
            branch_id=order.branch_id or u.branch_id,
            request_type=request_type,
            status='NEW',
            reason=reason[:2000],
            requested_by=u.id,
            updated_at=_rb.datetime.utcnow(),
        )
        _rb.db.session.add(row)
        try:
            _rb.db.session.flush()
            _rb.audit(
                'CORRECTION_REQUEST_CREATED','correction_request',row.id,
                f'order_id={order.id};accession={order.accession};type={request_type};branch_id={row.branch_id or ""};reason={reason[:1000]}'
            )
            _rb.db.session.commit()
        except _rb.IntegrityError:
            _rb.db.session.rollback()
            _rb.abort(409,f'An active {request_type} request already exists for this order.')
        _rb.flash('Correction request submitted for coordinator review.','success')
        return _rb.redirect(_rb.url_for('correction_center',q=order.accession))
    return correction_request_submit


def install_0627(_rb):
    @_rb.app.get('/correction-center/executions')
    @_rb.require_perm('correction.execute')
    def correction_execution_queue():
        user=_rb.current_user()

        approved=(
            _rb.CorrectionRequest.query
            .filter(
                _rb.CorrectionRequest.status=='APPROVED'
            )
            .order_by(
                _rb.CorrectionRequest.id.desc()
            )
            .limit(300)
            .all()
        )

        approved_rows=[]

        for row in approved:
            if row.requested_by==user.id:
                continue

            if (
                row.assigned_to
                and row.assigned_to==user.id
            ):
                continue

            if (
                row.order
                and not _rb.correction_branch_allowed(
                    row.order,
                    user
                )
            ):
                continue

            execution=(
                _rb.CorrectionExecution.query
                .filter_by(
                    correction_request_id=row.id
                )
                .first()
            )

            approved_rows.append(
                {
                    'request':row,
                    'execution':execution,
                }
            )

        executions=(
            _rb.CorrectionExecution.query
            .order_by(
                _rb.CorrectionExecution.id.desc()
            )
            .limit(300)
            .all()
        )

        visible_executions=[]

        for execution in executions:
            order=_rb.db.session.get(
                _rb.Order,
                execution.order_id
            )

            if (
                order
                and _rb.correction_branch_allowed(
                    order,
                    user
                )
            ):
                visible_executions.append(
                    execution
                )

        return _rb.render_template(
            'correction_execution_queue.html',
            approved_rows=approved_rows,
            executions=visible_executions,
        )
    return correction_execution_queue


def install_0628(_rb):
    @_rb.app.post(
        '/correction-center/requests/'
        '<int:request_id>/execution/prepare'
    )
    @_rb.require_perm('correction.execute')
    def correction_execution_prepare_route(
        request_id
    ):
        user=_rb.current_user()

        row=(
            _rb.CorrectionRequest.query
            .filter_by(id=request_id)
            .with_for_update()
            .first_or_404()
        )

        try:
            _rb.correction_execution_assert_request_actor(
                row,
                user
            )

            execution=_rb.correction_execution_prepare(
                row
            )

            _rb.audit(
                'CORRECTION_EXECUTION_PREPARED',
                'correction_execution',
                execution.id,
                (
                    f'correction_request_id={row.id};'
                    f'order_id={row.order_id};'
                    f'type={row.request_type};'
                    f'executor_candidate={user.id};'
                    f'status={execution.status};'
                    f'state_version={execution.state_version}'
                )
            )

            _rb.db.session.commit()

        except (
            ValueError,
            PermissionError,
        ) as exc:
            _rb.db.session.rollback()
            _rb.correction_execution_http_error(exc)

        _rb.flash(
            'Execution ledger prepared. '
            'No correction has been executed.',
            'success'
        )

        return _rb.redirect(
            _rb.url_for(
                'correction_execution_queue'
            )
        )
    return correction_execution_prepare_route


def install_0629(_rb):
    @_rb.app.post(
        '/correction-center/executions/'
        '<int:execution_id>/claim'
    )
    @_rb.require_perm('correction.execute')
    def correction_execution_claim_route(
        execution_id
    ):
        user=_rb.current_user()

        execution=(
            _rb.CorrectionExecution.query
            .filter_by(id=execution_id)
            .with_for_update()
            .first_or_404()
        )

        expected_version=_rb.request.form.get(
            'expected_version',
            type=int
        )

        if expected_version is None:
            _rb.abort(
                400,
                'Expected state version is required.'
            )

        try:
            updated=_rb.correction_execution_transition(
                execution,
                'CLAIMED_FOR_EXECUTION',
                user,
                expected_version=expected_version,
            )

            _rb.audit(
                'CORRECTION_EXECUTION_CLAIMED',
                'correction_execution',
                updated.id,
                (
                    f'user_id={user.id};'
                    f'status={updated.status};'
                    f'state_version={updated.state_version}'
                )
            )

            _rb.db.session.commit()

        except (
            ValueError,
            PermissionError,
        ) as exc:
            _rb.db.session.rollback()
            _rb.correction_execution_http_error(exc)

        return _rb.redirect(
            _rb.url_for(
                'correction_execution_queue'
            )
        )
    return correction_execution_claim_route


def install_0630(_rb):
    @_rb.app.post(
        '/correction-center/executions/'
        '<int:execution_id>/hold'
    )
    @_rb.require_perm('correction.execute')
    def correction_execution_hold_route(
        execution_id
    ):
        user=_rb.current_user()

        execution=(
            _rb.CorrectionExecution.query
            .filter_by(id=execution_id)
            .with_for_update()
            .first_or_404()
        )

        expected_version=_rb.request.form.get(
            'expected_version',
            type=int
        )

        if expected_version is None:
            _rb.abort(
                400,
                'Expected state version is required.'
            )

        try:
            updated=_rb.correction_execution_hold(
                execution,
                user,
                expected_version=expected_version,
            )

            _rb.audit(
                'CORRECTION_EXECUTION_HELD',
                'correction_execution',
                updated.id,
                (
                    f'user_id={user.id};'
                    f'status={updated.status};'
                    f'state_version={updated.state_version}'
                )
            )

            _rb.db.session.commit()

        except (
            ValueError,
            PermissionError,
        ) as exc:
            _rb.db.session.rollback()
            _rb.correction_execution_http_error(exc)

        return _rb.redirect(
            _rb.url_for(
                'correction_execution_queue'
            )
        )
    return correction_execution_hold_route


def install_0631(_rb):
    @_rb.app.post(
        '/correction-center/executions/'
        '<int:execution_id>/release'
    )
    @_rb.require_perm('correction.execute')
    def correction_execution_release_route(
        execution_id
    ):
        user=_rb.current_user()

        execution=(
            _rb.CorrectionExecution.query
            .filter_by(id=execution_id)
            .with_for_update()
            .first_or_404()
        )

        expected_version=_rb.request.form.get(
            'expected_version',
            type=int
        )

        if expected_version is None:
            _rb.abort(
                400,
                'Expected state version is required.'
            )

        try:
            updated=_rb.correction_execution_release(
                execution,
                user,
                expected_version=expected_version,
            )

            _rb.audit(
                'CORRECTION_EXECUTION_RELEASED',
                'correction_execution',
                updated.id,
                (
                    f'user_id={user.id};'
                    f'status={updated.status};'
                    f'state_version={updated.state_version}'
                )
            )

            _rb.db.session.commit()

        except (
            ValueError,
            PermissionError,
        ) as exc:
            _rb.db.session.rollback()
            _rb.correction_execution_http_error(exc)

        return _rb.redirect(
            _rb.url_for(
                'correction_execution_queue'
            )
        )
    return correction_execution_release_route


def install_0633(_rb):
    @_rb.app.post(
        '/correction-center/executions/'
        '<int:execution_id>/execute'
    )
    @_rb.require_perm('correction.execute')
    def correction_execution_execute_route(
        execution_id,
    ):
        enabled=(
            _rb.os.getenv(
                'RADBRIDGE_CORRECTION_DESTRUCTIVE_EXECUTION_ENABLED',
                '0',
            )
            or '0'
        ).strip().lower()

        if enabled not in (
            '1',
            'true',
            'yes',
            'on',
        ):
            _rb.abort(
                503,
                'Correction destructive execution is disabled.',
            )

        actor=_rb.current_user()

        if not actor:
            _rb.abort(401)

        expected_version=(
            _rb.request.form.get('expected_version')
            or ''
        ).strip()

        typed_accession=(
            _rb.request.form.get('confirm_accession')
            or ''
        ).strip()

        reason=(
            _rb.request.form.get('reason')
            or ''
        ).strip()

        if not expected_version:
            _rb.abort(
                400,
                'Expected state version is required.',
            )

        try:
            int(expected_version)
        except (TypeError,ValueError):
            _rb.abort(
                400,
                'Expected state version is invalid.',
            )

        if not typed_accession:
            _rb.abort(
                400,
                'Accession confirmation is required.',
            )

        if len(reason)<5:
            _rb.abort(
                400,
                'Execution reason must contain at least 5 characters.',
            )

        payload,status_code=_rb.correction_wrong_images_execute(
            execution_id,
            actor,
            expected_version,
            typed_accession,
            reason,
        )

        if status_code==200:
            _rb.flash(
                'Correction execution completed and verified.',
                'success',
            )

        elif status_code==409:
            _rb.flash(
                payload.get('error')
                or 'Correction execution was blocked.',
                'danger',
            )

        elif status_code>=500:
            _rb.flash(
                payload.get('error')
                or 'Correction execution failed.',
                'danger',
            )

        else:
            _rb.flash(
                payload.get('error')
                or 'Correction execution was not completed.',
                'warning',
            )

        return (
            _rb.jsonify(payload),
            status_code,
        )
    return correction_execution_execute_route


def install_0634(_rb):
    @_rb.app.get('/correction-center/requests')
    @_rb.require_perm('correction.review')
    def correction_request_queue():
        u=_rb.current_user()
        status=(_rb.request.args.get('status') or 'ALL').strip().upper()
        if status not in _rb.CORRECTION_REVIEW_STATUSES:
            status='ALL'
        q=_rb.CorrectionRequest.query
        if u.branch_id and not (u.role and u.role.code=='SUPER_ADMIN'):
            q=q.filter(_rb.db.or_(_rb.CorrectionRequest.branch_id==u.branch_id,_rb.CorrectionRequest.branch_id.is_(None)))
        if status!='ALL':
            q=q.filter(_rb.CorrectionRequest.status==status)
        rows=q.order_by(_rb.CorrectionRequest.id.desc()).limit(300).all()
        return _rb.render_template(
            'correction_request_queue.html',rows=rows,status=status,
            statuses=_rb.CORRECTION_REVIEW_STATUSES,
        )
    return correction_request_queue


def install_0635(_rb):
    @_rb.app.post('/correction-center/requests/<int:request_id>/action')
    @_rb.require_perm('correction.review')
    def correction_request_action(request_id):
        u=_rb.current_user()
        row=(
            _rb.CorrectionRequest.query
            .filter_by(id=request_id)
            .with_for_update()
            .first_or_404()
        )
        if row.order and not _rb.correction_branch_allowed(row.order,u):
            _rb.abort(403)
        action=(_rb.request.form.get('action') or '').strip().upper()
        note=(_rb.request.form.get('note') or '').strip()
        if action not in ('CLAIM','NEED_INFO','APPROVE','REJECT'):
            _rb.abort(400,'Invalid correction review action.')
        # Four-eyes rule applies to every review action, not only approval.
        # A requester cannot claim, request information on, approve, or reject
        # their own correction request even if they hold multiple roles.
        if row.requested_by==u.id:
            _rb.abort(409,'Requester cannot review their own correction request.')
        if action!='CLAIM' and len(note)<5:
            _rb.abort(400,'Review note must contain at least 5 characters.')
        if row.assigned_to and row.assigned_to!=u.id and not (u.role and u.role.code=='SUPER_ADMIN'):
            _rb.abort(403)
        if action=='APPROVE' and row.request_type=='WRONG_DEMOGRAPHICS':
            from patient_correction_policy import assert_approvable
            assert_approvable(row)
        if action=='CLAIM':
            if row.status not in ('NEW','NEED_INFO','UNDER_REVIEW'):
                _rb.abort(409,'This request cannot be claimed in its current state.')
            row.assigned_to=u.id
            row.status='UNDER_REVIEW'
        elif action=='NEED_INFO':
            if row.status not in ('NEW','UNDER_REVIEW'):
                _rb.abort(409,'This request cannot request more information in its current state.')
            row.assigned_to=u.id
            row.status='NEED_INFO'
            row.review_note=note[:2000]
            row.reviewed_at=_rb.datetime.utcnow()
        elif action=='APPROVE':
            if row.status not in ('NEW','UNDER_REVIEW','NEED_INFO'):
                _rb.abort(409,'This request cannot be approved in its current state.')
            row.assigned_to=u.id
            row.status='APPROVED'
            row.review_note=note[:2000]
            row.reviewed_at=_rb.datetime.utcnow()
        elif action=='REJECT':
            if row.status not in ('NEW','UNDER_REVIEW','NEED_INFO'):
                _rb.abort(409,'This request cannot be rejected in its current state.')
            row.assigned_to=u.id
            row.status='REJECTED'
            row.review_note=note[:2000]
            row.reviewed_at=_rb.datetime.utcnow()
            row.closed_at=_rb.datetime.utcnow()
        row.updated_at=_rb.datetime.utcnow()
        _rb.audit(
            'CORRECTION_REQUEST_REVIEW','correction_request',row.id,
            f'action={action};status={row.status};order_id={row.order_id};accession={row.order.accession if row.order else ""};requester={row.requested_by};reviewer={u.id};note={note[:1000]}'
        )
        _rb.db.session.commit()
        _rb.flash(f'Correction request {row.id}: {row.status}.','success')
        return _rb.redirect(_rb.url_for('correction_request_queue',status=_rb.request.form.get('return_status','ALL')))
    return correction_request_action


def install_0652(_rb):
    @_rb.app.route('/studio')
    @_rb.require_perm('users.view')
    def studio_home(): return _rb.render_template('studio_home.html')
    return studio_home


def install_0653(_rb):
    @_rb.app.route('/studio/templates/<template_type>',methods=['GET','POST'])
    @_rb.require_perm('users.view')
    def studio_templates(template_type):
        typ=template_type.upper()
        if typ not in ('FORM','RECEIPT','REPORT'): _rb.abort(404)
        if _rb.request.method=='POST':
            row=_rb.StudioTemplate(template_type=typ,name=(_rb.request.form.get('name') or typ+' Template').strip(),
              scope=(_rb.request.form.get('scope') or 'GLOBAL').upper(),branch_id=_rb.request.form.get('branch_id',type=int),
              layout_json=(_rb.request.form.get('layout_json') or '{}').strip(),notes=(_rb.request.form.get('notes') or '').strip(),
              created_by=_rb.current_user().id)
            _rb.db.session.add(row); _rb.db.session.commit(); return _rb.redirect(_rb.url_for('studio_templates',template_type=typ))
        return _rb.render_template('studio_templates.html',template_type=typ,
          rows=_rb.StudioTemplate.query.filter_by(template_type=typ).order_by(_rb.StudioTemplate.id.desc()).all(),
          branches=_rb.Branch.query.order_by(_rb.Branch.name).all())
    return studio_templates


def install_0654(_rb):
    @_rb.app.post('/studio/templates/<int:template_id>/publish')
    @_rb.require_perm('users.view')
    def studio_template_publish(template_id):
        row=_rb.StudioTemplate.query.get_or_404(template_id)
        if row.template_type=='REPORT_HEADER': _rb.abort(403)
        _rb.db.session.add(_rb.StudioTemplateVersion(template_id=row.id,version_no=row.version_no,
          snapshot_json=_rb.json.dumps({'layout_json':row.layout_json,'notes':row.notes,'status':row.status},ensure_ascii=False),
          created_by=_rb.current_user().id))
        row.status='PUBLISHED'; row.published_at=_rb.datetime.utcnow(); _rb.db.session.commit()
        return _rb.redirect(_rb.request.referrer or _rb.url_for('studio_home'))
    return studio_template_publish


def install_0655(_rb):
    @_rb.app.route('/doctor/templates',methods=['GET','POST'])
    @_rb.login_required
    def doctor_templates():
        if _rb.request.method=='POST':
            f=_rb.request.files.get('file')
            if not f or not f.filename.lower().endswith('.docx'): _rb.abort(400)
            folder=_rb.os.path.join(_rb.REPORT_DIR,'doctor-templates',str(_rb.current_user().id)); _rb.os.makedirs(folder,exist_ok=True)
            safe=_rb.re.sub(r'[^A-Za-z0-9._-]','_',f.filename); path=_rb.os.path.join(folder,f'{int(_rb.datetime.utcnow().timestamp())}_{safe}'); f.save(path)
            _rb.db.session.add(_rb.DoctorWordTemplate(owner_user_id=_rb.current_user().id,name=(_rb.request.form.get('name') or f.filename).strip(),
              modality=(_rb.request.form.get('modality') or '').strip(),procedure_id=_rb.request.form.get('procedure_id',type=int),
              visibility=(_rb.request.form.get('visibility') or 'PERSONAL').upper(),file_path=path,original_name=f.filename))
            _rb.db.session.commit(); return _rb.redirect(_rb.url_for('doctor_templates'))
        rows=_rb.DoctorWordTemplate.query.filter(_rb.or_(_rb.DoctorWordTemplate.owner_user_id==_rb.current_user().id,
          _rb.DoctorWordTemplate.visibility.in_(['DEPARTMENT','SHARED']))).filter_by(active=True).order_by(_rb.DoctorWordTemplate.created_at.desc()).all()
        return _rb.render_template('doctor_templates.html',rows=rows,procedures=_rb.Procedure.query.filter_by(active=True).order_by(_rb.Procedure.name).all())
    return doctor_templates


def install_0657(_rb):
    @_rb.app.get('/studio/templates/<int:template_id>/preview')
    @_rb.require_perm('users.view')
    def studio_template_preview(template_id):
        tpl=_rb.StudioTemplate.query.get_or_404(template_id)
        try: layout=_rb.json.loads(tpl.layout_json or '{}')
        except Exception: layout={}
        return _rb.render_template('studio_template_preview.html',template=tpl,layout=layout)
    return studio_template_preview


def install_0668(_rb):
    @_rb.app.get('/my/quick-actions')
    @_rb.login_required
    def my_quick_actions():
        return _rb.render_template('my_quick_actions.html',
            action_role=_rb.quick_action_role(),actions=_rb.role_quick_actions())
    return my_quick_actions


def install_0669(_rb):
    @_rb.app.get('/search')
    @_rb.login_required
    def universal_search():
        f=_rb.common_search_filters()
        q=f['q']
        patients=[]
        orders=[]
        if q:
            patients=_rb.Patient.query.filter(_rb.or_(
                _rb.Patient.name.ilike(f'%{q}%'),
                _rb.Patient.patient_id.ilike(f'%{q}%'),
                _rb.Patient.phone.ilike(f'%{q}%'),
                _rb.Patient.national_id.ilike(f'%{q}%')
            )).order_by(_rb.Patient.id.desc()).limit(100).all()

            oq=_rb.Order.query.join(_rb.Patient).filter(_rb.or_(
                _rb.Order.accession.ilike(f'%{q}%'),
                _rb.Order.procedure.ilike(f'%{q}%'),
                _rb.Patient.name.ilike(f'%{q}%'),
                _rb.Patient.patient_id.ilike(f'%{q}%'),
                _rb.Patient.phone.ilike(f'%{q}%')
            ))
            if f['branch_id']: oq=oq.filter(_rb.Order.branch_id==f['branch_id'])
            if f['modality']: oq=oq.filter(_rb.Order.modality==f['modality'])
            if f['priority']: oq=oq.filter(_rb.Order.priority==f['priority'])
            orders=oq.order_by(_rb.Order.id.desc()).limit(200).all()

            if f['has_priors']:
                orders=[o for o in orders if _rb.related_prior_orders(o,1) or _rb.external_priors_for_order(o)]
            if f['has_documents']:
                orders=[o for o in orders if _rb.PatientDocument.query.filter_by(patient_id=o.patient_id).first()]

        return _rb.render_template('universal_search.html',
            filters=f,patients=patients,orders=orders,
            branches=_rb.Branch.query.filter_by(active=True).order_by(_rb.Branch.name).all())
    return universal_search


def install_0696(_rb):
    @_rb.app.get('/operations/case-control-center')
    @_rb.require_perm('orders.view')
    def case_operations_control_center():
        """Unified read-only view over assignment, readiness and PACS state."""
        from case_operations_dashboard_service import (
            build_case_operations_snapshot,
        )
        from registration_policy import allowed_registration_branches

        snapshot=build_case_operations_snapshot(
            db=_rb.db,
            Order=_rb.Order,
            Report=_rb.Report,
            CaseAssignment=_rb.CaseAssignment,
            AssignmentOffer=_rb.AssignmentOffer,
            AssignmentStrategy=_rb.AssignmentStrategy,
            AssignmentEscalationEvent=_rb.AssignmentEscalationEvent,
            CaseReadiness=_rb.CaseReadiness,
            PacsStudyInbox=_rb.PacsStudyInbox,
            PacsExamLink=_rb.PacsExamLink,
            PacsResolutionEvent=_rb.PacsResolutionEvent,
            limit=_rb.request.args.get('limit',300,type=int),
            branch_ids=allowed_registration_branches(),
        )

        return _rb.render_template(
            'case_operations_control_center.html',
            snapshot=snapshot,
            can_manage_assignment=_rb.has_perm('assignment.manage'),
            can_reconcile_pacs=_rb.has_perm('pacs.reconcile'),
            can_link_exam=_rb.has_perm('pacs.exam_link'),
            can_view_audit=_rb.has_perm('audit.view'),
            can_resolve_exceptions=_rb.has_perm('pacs.reconcile'),
        )
    return case_operations_control_center


def install_0711(_rb):
    @_rb.app.get('/returned-cases')
    @_rb.login_required
    def returned_cases_queue():
        u=_rb.current_user()
        role=(u.role.code if u and u.role else '').upper()

        q=_rb.CaseWorkflowEvent.query.filter(
            _rb.CaseWorkflowEvent.event_type=='RETURNED'
        )

        if role not in ('SUPER_ADMIN','ADMIN') and not u.branch_id:
            q=q.filter(_rb.db.false())

        if role=='TECHNICIAN':
            q=q.filter(
                _rb.CaseWorkflowEvent.owner_role=='TECHNICIAN'
            )

            if u.branch_id:
                q=q.join(
                    _rb.Order,
                    _rb.CaseWorkflowEvent.order_id==_rb.Order.id
                ).filter(
                    _rb.Order.branch_id==u.branch_id
                )

        elif role in ('RECEPTION','FRONT_DESK'):
            q=q.filter(
                _rb.CaseWorkflowEvent.owner_role=='RECEPTION'
            )

            if u.branch_id:
                q=q.join(
                    _rb.Order,
                    _rb.CaseWorkflowEvent.order_id==_rb.Order.id
                ).filter(
                    _rb.Order.branch_id==u.branch_id
                )

        elif role in ('SUPER_ADMIN','ADMIN','CASE_COORDINATOR','BRANCH_MANAGER'):
            if u.branch_id and role not in ('SUPER_ADMIN','ADMIN'):
                q=q.join(
                    _rb.Order,
                    _rb.CaseWorkflowEvent.order_id==_rb.Order.id
                ).filter(
                    _rb.Order.branch_id==u.branch_id
                )

        else:
            q=q.filter(_rb.db.false())

        returned=q.order_by(
            _rb.CaseWorkflowEvent.created_at.desc()
        ).limit(500).all()

        rows=[]
        seen_orders=set()

        for ev in returned:
            if ev.order_id in seen_orders:
                continue

            state=_rb.case_return_snapshot(ev.order_id)
            latest=state['return_event']

            if not state['open'] or not latest or latest.id!=ev.id:
                continue

            order=_rb.Order.query.get(ev.order_id)
            if order:
                rows.append((ev,order))
                seen_orders.add(ev.order_id)

        return _rb.render_template(
            'returned_cases.html',
            rows=rows
        )
    return returned_cases_queue


def install_0712(_rb):
    @_rb.app.post('/returned-cases/<int:event_id>/resolve')
    @_rb.login_required
    def resolve_returned_case(event_id):
        ev=_rb.CaseWorkflowEvent.query.get_or_404(event_id)
        o=_rb.Order.query.get_or_404(ev.order_id)
        u=_rb.current_user()
        role=(u.role.code if u and u.role else '').upper()

        allowed_roles={
            'TECHNICIAN','RECEPTION','FRONT_DESK','CASE_COORDINATOR',
            'BRANCH_MANAGER','SUPER_ADMIN','ADMIN'
        }
        if role not in allowed_roles:
            _rb.abort(403)
        from technician_queue import scoped_order, mutable_return, ACTIVE_CORRECTIONS
        scoped_order(_rb._reporting_support_sys.modules[_rb.__name__],o)
        mutable_return(_rb._reporting_support_sys.modules[_rb.__name__],o)
        state=_rb.case_return_snapshot(o.id)
        if ev.event_type!='RETURNED' or not state['open'] or state['return_event'].id!=ev.id:
            _rb.abort(409)
        if role in ('TECHNICIAN','RECEPTION','FRONT_DESK') and ev.owner_role != ('TECHNICIAN' if role=='TECHNICIAN' else 'RECEPTION'):
            _rb.abort(403)
        if _rb.CorrectionRequest.query.filter_by(order_id=o.id,request_type='WRONG_IMAGES').filter(_rb.CorrectionRequest.status.in_(ACTIVE_CORRECTIONS)).first():
            _rb.flash('طلب مراجعة الصور لم يُغلق بعد.' if _rb.current_ui_language()=='ar' else 'The image correction request is still open.','warning')
            return _rb.redirect(_rb.url_for('technician_case_workspace',order_id=o.id) if role=='TECHNICIAN' else _rb.url_for('returned_cases_queue'))

        note=(_rb.request.form.get('note') or '').strip()
        _rb.pacs_lookup_order(o)
        strict_images=True
        documents_ready=True
        if ev.owner_role=='TECHNICIAN':
            from technician_queue import correction_documents_ready
            image_result,image_evidence=_rb.technician_completion_evidence(o)
            strict_images=bool(image_result['allowed'])
            documents_ready=correction_documents_ready(_rb._reporting_support_sys.modules[_rb.__name__],o,state)
            readiness=_rb.evaluate_case_readiness(o,pacs_evidence=image_evidence)
        else:
            readiness=_rb.evaluate_case_readiness(o)
        decision=_rb.assignment_readiness_decision(o,refresh_stale=False)
        ready=bool(
            strict_images and documents_ready and decision.get('allowed')
            and (o.exam_status or '').upper()=='EXAM_COMPLETED'
            and (o.pacs_status or '').upper()=='IMAGES_COMPLETE'
        )

        if not ready:
            _rb.db.session.add(_rb.CaseWorkflowEvent(
                order_id=o.id,event_type='RESOLUTION_RECHECK_FAILED',
                owner_role=ev.owner_role,reason_code=ev.reason_code,
                note=note or 'Required correction is still incomplete',created_by=u.id
            ))
            _rb.audit(
                'RETURNED_CASE_RECHECK_BLOCKED','order',o.id,
                f'readiness={getattr(readiness,"status","")}; reason={ev.reason_code}'
            )
            _rb.db.session.commit()
            _rb.flash('The case still has readiness blockers.','warning')
            return _rb.redirect(_rb.url_for('returned_cases_queue'))

        previous_assignment=(
            _rb.CaseAssignment.query
            .filter_by(order_id=o.id,active=False)
            .order_by(_rb.CaseAssignment.unassigned_at.desc(),_rb.CaseAssignment.id.desc())
            .first()
        )
        previous_doctor_id=(previous_assignment.doctor_user_id if previous_assignment else None)

        _rb.db.session.add(_rb.CaseWorkflowEvent(
            order_id=o.id,event_type='READY_FOR_REREVIEW',owner_role='ASSIGNMENT',
            reason_code=ev.reason_code,note=note or 'Requested action completed',created_by=u.id
        ))
        _rb.db.session.commit()

        assignment_status='READY_FOR_ASSIGNMENT'
        if previous_doctor_id and ev.reason_code!='OUTSIDE_SPECIALTY':
            try:
                result=_rb.assign_case_atomically(
                    db=_rb.db,Order=_rb.Order,User=_rb.User,CaseAssignment=_rb.CaseAssignment,
                    Report=_rb.Report,AssignmentOffer=_rb.AssignmentOffer,
                    order_id=o.id,doctor_user_id=previous_doctor_id,
                    assigned_by=u.id,assignment_type='REREVIEW',require_unassigned=True
                )
                _rb.db.session.commit()
                assignment_status='RETURNED_TO_PREVIOUS_DOCTOR'
                _rb.create_ris_notification(
                    o,'READY_FOR_REREVIEW','Your returned case is ready for re-review',
                    f'{ev.reason_code}: {note}','INFO','',user_id=previous_doctor_id
                )
                _rb.db.session.commit()
            except Exception as exc:
                _rb.db.session.rollback()
                _rb.app.logger.warning('Previous-doctor re-review failed order=%s: %s',o.id,exc)
                _offer,assignment_status=_rb.coordinate_post_exam_assignment(
                    o,created_by=u.id,trigger='RETURN_RESOLVED_FALLBACK'
                )
        else:
            _offer,assignment_status=_rb.coordinate_post_exam_assignment(
                o,created_by=u.id,trigger='RETURN_RESOLVED'
            )

        _rb.audit(
            'CASE_READY_FOR_REREVIEW','order',o.id,
            f'reason={ev.reason_code}; assignment_status={assignment_status}; note={note}'
        )
        _rb.db.session.commit()
        _rb.flash(f'Correction resolved; assignment status: {assignment_status}.','success')
        return _rb.redirect(_rb.url_for('returned_cases_queue'))
    return resolve_returned_case


def install_0724(_rb):
    @_rb.app.get('/operations/escalations')
    @_rb.require_perm('orders.view')
    def escalation_board():
        rows=_rb.RISNotification.query.filter(_rb.RISNotification.status=='NEW',_rb.RISNotification.severity.in_(['WARNING','CRITICAL'])).order_by(_rb.RISNotification.created_at).all()
        return _rb.render_template('escalation_board.html',rows=rows)
    return escalation_board


def install_0725(_rb):
    @_rb.app.get('/search/advanced')
    @_rb.login_required
    def advanced_search():
        rows=_rb.advanced_order_query()
        saved=_rb.SavedSearchFilter.query.filter_by(user_id=_rb.current_user().id,page_key='GLOBAL').order_by(_rb.SavedSearchFilter.name).all()
        doctors=_rb.User.query.join(_rb.Role).filter(_rb.Role.code.in_(['RADIOLOGIST','DOCTOR']),_rb.User.active.is_(True)).order_by(_rb.User.full_name).all()
        return _rb.render_template(
          'advanced_search.html',
          rows=rows,
          saved=saved,
          doctors=doctors,
          branches=_rb.Branch.query.filter_by(active=True).order_by(_rb.Branch.name).all(),
          CaseReadiness=_rb.CaseReadiness,
          CaseAssignment=_rb.CaseAssignment,
          Report=_rb.Report
        )
    return advanced_search


def install_0729(_rb):
    @_rb.app.post('/saved-views/<page_key>/save')
    @_rb.login_required
    def saved_view_save(page_key):
        page_key=_rb._saved_view_page_or_404(page_key)
        name=(_rb.request.form.get('view_name') or '').strip()
        if not name:
            _rb.abort(400)

        data=_rb._saved_view_filtered_data(page_key, _rb.request.form)

        row=_rb.SavedSearchFilter(
            user_id=_rb.current_user().id,
            name=name,
            page_key=page_key,
            filter_json=_rb.json.dumps(data,ensure_ascii=False),
            is_default=False
        )
        _rb.db.session.add(row)
        _rb.db.session.commit()

        return _rb.redirect(_rb.url_for(_rb.SAVED_VIEW_PAGES[page_key], **data))
    return saved_view_save


def install_0730(_rb):
    @_rb.app.post('/saved-views/<page_key>/<int:view_id>/update')
    @_rb.login_required
    def saved_view_update(page_key,view_id):
        page_key=_rb._saved_view_page_or_404(page_key)
        row=_rb.SavedSearchFilter.query.filter_by(
            id=view_id,
            user_id=_rb.current_user().id,
            page_key=page_key
        ).first_or_404()
        data=_rb._saved_view_filtered_data(page_key,_rb.request.form)
        name=(_rb.request.form.get('view_name') or '').strip()
        if name:
            row.name=name[:120]
        row.filter_json=_rb.json.dumps(data,ensure_ascii=False)
        _rb.audit('SAVED_VIEW_UPDATE','saved_search_filter',row.id,
              f'page={page_key}; name={row.name}')
        _rb.db.session.commit()
        _rb.flash('Saved view updated.','success')
        return _rb.redirect(_rb.url_for(_rb.SAVED_VIEW_PAGES[page_key],**data))
    return saved_view_update


def install_0731(_rb):
    @_rb.app.get('/saved-views/<page_key>/<int:view_id>/apply')
    @_rb.login_required
    def saved_view_apply(page_key,view_id):
        page_key=_rb._saved_view_page_or_404(page_key)

        row=_rb.SavedSearchFilter.query.filter_by(
            id=view_id,
            user_id=_rb.current_user().id,
            page_key=page_key
        ).first_or_404()

        try:
            data=_rb.json.loads(row.filter_json or '{}')
        except Exception:
            data={}

        data=_rb._saved_view_filtered_data(page_key,data)

        return _rb.redirect(_rb.url_for(_rb.SAVED_VIEW_PAGES[page_key], **data))
    return saved_view_apply


def install_0732(_rb):
    @_rb.app.post('/saved-views/<page_key>/<int:view_id>/default')
    @_rb.login_required
    def saved_view_set_default(page_key,view_id):
        page_key=_rb._saved_view_page_or_404(page_key)

        row=_rb.SavedSearchFilter.query.filter_by(
            id=view_id,
            user_id=_rb.current_user().id,
            page_key=page_key
        ).first_or_404()

        _rb.SavedSearchFilter.query.filter_by(
            user_id=_rb.current_user().id,
            page_key=page_key
        ).update({'is_default':False})

        row.is_default=True
        _rb.db.session.commit()

        return _rb.redirect(_rb.url_for(_rb.SAVED_VIEW_PAGES[page_key]))
    return saved_view_set_default


def install_0733(_rb):
    @_rb.app.post('/saved-views/<page_key>/<int:view_id>/rename')
    @_rb.login_required
    def saved_view_rename(page_key,view_id):
        page_key=_rb._saved_view_page_or_404(page_key)

        row=_rb.SavedSearchFilter.query.filter_by(
            id=view_id,
            user_id=_rb.current_user().id,
            page_key=page_key
        ).first_or_404()

        name=(_rb.request.form.get('view_name') or '').strip()
        if not name:
            _rb.abort(400)

        row.name=name
        _rb.db.session.commit()

        return _rb.redirect(_rb.url_for(_rb.SAVED_VIEW_PAGES[page_key]))
    return saved_view_rename


def install_0734(_rb):
    @_rb.app.post('/saved-views/<page_key>/<int:view_id>/delete')
    @_rb.login_required
    def saved_view_delete(page_key,view_id):
        page_key=_rb._saved_view_page_or_404(page_key)

        row=_rb.SavedSearchFilter.query.filter_by(
            id=view_id,
            user_id=_rb.current_user().id,
            page_key=page_key
        ).first_or_404()

        _rb.db.session.delete(row)
        _rb.db.session.commit()

        return _rb.redirect(_rb.url_for(_rb.SAVED_VIEW_PAGES[page_key]))
    return saved_view_delete


def install_0735(_rb):
    @_rb.app.post('/search/advanced/save')
    @_rb.login_required
    def advanced_search_save():
        name=(_rb.request.form.get('name') or '').strip()
        if not name: _rb.abort(400)
        data={k:v for k,v in _rb.request.form.items() if k not in ('name','csrf_token')}
        if _rb.request.form.getlist('has_priors'): data['has_priors']='1'
        row=_rb.SavedSearchFilter(user_id=_rb.current_user().id,name=name,page_key='GLOBAL',
          filter_json=_rb.json.dumps(data,ensure_ascii=False))
        _rb.db.session.add(row);_rb.db.session.commit()
        return _rb.redirect(_rb.url_for('advanced_search'))
    return advanced_search_save


def install_0736(_rb):
    @_rb.app.get('/search/advanced/saved/<int:filter_id>')
    @_rb.login_required
    def advanced_search_apply_saved(filter_id):
        row=_rb.SavedSearchFilter.query.filter_by(id=filter_id,user_id=_rb.current_user().id).first_or_404()
        data=_rb.json.loads(row.filter_json or '{}')
        return _rb.redirect(_rb.url_for('advanced_search',**data))
    return advanced_search_apply_saved


def install_0767(_rb):
    @_rb.app.route('/studio/shortcuts',methods=['GET','POST'])
    @_rb.require_perm('users.view')
    def studio_shortcuts():
        if _rb.request.method=='POST':
            target=(_rb.request.form.get('target') or '').strip()
            target_type=(_rb.request.form.get('target_type') or 'INTERNAL').upper()
            if not target:
                _rb.flash('Shortcut target is required.','danger')
                return _rb.redirect(_rb.url_for('studio_shortcuts'))
            if target_type=='INTERNAL' and not target.startswith('/'):
                _rb.flash('Internal shortcut must start with /.','danger')
                return _rb.redirect(_rb.url_for('studio_shortcuts'))
            row=_rb.StudioShortcut(
                title_en=(_rb.request.form.get('title_en') or '').strip() or 'Shortcut',
                title_ar=(_rb.request.form.get('title_ar') or '').strip(),
                icon=(_rb.request.form.get('icon') or 'link').strip(),
                accent=(_rb.request.form.get('accent') or 'blue').strip(),
                target_type=target_type,target=target,
                placement=(_rb.request.form.get('placement') or 'DASHBOARD').upper(),
                open_mode=(_rb.request.form.get('open_mode') or 'SAME').upper(),
                size=(_rb.request.form.get('size') or 'MEDIUM').upper(),
                sort_order=_rb.request.form.get('sort_order',type=int) or 100,
                permission_code=(_rb.request.form.get('permission_code') or '').strip(),
                role_code=(_rb.request.form.get('role_code') or '').strip(),
                branch_id=_rb.request.form.get('branch_id',type=int),
                user_id=_rb.request.form.get('user_id',type=int),
                active=_rb.request.form.get('active')=='1',
                created_by=_rb.current_user().id
            )
            _rb.db.session.add(row);_rb.db.session.commit()
            _rb.audit('STUDIO_SHORTCUT_CREATE','studio_shortcut',row.id,row.title_en)
            _rb.flash('Shortcut created.','success')
            return _rb.redirect(_rb.url_for('studio_shortcuts'))
        return _rb.render_template('studio_shortcuts.html',
            rows=_rb.StudioShortcut.query.order_by(_rb.StudioShortcut.placement,_rb.StudioShortcut.sort_order,_rb.StudioShortcut.id).all(),
            icons=_rb.STUDIO_ICON_LIBRARY,
            branches=_rb.Branch.query.filter_by(active=True).order_by(_rb.Branch.name).all(),
            users=_rb.User.query.filter_by(active=True).order_by(_rb.User.full_name).all())
    return studio_shortcuts


def install_0768(_rb):
    @_rb.app.post('/studio/shortcuts/<int:shortcut_id>/toggle')
    @_rb.require_perm('users.view')
    def studio_shortcut_toggle(shortcut_id):
        row=_rb.StudioShortcut.query.get_or_404(shortcut_id)
        row.active=not row.active;_rb.db.session.commit()
        _rb.audit('STUDIO_SHORTCUT_TOGGLE','studio_shortcut',row.id,str(row.active))
        return _rb.redirect(_rb.url_for('studio_shortcuts'))
    return studio_shortcut_toggle


def install_0769(_rb):
    @_rb.app.post('/studio/shortcuts/<int:shortcut_id>/delete')
    @_rb.require_perm('users.view')
    def studio_shortcut_delete(shortcut_id):
        row=_rb.StudioShortcut.query.get_or_404(shortcut_id)
        _rb.audit('STUDIO_SHORTCUT_DELETE','studio_shortcut',row.id,row.title_en)
        _rb.db.session.delete(row);_rb.db.session.commit()
        return _rb.redirect(_rb.url_for('studio_shortcuts'))
    return studio_shortcut_delete


def install_0770(_rb):
    @_rb.app.post('/studio/shortcuts/reorder')
    @_rb.require_perm('users.view')
    def studio_shortcut_reorder():
        ids=_rb.request.form.getlist('shortcut_id')
        for i,raw in enumerate(ids):
            try:
                row=_rb.StudioShortcut.query.get(int(raw))
                if row: row.sort_order=(i+1)*10
            except Exception: pass
        _rb.db.session.commit()
        return _rb.redirect(_rb.url_for('studio_shortcuts'))
    return studio_shortcut_reorder


def install_0772(_rb):
    @_rb.app.context_processor
    def inject_studio_shortcuts():
        return {
            'studio_shortcuts_for': _rb.studio_shortcuts_for,
            'studio_icon_map': _rb.STUDIO_ICON_MAP,
        }
    return inject_studio_shortcuts


def install_0773(_rb):
    @_rb.app.get('/management')
    @_rb.require_perm('orders.view')
    def management_dashboard():
        start,end,start_dt,end_dt=_rb.management_date_range()
        summary=_rb.management_summary(start_dt,end_dt)
        branches={b.id:b for b in _rb.Branch.query.all()}
        referrers={r.id:r for r in _rb.ReferringDoctor.query.all()}
        branch_rows=sorted([{'name':branches.get(k).name if branches.get(k) else f'Branch {k}','count':v} for k,v in summary['branch_counts'].items()],key=lambda x:x['count'],reverse=True)
        modality_rows=sorted([{'name':k,'count':v} for k,v in summary['modality_counts'].items()],key=lambda x:x['count'],reverse=True)
        referrer_rows=sorted([{'id':k,'name':referrers.get(k).name if referrers.get(k) else f'Referrer {k}','count':v} for k,v in summary['referrer_counts'].items()],key=lambda x:x['count'],reverse=True)[:20]
        return _rb.render_template('management_dashboard.html',start=start,end=end,summary=summary,branch_rows=branch_rows,modality_rows=modality_rows,referrer_rows=referrer_rows)
    return management_dashboard


def install_0774(_rb):
    @_rb.app.get('/management/referrals')
    @_rb.require_perm('orders.view')
    def referral_analytics():
        start,end,start_dt,end_dt=_rb.management_date_range()
        groups={}
        for o in _rb.management_orders_query(start_dt,end_dt).filter(_rb.Order.referring_doctor_id.isnot(None)).all():
            rid=o.referring_doctor_id; ref=_rb.ReferringDoctor.query.get(rid)
            g=groups.setdefault(rid,{'name':ref.name if ref else f'Referrer {rid}','cases':0,'revenue':0.0,'commission':0.0,'modalities':{}})
            g['cases']+=1; g['revenue']+=float(getattr(o,'contract_price',0) or getattr(o,'gross_price',0) or 0)
            com,_=_rb.referral_commission_for_order(o); g['commission']+=com
            g['modalities'][o.modality]=g['modalities'].get(o.modality,0)+1
        rows=sorted(groups.values(),key=lambda x:(x['revenue'],x['cases']),reverse=True)
        return _rb.render_template('referral_analytics.html',start=start,end=end,rows=rows)
    return referral_analytics


def install_0812(_rb):
    @_rb.app.get('/analytics/executive')
    @_rb.require_perm('analytics.executive.view')
    def executive_analytics():
        f=_rb.executive_analytics_filters()
        payload=_rb.executive_analytics_payload(f)
        return _rb.render_template('executive_analytics.html',
            f=f,data=payload,
            branches=_rb.Branch.query.filter_by(active=True).order_by(_rb.Branch.name).all(),
            devices=_rb.Device.query.filter_by(active=True).order_by(_rb.Device.name).all(),
            doctors=_rb.User.query.filter_by(active=True).order_by(_rb.User.full_name).all(),
            contracts=_rb.Contract.query.filter_by(active=True).order_by(_rb.Contract.name).all(),
            modalities=sorted({x[0] for x in _rb.db.session.query(_rb.Procedure.modality).filter(_rb.Procedure.active==True).distinct().all() if x[0]})
        )
    return executive_analytics


def install_0813(_rb):
    @_rb.app.get('/operations/command-center')
    @_rb.require_perm('workflow.command.view')
    def workflow_command_center():
        snap=_rb.workflow_command_snapshot()
        return _rb.render_template('workflow_command_center.html',snap=snap)
    return workflow_command_center


def install_0922(_rb):
    @_rb.app.route("/call", methods=["GET"])
    def public_click_to_call():
        return _rb.render_template(
            "public_call.html"
        )
    return public_click_to_call


def install_0945(_rb):
    @_rb.app.get(
        "/staff/public-attachment/"
        "<int:attachment_id>"
    )
    @_rb.login_required
    def staff_public_attachment_view(attachment_id):

        if not _rb._rb_staff_role_allowed():
            _rb.abort(403)

        row = _rb.db.session.execute(
            _rb.db.text("""
            SELECT
                contact_request_id,
                stored_filename,
                original_filename,
                mime_type

            FROM public_contact_attachment

            WHERE id=:id
        """),
            {"id": attachment_id}
        ).mappings().first()

        if not row:
            _rb.abort(404)

        root = _rb._rb_public_attachment_root()

        path = _rb._rb_os.path.realpath(
            _rb._rb_os.path.join(
                root,
                str(row["contact_request_id"]),
                row["stored_filename"]
            )
        )

        safe_root = _rb._rb_os.path.realpath(
            root
        )

        if not path.startswith(
            safe_root + _rb._rb_os.sep
        ):
            _rb.abort(403)

        if not _rb._rb_os.path.isfile(path):
            _rb.abort(404)

        return _rb.send_file(
            path,
            mimetype=(
                row["mime_type"]
                or "application/octet-stream"
            ),
            download_name=
                row["original_filename"],
            as_attachment=False
        )
    return staff_public_attachment_view


def install_0946(_rb):
    @_rb.app.post(
        "/api/staff/attachments/"
        "<int:attachment_id>/verify"
    )
    @_rb.login_required
    def staff_attachment_verify(attachment_id):

        if not _rb._rb_staff_role_allowed():
            _rb.abort(403)

        u = _rb.current_user()

        _rb.db.session.execute(
            _rb.db.text("""
            UPDATE public_contact_attachment
            SET
                verification_status='VERIFIED',
                verified_by_user_id=:uid,
                verified_at=NOW()
            WHERE id=:id
        """),
            {
                "id": attachment_id,
                "uid": u.id,
            }
        )

        _rb.db.session.commit()

        return _rb.jsonify(ok=True)
    return staff_attachment_verify


def install_0947(_rb):
    @_rb.app.post(
        "/api/staff/attachments/"
        "<int:attachment_id>/reject"
    )
    @_rb.login_required
    def staff_attachment_reject(attachment_id):

        if not _rb._rb_staff_role_allowed():
            _rb.abort(403)

        u = _rb.current_user()

        _rb.db.session.execute(
            _rb.db.text("""
            UPDATE public_contact_attachment
            SET
                verification_status='REJECTED',
                rejected_by_user_id=:uid,
                rejected_at=NOW()
            WHERE id=:id
        """),
            {
                "id": attachment_id,
                "uid": u.id,
            }
        )

        _rb.db.session.commit()

        return _rb.jsonify(ok=True)
    return staff_attachment_reject
