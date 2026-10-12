"""Runtime-bound web.components.registration; dependencies are supplied at composition.

Legacy behavior is preserved; new policies belong in the independent domain layer.
"""

def install_0154(_rb):
    @_rb.login_required
    def api_registration_procedures():
        branch_id=_rb.request.args.get('branch_id',type=int)
        if not branch_id:
            return _rb.jsonify({'ok':False,'error':'branch_id required'}),400
        rows=_rb.allowed_procedures_for_branch(branch_id)
        return _rb.jsonify({'ok':True,'procedures':[{
            'id':p.id,'code':p.code,'name':p.name,'name_ar':p.name_ar,
            'modality':p.modality,'duration_min':p.duration_min,'base_price':p.base_price
        } for p in rows]})
    return api_registration_procedures


def install_0317(_rb):
    def render_registration_form(form_data=None,selected_patient=None,duplicate_patients=None,status=200):
        return _rb.render_template(
            _rb.registration_template_for(),
            **_rb.registration_form_context(form_data,selected_patient,duplicate_patients)
        ), status
    return render_registration_form


def install_0318(_rb):
    def registration_validation_error(message,form_data,rollback=False,status=422,duplicate_patients=None):
        if rollback:
            _rb.db.session.rollback()
        _rb.flash(message,'danger')
        return _rb.render_registration_form(
            form_data=form_data,
            selected_patient=_rb.request.form.get('patient',type=int),
            duplicate_patients=duplicate_patients,
            status=status
        )
    return registration_validation_error


def install_0383(_rb):
    def advanced_order_query():
        q=_rb.Order.query.join(_rb.Patient)
        text=(_rb.request.args.get('q') or '').strip()
        if text:
            q=q.filter(_rb.or_(
              _rb.Patient.name.ilike(f'%{text}%'),
              _rb.Patient.patient_id.ilike(f'%{text}%'),
              _rb.Patient.phone.ilike(f'%{text}%'),
              _rb.Patient.national_id.ilike(f'%{text}%'),
              _rb.Order.accession.ilike(f'%{text}%'),
              _rb.Order.procedure.ilike(f'%{text}%')
            ))
        branch_id=_rb.request.args.get('branch_id',type=int)
        modality=(_rb.request.args.get('modality') or '').strip().upper()
        procedure=(_rb.request.args.get('procedure') or '').strip()
        priority=(_rb.request.args.get('priority') or '').strip().upper()
        readiness=(_rb.request.args.get('readiness') or '').strip().upper()
        assignment=(_rb.request.args.get('assignment') or '').strip().upper()
        report_status=(_rb.request.args.get('report_status') or '').strip().upper()
        returned=(_rb.request.args.get('returned') or '')=='1'
        overdue=(_rb.request.args.get('overdue') or '')=='1'
        missing_history=(_rb.request.args.get('missing_history') or '')=='1'
        missing_images=(_rb.request.args.get('missing_images') or '')=='1'
        missing_attachments=(_rb.request.args.get('missing_attachments') or '')=='1'
        has_priors=(_rb.request.args.get('has_priors') or '')=='1'
        has_documents=(_rb.request.args.get('has_documents') or '')=='1'
        doctor_id=_rb.request.args.get('doctor_id',type=int)
        if branch_id: q=q.filter(_rb.Order.branch_id==branch_id)
        if modality: q=q.filter(_rb.Order.modality==modality)
        if procedure: q=q.filter(_rb.Order.procedure.ilike(f'%{procedure}%'))
        if priority: q=q.filter(_rb.Order.priority==priority)
        rows=q.order_by(_rb.Order.id.desc()).limit(1000).all()

        def keep(o):
            r=__import__('reception_readiness').view(o,_rb.CaseReadiness.query.filter_by(order_id=o.id).first())
            ca=_rb.CaseAssignment.query.filter_by(order_id=o.id,active=True).first()
            rp=_rb.Report.query.filter_by(order_id=o.id).order_by(_rb.Report.id.desc()).first()
            events=_rb.CaseWorkflowEvent.query.filter_by(order_id=o.id).all()
            if readiness and (not r or r.status!=readiness): return False
            if assignment=='ASSIGNED' and not ca: return False
            if assignment=='UNASSIGNED' and ca: return False
            if doctor_id and (not ca or ca.doctor_user_id!=doctor_id): return False
            if report_status and (not rp or str(rp.status or '').upper()!=report_status): return False
            if returned and not any(e.event_type=='RETURNED' for e in events): return False
            if missing_history and not (r and r.missing_history): return False
            if missing_images and not (r and r.incomplete_images): return False
            if missing_attachments and not (r and r.missing_attachments): return False
            if has_priors and not (_rb.related_prior_orders(o,1) or _rb.external_priors_for_order(o)): return False
            if has_documents and _rb.PatientDocument.query.filter_by(patient_id=o.patient_id).count()==0: return False
            if overdue and not _rb.case_delay_snapshot(o)['overdue']: return False
            return True
        return [o for o in rows if keep(o)]
    return advanced_order_query


def install_0397(_rb):
    def _intake_redirect(intake_id,section='documents'):
        """PRG redirect that returns staff to the action area instead of page top."""
        section=str(section or 'documents').strip().lower()
        if not _rb.re.fullmatch(r'(documents|identity|visit|matching|commit|document-\d+)',section):
            section='documents'
        return _rb.redirect(_rb.url_for('smart_intake_workspace',intake_id=intake_id)+'#'+section)
    return _intake_redirect


def install_0405(_rb):
    @_rb.require_perm('appointments.manage')
    def api_slots():
        device=_rb.Device.query.get_or_404(_rb.request.args.get('device_id',type=int))
        from registration_policy import require_registration_branch
        require_registration_branch(device.branch_id)
        proc=_rb.Procedure.query.get_or_404(_rb.request.args.get('procedure_id',type=int))
        day_s=_rb.request.args.get('date','')
        try:
            day=_rb.datetime.fromisoformat(day_s).date()
        except Exception:
            _rb.abort(400)
        return _rb.jsonify({'slots':[{
            'start':x['start'].isoformat(timespec='minutes'),
            'end':x['end'].isoformat(timespec='minutes'),
            'label':x['label'],
            'available':x['available']
        } for x in _rb.generate_slots(device,proc,day)]})
    return api_slots


def install_0408(_rb):
    def _rb_v5462_allow_registration():
        if not _rb.current_user():
            _rb.abort(401)
        if not (_rb.has_perm('*') or _rb.has_perm('orders.create') or _rb.has_perm('appointments.manage')):
            _rb.abort(403)
    return _rb_v5462_allow_registration


def install_0433(_rb):
    @_rb.require_perm('appointments.view')
    def api_booking_procedures():
        branch_id=_rb.request.args.get('branch_id',type=int)
        device_id=_rb.request.args.get('device_id',type=int)
        if not branch_id:
            return _rb.jsonify({'ok':False,'error':'branch_id required'}),400

        modality=''
        if device_id:
            device=_rb.Device.query.get_or_404(device_id)
            if device.branch_id!=branch_id:
                return _rb.jsonify({'ok':False,'error':'device/branch mismatch'}),400
            modality=device.modality or ''

        rows=_rb.allowed_procedures_for_branch(branch_id,modality)
        return _rb.jsonify({'ok':True,'procedures':[{
            'id':p.id,'code':p.code,'name':p.name,'name_ar':p.name_ar,
            'modality':p.modality,'duration_min':p.duration_min
        } for p in rows]})
    return api_booking_procedures


def install_0754(_rb):
    def _block_intake_registration(intake,status,message,reason_code):
        intake.status=status
        _rb.audit('SMART_INTAKE_COMMIT_BLOCKED','smart_intake_session',intake.id,
          f'reason={reason_code} status={status}')
        _rb.db.session.commit();_rb.flash(message,'danger')
        return _rb._intake_redirect(intake.id,'commit')
    return _block_intake_registration


def install_0846(_rb):
    def queue_external_intake(row,actor_user_id):
        if row.status not in ('RECEIVED','HOLD'):
            return None,'INTAKE_NOT_REVIEWABLE'
        setting=_rb.external_reporting_setting()
        center=row.center
        inbox=row.inbox
        if not setting.enabled:
            return None,'EXTERNAL_REPORTING_DISABLED'
        if not center.active or not center.receiving_enabled or not center.assignment_enabled:
            return None,'CENTER_NOT_ENABLED'
        pool=_rb.ExternalCenterDoctor.query.filter_by(center_id=center.id,active=True).count()
        if pool<1:
            return None,'DOCTOR_POOL_EMPTY'
        if not inbox.study_instance_uid or not inbox.orthanc_study_id or int(inbox.image_count or 0)<1:
            return None,'STUDY_NOT_READY'
        verification=_rb.external_intake_demographic_verification(row)
        if verification['status']=='BLOCKED':
            return None,'DEMOGRAPHICS_BLOCKED'
        if verification['status']=='REVIEW_REQUIRED' and not (
            not verification['source_error'] and
            row.demographic_override_approved and
            row.demographic_override_facts_sha256==verification['facts_sha256']
        ):
            return None,'DEMOGRAPHICS_REVIEW_REQUIRED'
        if verification['status'] not in ('MATCHED','REVIEW_REQUIRED'):
            return None,'DEMOGRAPHICS_NOT_VERIFIED'
        intake_attachments=_rb.Attachment.query.filter_by(external_intake_id=row.id).all()
        if center.required_documents and not intake_attachments:
            return None,'REQUIRED_DOCUMENTS_MISSING'
        if center.billing_enabled and not center.billing_contract_id:
            return None,'CENTER_BILLING_CONTRACT_REQUIRED'

        branch=_rb.Branch.query.filter_by(active=True).order_by(_rb.Branch.id).first()
        if not branch:
            return None,'ACTIVE_BRANCH_REQUIRED'
        patient=_rb.Patient(
            patient_id=_rb._external_intake_local_patient_id(row),
            name=(str(row.expected_patient_name or '').strip()
                  or (inbox.pacs_patient_name or '').replace('^',' ').strip()
                  or 'External patient')[:120],
            dob=_rb.normalize_date(row.expected_dob),sex=(row.expected_sex or '')[:1],phone='',
            worklist_name=f'EXTERNAL:{center.code}:{center.name}'[:180]
        )
        _rb.db.session.add(patient);_rb.db.session.flush()
        local_accession=_rb._external_intake_generated_accession(row)
        description=(
            f'External - {center.name} - '
            f'{inbox.study_description or "Reporting study"}'
        )[:120]
        report_fee=max(0.0,float(center.default_report_fee or 0)) if center.billing_enabled else 0.0
        order=_rb.Order(
            accession=local_accession,patient_id=patient.id,
            modality=(inbox.modality or 'OT').split('\\')[0].strip().upper()[:8] or 'OT',
            procedure=description,
            station_ae=(inbox.source_ae or '')[:40],scheduled=inbox.first_seen_at or _rb.datetime.utcnow(),
            status='IMAGES_RECEIVED',branch_id=branch.id,priority=center.default_priority,
            contract_id=(center.billing_contract_id if center.billing_enabled else None),
            gross_price=report_fee,contract_price=report_fee,
            patient_share=0,company_share=report_fee,paid_amount=0,
            created_by=actor_user_id,created_at=_rb.datetime.utcnow(),exam_status='EXAM_COMPLETED',
            exam_completed_at=_rb.datetime.utcnow(),pacs_image_count=int(inbox.image_count or 0),
            pacs_status='IMAGES_COMPLETE',pacs_last_seen_at=inbox.last_seen_at or _rb.datetime.utcnow(),
            pacs_last_change_at=inbox.last_seen_at or _rb.datetime.utcnow(),
            pacs_study_id=inbox.orthanc_study_id,study_instance_uid=inbox.study_instance_uid
        )
        _rb.db.session.add(order);_rb.db.session.flush()
        for attachment in intake_attachments:
            attachment.patient_id=patient.id
            attachment.order_id=order.id
        row.order_id=order.id;row.status='QUEUED';row.reviewed_by=actor_user_id
        row.reviewed_at=_rb.datetime.utcnow();row.queued_at=row.reviewed_at
        inbox.order_id=order.id;inbox.state='EXTERNAL_QUEUED'
        _rb.db.session.add(_rb.AuditLog(
            user_id=actor_user_id,username=_rb.current_user().username,
            action='EXTERNAL_INTAKE_QUEUE',entity='external_intake_case',entity_id=str(row.id),
            details=(f'center={center.code};order={order.id};study={inbox.orthanc_study_id};'
                     f'billing={center.billing_enabled};fee={report_fee};documents={len(intake_attachments)}'),
            ip=_rb.request.remote_addr or ''
        ))
        _rb.db.session.commit()
        offer,status=_rb.offer_next_doctor(order,created_by=actor_user_id)
        return offer,status
    return queue_external_intake

