"""Runtime-bound web.routes.communications; dependencies are supplied at composition.

Legacy behavior is preserved; new policies belong in the independent domain layer.
"""

def install_0175(_rb):
    @_rb.app.route('/admin/notifications')
    @_rb.require_perm('audit.view')
    def admin_notifications():
        return _rb.render_template('admin_notifications.html',rows=_rb.NotificationEvent.query.order_by(_rb.NotificationEvent.id.desc()).limit(300).all())
    return admin_notifications


def install_0176(_rb):
    @_rb.app.post('/admin/notifications/process')
    @_rb.require_perm('audit.view')
    def admin_notifications_process():
        count=_rb.process_notification_queue()
        _rb.flash(f'Processed {count} notification job(s).','success')
        return _rb.redirect(_rb.url_for('admin_notifications'))
    return admin_notifications_process


def install_0177(_rb):
    @_rb.app.post('/admin/notifications/<int:notification_id>/retry')
    @_rb.require_perm('audit.view')
    def admin_notification_retry(notification_id):
        row=_rb.NotificationEvent.query.get_or_404(notification_id)
        row.status='PENDING'
        row.last_error=''
        _rb.db.session.commit()
        _rb.flash('Notification queued for retry.','success')
        return _rb.redirect(_rb.url_for('admin_notifications'))
    return admin_notification_retry


def install_0448(_rb):
    @_rb.app.get('/chat')
    @_rb.login_required
    def chat_home():
        ms=_rb.ChatThreadMember.query.filter_by(user_id=_rb.current_user().id).all();threads=[m.thread for m in ms if m.thread and m.thread.active];threads.sort(key=lambda x:x.created_at,reverse=True)
        users=_rb.User.query.filter(_rb.User.active.is_(True),_rb.User.id!=_rb.current_user().id).order_by(_rb.User.full_name).all()
        return _rb.render_template('chat_home.html',threads=threads,users=users)
    return chat_home


def install_0449(_rb):
    @_rb.app.post('/chat/direct')
    @_rb.login_required
    def chat_direct_create():
        uid=_rb.request.form.get('user_id',type=int)
        if not uid or uid==_rb.current_user().id:_rb.abort(400)
        other=_rb.User.query.get_or_404(uid);mine={m.thread_id for m in _rb.ChatThreadMember.query.filter_by(user_id=_rb.current_user().id).all()};theirs={m.thread_id for m in _rb.ChatThreadMember.query.filter_by(user_id=uid).all()}
        thread=_rb.ChatThread.query.filter(_rb.ChatThread.id.in_(mine & theirs),_rb.ChatThread.thread_type=='DIRECT',_rb.ChatThread.active.is_(True)).first() if mine & theirs else None
        if not thread:
            thread=_rb.ChatThread(thread_type='DIRECT',title=f'{_rb.current_user().full_name or _rb.current_user().username} / {other.full_name or other.username}',created_by=_rb.current_user().id);_rb.db.session.add(thread);_rb.db.session.flush();_rb.ensure_chat_member(thread,_rb.current_user().id);_rb.ensure_chat_member(thread,uid);_rb.db.session.commit()
        return _rb.redirect(_rb.url_for('chat_thread',thread_id=thread.id))
    return chat_direct_create


def install_0450(_rb):
    @_rb.app.post('/chat/group')
    @_rb.login_required
    def chat_group_create():
        title=(_rb.request.form.get('title') or '').strip();ids=[int(x) for x in _rb.request.form.getlist('user_ids') if str(x).isdigit()]
        if not title:return _rb.redirect(_rb.url_for('chat_home'))
        thread=_rb.ChatThread(thread_type='GROUP',title=title,created_by=_rb.current_user().id);_rb.db.session.add(thread);_rb.db.session.flush();_rb.ensure_chat_member(thread,_rb.current_user().id)
        for uid in ids:_rb.ensure_chat_member(thread,uid)
        _rb.db.session.commit();return _rb.redirect(_rb.url_for('chat_thread',thread_id=thread.id))
    return chat_group_create


def install_0451(_rb):
    @_rb.app.get('/chat/case/<int:order_id>')
    @_rb.login_required
    def chat_case(order_id):
        thread=_rb.get_or_create_case_thread(_rb.Order.query.get_or_404(order_id));_rb.ensure_chat_member(thread,_rb.current_user().id);_rb.db.session.commit();return _rb.redirect(_rb.url_for('chat_thread',thread_id=thread.id))
    return chat_case


def install_0452(_rb):
    @_rb.app.route('/chat/<int:thread_id>',methods=['GET','POST'])
    @_rb.login_required
    def chat_thread(thread_id):
        thread=_rb.ChatThread.query.get_or_404(thread_id);member=_rb.ChatThreadMember.query.filter_by(thread_id=thread.id,user_id=_rb.current_user().id).first()
        if not member:_rb.abort(403)
        if _rb.request.method=='POST':
            body=(_rb.request.form.get('body') or '').strip();f=_rb.request.files.get('attachment');path=name=''
            if f and f.filename:
                ext=_rb.os.path.splitext(f.filename)[1].lower()
                if ext not in ('.pdf','.jpg','.jpeg','.png','.doc','.docx','.txt'):_rb.abort(400)
                folder=_rb.os.path.join(_rb.ATTACHMENT_DIR,'chat',str(thread.id));_rb.os.makedirs(folder,exist_ok=True);safe=_rb.re.sub(r'[^A-Za-z0-9._-]','_',f.filename);path=_rb.os.path.join(folder,f'{int(_rb.datetime.utcnow().timestamp())}_{safe}');f.save(path);name=f.filename
            if body or path:_rb.db.session.add(_rb.ChatMessage(thread_id=thread.id,sender_id=_rb.current_user().id,body=body or '[Attachment]',attachment_path=path,attachment_name=name));member.last_read_at=_rb.datetime.utcnow();_rb.db.session.commit()
            return _rb.redirect(_rb.url_for('chat_thread',thread_id=thread.id))
        member.last_read_at=_rb.datetime.utcnow();_rb.db.session.commit();msgs=_rb.ChatMessage.query.filter_by(thread_id=thread.id).filter(_rb.ChatMessage.deleted_at.is_(None)).order_by(_rb.ChatMessage.created_at).limit(500).all()
        return _rb.render_template('chat_thread.html',thread=thread,messages=msgs)
    return chat_thread


def install_0458(_rb):
    @_rb.app.post('/api/telephony/incoming')
    def telephony_incoming():
        # Intended for trusted PBX/reverse-proxy integration.
        data=_rb.request.get_json(silent=True) or _rb.request.form
        caller=(data.get('caller') or data.get('caller_number') or '').strip()
        extension=(data.get('extension') or '').strip()
        external=(data.get('call_id') or '').strip()
        patient=_rb.patient_by_phone(caller)
        ext=_rb.TelephonyExtension.query.filter_by(extension=extension,active=True).first() if extension else None
        row=_rb.CallLog(
          direction='INBOUND',caller_number=caller,extension=extension,
          patient_id=(patient.id if patient else None),
          user_id=(ext.user_id if ext else None),external_call_id=external,status='RINGING'
        )
        _rb.db.session.add(row);_rb.db.session.commit()
        return _rb.jsonify({'ok':True,'call_id':row.id,'patient_id':row.patient_id,'matched':bool(patient)})
    return telephony_incoming


def install_0459(_rb):
    @_rb.app.get('/telephony/calls')
    @_rb.login_required
    def telephony_calls():
        calls=_rb.CallLog.query.order_by(_rb.CallLog.started_at.desc()).limit(300).all()
        return _rb.render_template('telephony_calls.html',calls=calls)
    return telephony_calls


def install_0460(_rb):
    @_rb.app.get('/telephony/caller/<int:call_id>')
    @_rb.login_required
    def telephony_caller(call_id):
        call=_rb.CallLog.query.get_or_404(call_id)
        patient=call.patient
        orders=_rb.Order.query.filter_by(patient_id=patient.id).order_by(_rb.Order.id.desc()).limit(20).all() if patient else []
        docs=_rb.PatientDocument.query.filter_by(patient_id=patient.id).order_by(_rb.PatientDocument.created_at.desc()).limit(20).all() if patient else []
        return _rb.render_template('telephony_caller.html',call=call,patient=patient,orders=orders,documents=docs)
    return telephony_caller


def install_0461(_rb):
    @_rb.app.post('/telephony/calls/<int:call_id>/notes')
    @_rb.login_required
    def telephony_call_notes(call_id):
        call=_rb.CallLog.query.get_or_404(call_id)
        call.notes=(_rb.request.form.get('notes') or '').strip()
        if not call.patient_id:
            pid=_rb.request.form.get('patient_id',type=int)
            if pid: call.patient_id=pid
        _rb.db.session.commit()
        return _rb.redirect(_rb.url_for('telephony_caller',call_id=call.id))
    return telephony_call_notes


def install_0670(_rb):
    @_rb.app.route('/admin/communications',methods=['GET','POST'])
    @_rb.require_perm('users.view')
    def admin_communications():
        if _rb.request.method=='POST':
            ch=(_rb.request.form.get('channel') or '').upper()
            row=_rb.CommunicationChannelSetting.query.filter_by(channel=ch).first_or_404()
            row.enabled=_rb.request.form.get('enabled')=='1'
            row.provider=(_rb.request.form.get('provider') or '').strip()
            row.base_url=(_rb.request.form.get('base_url') or '').strip()
            row.sender=(_rb.request.form.get('sender') or '').strip()
            row.smtp_host=(_rb.request.form.get('smtp_host') or '').strip()
            row.smtp_port=_rb.request.form.get('smtp_port',type=int) or 587
            row.smtp_tls=_rb.request.form.get('smtp_tls')=='1'
            row.smtp_user=(_rb.request.form.get('smtp_user') or '').strip()
            row.secret_env_name=(_rb.request.form.get('secret_env_name') or '').strip()
            row.updated_by=_rb.current_user().id
            _rb.db.session.commit()
            _rb.flash('Communication settings saved.','success')
            return _rb.redirect(_rb.url_for('admin_communications'))
        return _rb.render_template('admin_communications.html',
            rows=_rb.CommunicationChannelSetting.query.order_by(_rb.CommunicationChannelSetting.channel).all(),
            templates=_rb.CommunicationTemplate.query.order_by(_rb.CommunicationTemplate.code).all())
    return admin_communications


def install_0671(_rb):
    @_rb.app.route('/admin/communication-templates',methods=['POST'])
    @_rb.require_perm('users.view')
    def admin_communication_template_save():
        tid=_rb.request.form.get('template_id',type=int)
        row=_rb.CommunicationTemplate.query.get(tid) if tid else None
        if not row:
            row=_rb.CommunicationTemplate(code=(_rb.request.form.get('code') or '').strip().upper(),name_en='')
            _rb.db.session.add(row)
        row.name_en=(_rb.request.form.get('name_en') or '').strip()
        row.name_ar=(_rb.request.form.get('name_ar') or '').strip()
        row.channel=(_rb.request.form.get('channel') or 'ANY').upper()
        row.event_key=(_rb.request.form.get('event_key') or '').strip().upper()
        row.subject_template=(_rb.request.form.get('subject_template') or '').strip()
        row.body_template=(_rb.request.form.get('body_template') or '').strip()
        row.active=_rb.request.form.get('active')=='1'
        row.created_by=row.created_by or _rb.current_user().id
        _rb.db.session.commit()
        return _rb.redirect(_rb.url_for('admin_communications'))
    return admin_communication_template_save


def install_0672(_rb):
    @_rb.app.route('/patients/<int:patient_id>/communications',methods=['GET','POST'])
    @_rb.login_required
    def patient_communications(patient_id):
        patient=_rb.Patient.query.get_or_404(patient_id)
        if _rb.request.method=='POST':
            channel=(_rb.request.form.get('channel') or '').upper()
            order=_rb.Order.query.get(_rb.request.form.get('order_id',type=int)) if _rb.request.form.get('order_id',type=int) else None
            receipt=_rb.Receipt.query.get(_rb.request.form.get('receipt_id',type=int)) if _rb.request.form.get('receipt_id',type=int) else None
            code=(_rb.request.form.get('template_code') or '').strip().upper()
            tpl=_rb.CommunicationTemplate.query.filter_by(code=code,active=True).first() if code else None
            ctx=_rb.communication_context(patient,order,receipt,{'document_name':_rb.request.form.get('document_name','')})
            subject=_rb.render_comm_text(tpl.subject_template if tpl else _rb.request.form.get('subject',''),ctx)
            body=_rb.render_comm_text(tpl.body_template if tpl else _rb.request.form.get('body',''),ctx)
            recipient=(_rb.request.form.get('recipient') or _rb.patient_default_recipient(patient,channel)).strip()
            if not recipient or not body:
                _rb.flash('Recipient and message are required.','danger')
                return _rb.redirect(_rb.request.url)
            row=_rb.PatientCommunication(
                patient_id=patient.id,order_id=(order.id if order else None),
                receipt_id=(receipt.id if receipt else None),channel=channel,
                recipient=recipient,template_code=code,subject=subject,body=body,
                created_by=_rb.current_user().id,status='PENDING'
            )
            _rb.db.session.add(row);_rb.db.session.commit()
            ok,error=_rb.send_patient_communication(row)
            _rb.audit('PATIENT_COMMUNICATION','patient',patient.id,f'{channel}:{row.status}')
            _rb.flash('Message sent.' if ok else 'Message failed: '+error,'success' if ok else 'danger')
            return _rb.redirect(_rb.url_for('patient_communications',patient_id=patient.id))
        rows=_rb.PatientCommunication.query.filter_by(patient_id=patient.id).order_by(_rb.PatientCommunication.created_at.desc()).limit(300).all()
        templates=_rb.CommunicationTemplate.query.filter_by(active=True).order_by(_rb.CommunicationTemplate.name_en).all()
        orders=_rb.Order.query.filter_by(patient_id=patient.id).order_by(_rb.Order.id.desc()).limit(50).all()
        return _rb.render_template('patient_communications.html',patient=patient,rows=rows,templates=templates,orders=orders)
    return patient_communications


def install_0673(_rb):
    @_rb.app.post('/communications/<int:comm_id>/retry')
    @_rb.login_required
    def communication_retry(comm_id):
        row=_rb.PatientCommunication.query.get_or_404(comm_id)
        ok,error=_rb.send_patient_communication(row)
        _rb.flash('Message sent.' if ok else 'Message failed: '+error,'success' if ok else 'danger')
        return _rb.redirect(_rb.request.referrer or _rb.url_for('patient_communications',patient_id=row.patient_id))
    return communication_retry


def install_0722(_rb):
    @_rb.app.get('/notifications')
    @_rb.login_required
    def notification_center():
        u=_rb.current_user();role=(u.role.code if u.role else '')
        rows=_rb.RISNotification.query.filter(_rb.or_(_rb.RISNotification.user_id==u.id,_rb.RISNotification.role_code==role)).order_by(_rb.RISNotification.created_at.desc()).limit(200).all()
        return _rb.render_template('notification_center.html',rows=rows)
    return notification_center


def install_0723(_rb):
    @_rb.app.post('/notifications/<int:notification_id>/ack')
    @_rb.login_required
    def notification_ack(notification_id):
        n=_rb.RISNotification.query.get_or_404(notification_id)
        n.status='ACKNOWLEDGED';n.acknowledged_at=_rb.datetime.utcnow();n.acknowledged_by=_rb.current_user().id
        _rb.db.session.commit();return _rb.redirect(_rb.request.referrer or _rb.url_for('notification_center'))
    return notification_ack


def install_0907(_rb):
    @_rb.app.route("/api/voice/patient/search", methods=["GET"])
    def voice_api_patient_search():
        if not _rb._voice_api_authorized():
            return _rb._voice_api_unauthorized()

        phone = (_rb.request.args.get("phone") or "").strip()

        if not phone:
            return _rb.jsonify(
                ok=False,
                error="PHONE_REQUIRED"
            ), 400

        patient = _rb.patient_by_phone(phone)

        if not patient:
            return _rb.jsonify(
                ok=True,
                found=False
            )

        return _rb.jsonify(
            ok=True,
            found=True,
            patient={
                "id": patient.id,
                "patient_id": patient.patient_id,
                "name": patient.name,
                "phone": patient.phone,
                "dob": patient.dob,
                "sex": patient.sex,
            }
        )
    return voice_api_patient_search


def install_0908(_rb):
    @_rb.app.route("/api/voice/patient", methods=["POST"])
    def voice_api_patient_create():
        if not _rb._voice_api_authorized():
            return _rb._voice_api_unauthorized()

        data = _rb.request.get_json(silent=True) or {}

        name = str(data.get("name") or "").strip()
        phone = str(data.get("phone") or "").strip()

        if not name:
            return _rb.jsonify(
                ok=False,
                error="PATIENT_NAME_REQUIRED"
            ), 400

        if not phone:
            return _rb.jsonify(
                ok=False,
                error="PHONE_REQUIRED"
            ), 400

        existing = _rb.patient_by_phone(phone)

        if existing:
            return _rb.jsonify(
                ok=True,
                created=False,
                duplicate=True,
                patient={
                    "id": existing.id,
                    "patient_id": existing.patient_id,
                    "name": existing.name,
                    "phone": existing.phone,
                }
            )

        patient = _rb.Patient(
            patient_id="TMP-" + _rb.secrets.token_hex(8),
            name=name,
            dob=str(data.get("dob") or "")
                .replace("-", ""),
            sex=str(data.get("sex") or "").strip(),
            phone=phone,
            national_id=str(
                data.get("national_id") or ""
            ).strip(),
            address=str(
                data.get("address") or ""
            ).strip(),
            email=str(
                data.get("email") or ""
            ).strip(),
            worklist_name=_rb.arabic_to_latin_name(name),
        )

        from registration_policy import validate_patient_fields
        try:
            validate_patient_fields(dict(name=patient.name,phone=patient.phone,dob=patient.dob,sex=patient.sex,
                national_id=patient.national_id,address=patient.address,email=patient.email,
                nationality=str(data.get('nationality') or '').strip()))
        except ValueError as exc:
            return _rb.jsonify(ok=False,error=str(exc)),422
        _rb.db.session.add(patient)
        _rb.db.session.flush()

        patient.patient_id = _rb.generate_patient_id(patient)

        _rb.audit(
            "PATIENT_CREATE_FROM_VOICE",
            "patient",
            patient.id,
            patient.patient_id
        )

        _rb.db.session.commit()

        return _rb.jsonify(
            ok=True,
            created=True,
            patient={
                "id": patient.id,
                "patient_id": patient.patient_id,
                "name": patient.name,
                "phone": patient.phone,
            }
        ), 201
    return voice_api_patient_create


def install_0909(_rb):
    @_rb.app.route("/api/voice/inquiry", methods=["GET"])
    def voice_api_inquiry():

        if not _rb._voice_api_authorized():
            return _rb._voice_api_unauthorized()

        phone = (_rb.request.args.get("phone") or "").strip()

        if not phone:
            return _rb.jsonify(
                ok=False,
                error="PHONE_REQUIRED"
            ), 400

        patient = _rb.patient_by_phone(phone)

        if not patient:
            return _rb.jsonify(
                ok=True,
                found=False,
                patient=None,
                orders=[]
            )

        orders = (
            _rb.Order.query
            .filter_by(patient_id=patient.id)
            .order_by(
                _rb.Order.scheduled.desc(),
                _rb.Order.id.desc()
            )
            .limit(10)
            .all()
        )

        result = []

        for order in orders:

            report = (
                _rb.Report.query
                .filter_by(order_id=order.id)
                .order_by(_rb.Report.id.desc())
                .first()
            )

            exam_status = (
                order.exam_status or
                order.status or
                "UNKNOWN"
            ).upper()

            pacs_status = (
                order.pacs_status or
                "WAITING"
            ).upper()

            report_status = (
                report.status
                if report else "UNREPORTED"
            )

            report_status = (
                report_status or "UNREPORTED"
            ).upper()

            exam_complete = bool(
                order.exam_completed_at
                or exam_status in (
                    "EXAM_COMPLETED",
                    "COMPLETED",
                    "DONE",
                    "FINAL",
                    "REPORTED"
                )
            )

            images_received = bool(
                (order.pacs_image_count or 0) > 0
                or pacs_status in (
                    "RECEIVED",
                    "COMPLETE",
                    "COMPLETED"
                )
            )

            report_ready = bool(
                report and
                report_status == "FINAL"
            )

            result.append({
                "order_id": order.id,
                "accession": order.accession,

                "procedure": order.procedure,
                "modality": order.modality,

                "scheduled": (
                    order.scheduled.isoformat(sep=" ")
                    if order.scheduled else None
                ),

                "branch": (
                    order.branch.name
                    if order.branch else None
                ),

                "exam_status": exam_status,

                "exam_complete": exam_complete,

                "exam_completed_at": (
                    order.exam_completed_at.isoformat(sep=" ")
                    if order.exam_completed_at else None
                ),

                "pacs_status": pacs_status,

                "pacs_image_count":
                    order.pacs_image_count or 0,

                "images_received": images_received,

                "report_status": report_status,

                "report_ready": report_ready,

                "report_finalized_at": (
                    report.finalized_at.isoformat(sep=" ")
                    if report and report.finalized_at
                    else None
                ),

                "report_delivered":
                    bool(order.report_delivered),

                "images_delivered":
                    bool(order.images_delivered)
            })

        return _rb.jsonify(
            ok=True,
            found=True,
            patient={
                "id": patient.id,
                "patient_id": patient.patient_id,
                "name": patient.name,
                "phone": patient.phone
            },
            orders=result
        )
    return voice_api_inquiry


def install_0911(_rb):
    @_rb.app.route("/api/voice/book", methods=["POST"])
    def voice_api_book():
        if not _rb._voice_api_authorized():
            return _rb._voice_api_unauthorized()

        data = _rb.request.get_json(silent=True) or {}

        # The gateway must obtain explicit caller
        # confirmation before sending confirmed=true.
        if data.get("confirmed") is not True:
            return _rb.jsonify(
                ok=False,
                error="EXPLICIT_CONFIRMATION_REQUIRED"
            ), 409

        try:
            patient_id = int(data["patient_id"])
            branch_id = int(data["branch_id"])
            procedure_id = int(data["procedure_id"])
            device_id = int(data["device_id"])

            scheduled = _rb.datetime.fromisoformat(
                str(data["scheduled"])
            )
        except (
            KeyError,
            TypeError,
            ValueError
        ):
            return _rb.jsonify(
                ok=False,
                error="INVALID_BOOKING_DATA"
            ), 400

        patient = _rb.db.session.get(
            _rb.Patient,
            patient_id
        )

        branch = _rb.db.session.get(
            _rb.Branch,
            branch_id
        )

        procedure = _rb.db.session.get(
            _rb.Procedure,
            procedure_id
        )

        device = _rb.db.session.get(
            _rb.Device,
            device_id
        )

        if not all([
            patient,
            branch,
            procedure,
            device
        ]):
            return _rb.jsonify(
                ok=False,
                error="BOOKING_REFERENCE_NOT_FOUND"
            ), 404

        duration = max(
            5,
            int(procedure.duration_min or 20)
        )

        reason = _rb.booking_restriction_reason(
            branch,
            procedure,
            device,
            scheduled,
            duration
        )

        if reason:
            return _rb.jsonify(
                ok=False,
                error="BOOKING_NOT_AVAILABLE",
                reason=reason
            ), 409

        duplicate = (
            _rb.Appointment.query
            .filter_by(
                patient_id=patient.id,
                procedure_id=procedure.id,
                scheduled=scheduled
            )
            .filter(
                _rb.Appointment.status != "CANCELLED"
            )
            .first()
        )

        if duplicate:
            return _rb.jsonify(
                ok=False,
                error="DUPLICATE_APPOINTMENT",
                appointment_id=duplicate.id
            ), 409

        appointment = _rb.Appointment(
            patient_id=patient.id,
            branch_id=branch.id,
            procedure_id=procedure.id,
            device_id=device.id,
            scheduled=scheduled,
            status="BOOKED",
            source="VOICE_AI",
            duration_min=duration,
            priority="NORMAL",
            waiting_list=False,
            notes=str(
                data.get("notes") or ""
            ).strip(),
            created_by=None,
        )

        _rb.db.session.add(appointment)
        _rb.db.session.flush()

        _rb.audit(
            "APPOINTMENT_CREATE_VOICE",
            "appointment",
            appointment.id,
            (
                f"{patient.patient_id} "
                f"{procedure.code} "
                f"{scheduled.isoformat()}"
            )
        )

        _rb.db.session.commit()

        return _rb.jsonify(
            ok=True,
            appointment={
                "id": appointment.id,
                "patient_id": patient.patient_id,
                "patient": patient.name,
                "procedure_id": procedure.id,
                "procedure":
                    procedure.name_ar
                    or procedure.name,
                "branch_id": branch.id,
                "branch": branch.name,
                "device_id": device.id,
                "device": device.name,
                "scheduled":
                    appointment.scheduled.isoformat(),
                "duration_min": duration,
                "status": appointment.status,
                "source": appointment.source,
            }
        ), 201
    return voice_api_book


def install_0912(_rb):
    @_rb.app.get("/voice-intake/review")
    @_rb.login_required
    def voice_intake_review():

        selected_status = (
            _rb.request.args.get("status")
            or "PENDING"
        ).upper()

        allowed = {
            "PENDING",
            "REVIEWED",
            "CONVERTED",
            "CANCELLED",
        }

        if selected_status not in allowed:
            selected_status = "PENDING"

        rows = _rb.db.session.execute(
            _rb.db.text("""
            SELECT
                v.id,
                v.reference,
                v.status,
                v.branch_id,
                v.source,
                v.reason,
                v.phone_text,
                v.patient_name_text,
                v.procedure_text,
                v.notes,
                v.transcript,
                v.audio_path,
                v.audio_mime,
                v.created_at,
                b.name AS branch_name
            FROM voice_intake_review v
            LEFT JOIN branch b
                ON b.id = v.branch_id
            WHERE v.status = :status
            ORDER BY v.created_at ASC
            LIMIT 500
        """),
            {"status": selected_status}
        ).mappings().all()

        return _rb.render_template(
            "voice_intake_review.html",
            rows=rows,
            selected_status=selected_status
        )
    return voice_intake_review


def install_0913(_rb):
    @_rb.app.get("/voice-intake/<int:intake_id>/audio")
    @_rb.login_required
    def voice_intake_audio(intake_id):

        row = _rb.db.session.execute(
            _rb.db.text("""
            SELECT
                reference,
                audio_path,
                audio_mime
            FROM voice_intake_review
            WHERE id = :id
        """),
            {"id": intake_id}
        ).mappings().first()

        if not row:
            _rb.abort(404)

        stored_path = row["audio_path"] or ""

        prefix = "/data/voice-intake/"

        if stored_path.startswith(prefix):
            stored_path = _rb.os.path.join(
                _rb.VOICE_INTAKE_STORAGE,
                stored_path[len(prefix):]
            )

        root = _rb.os.path.realpath(
            _rb.VOICE_INTAKE_STORAGE
        )

        real_path = _rb.os.path.realpath(
            stored_path
        )

        if not real_path.startswith(
            root + _rb.os.sep
        ):
            _rb.abort(403)

        if not _rb.os.path.isfile(real_path):
            _rb.abort(404)

        return _rb.send_file(
            real_path,
            mimetype=row["audio_mime"] or "audio/wav",
            as_attachment=False,
            conditional=True
        )
    return voice_intake_audio


def install_0914(_rb):
    @_rb.app.post("/voice-intake/<int:intake_id>/status")
    @_rb.login_required
    def voice_intake_status(intake_id):

        action = (
            _rb.request.form.get("action")
            or ""
        ).upper()

        mapping = {
            "REVIEW": "REVIEWED",
            "CANCEL": "CANCELLED",
            "REOPEN": "PENDING",
        }

        new_status = mapping.get(action)

        if not new_status:
            _rb.abort(400)

        row = _rb.db.session.execute(
            _rb.db.text("""
            UPDATE voice_intake_review
               SET status = :status
             WHERE id = :id
         RETURNING reference
        """),
            {
                "status": new_status,
                "id": intake_id
            }
        ).mappings().first()

        if not row:
            _rb.abort(404)

        _rb.db.session.commit()

        _rb.flash(
            f'Voice request {row["reference"]} updated.',
            "success"
        )

        return _rb.redirect(
            _rb.request.referrer
            or _rb.url_for("voice_intake_review")
        )
    return voice_intake_status


def install_0915(_rb):
    @_rb.app.post("/voice-intake/<int:intake_id>/caller-control")
    @_rb.login_required
    def voice_intake_caller_control(intake_id):

        action = (
            _rb.request.form.get("action")
            or ""
        ).upper()

        allowed = {
            "SPAM",
            "BLOCK",
            "WHITELIST",
            "NORMAL",
        }

        if action not in allowed:
            _rb.abort(400)

        intake = _rb.db.session.execute(
            _rb.db.text("""
            SELECT
                id,
                reference,
                caller_phone,
                phone_text
            FROM voice_intake_review
            WHERE id=:id
        """),
            {"id": intake_id}
        ).mappings().first()

        if not intake:
            _rb.abort(404)

        phone = (
            intake["caller_phone"]
            or intake["phone_text"]
            or ""
        ).strip()

        # Only allow a real-looking Egyptian mobile number
        # for BLOCK / WHITELIST.
        import re as _re

        normalized = _re.sub(r"\D", "", phone)

        if (
            action in {"BLOCK", "WHITELIST"}
            and not _re.fullmatch(r"01[0125][0-9]{8}", normalized)
        ):
            _rb.flash(
                "Cannot block or whitelist an unverified phone number.",
                "danger"
            )
            return _rb.redirect(
                _rb.request.referrer
                or _rb.url_for("voice_intake_review")
            )

        status_map = {
            "SPAM": "SUSPECTED_SPAM",
            "BLOCK": "BLOCKED",
            "WHITELIST": "WHITELISTED",
            "NORMAL": "NORMAL",
        }

        status = status_map[action]

        if normalized:

            _rb.db.session.execute(
                _rb.db.text("""
                INSERT INTO voice_caller_control
                (
                    phone,
                    status,
                    reason,
                    call_count,
                    last_call_at,
                    blocked_by,
                    blocked_at,
                    updated_at
                )
                VALUES
                (
                    :phone,
                    :status,
                    :reason,
                    1,
                    CURRENT_TIMESTAMP,
                    :user_id,
                    CASE
                      WHEN :status='BLOCKED'
                      THEN CURRENT_TIMESTAMP
                      ELSE NULL
                    END,
                    CURRENT_TIMESTAMP
                )
                ON CONFLICT (phone)
                DO UPDATE SET
                    status=:status,
                    reason=:reason,
                    blocked_by=
                      CASE
                        WHEN :status='BLOCKED'
                        THEN :user_id
                        ELSE voice_caller_control.blocked_by
                      END,
                    blocked_at=
                      CASE
                        WHEN :status='BLOCKED'
                        THEN CURRENT_TIMESTAMP
                        WHEN :status<>'BLOCKED'
                        THEN NULL
                        ELSE voice_caller_control.blocked_at
                      END,
                    updated_at=CURRENT_TIMESTAMP
            """),
                {
                    "phone": normalized,
                    "status": status,
                    "reason":
                        f"Updated from intake {intake['reference']}",
                    "user_id": _rb.current_user().id,
                }
            )

        if action == "SPAM":
            _rb.db.session.execute(
                _rb.db.text("""
                UPDATE voice_intake_review
                SET
                    spam_flag=true,
                    spam_reason='Marked by reception'
                WHERE id=:id
            """),
                {"id": intake_id}
            )

        elif action in {
            "NORMAL",
            "WHITELIST",
        }:
            _rb.db.session.execute(
                _rb.db.text("""
                UPDATE voice_intake_review
                SET
                    spam_flag=false,
                    spam_reason=NULL
                WHERE id=:id
            """),
                {"id": intake_id}
            )

        _rb.audit(
            "VOICE_CALLER_CONTROL",
            "voice_intake",
            intake_id,
            f"{intake['reference']}:{status}"
        )

        _rb.db.session.commit()

        _rb.flash(
            f"Caller status updated to {status}.",
            "success"
        )

        return _rb.redirect(
            _rb.request.referrer
            or _rb.url_for("voice_intake_review")
        )
    return voice_intake_caller_control


def install_0916(_rb):
    @_rb.app.get("/voice-intake/<int:intake_id>/caller-history")
    @_rb.login_required
    def voice_intake_caller_history(intake_id):

        intake = _rb.db.session.execute(
            _rb.db.text("""
            SELECT
                id,
                reference,
                caller_phone,
                phone_text
            FROM voice_intake_review
            WHERE id=:id
        """),
            {"id": intake_id}
        ).mappings().first()

        if not intake:
            _rb.abort(404)

        import re as _re

        phone = _re.sub(
            r"\D",
            "",
            (
                intake["caller_phone"]
                or intake["phone_text"]
                or ""
            )
        )

        control = None
        history = []

        if phone:

            control = _rb.db.session.execute(
                _rb.db.text("""
                SELECT *
                FROM voice_caller_control
                WHERE phone=:phone
            """),
                {"phone": phone}
            ).mappings().first()

            history = _rb.db.session.execute(
                _rb.db.text("""
                SELECT
                    id,
                    reference,
                    status,
                    reason,
                    created_at,
                    spam_flag
                FROM voice_intake_review
                WHERE caller_phone=:phone
                   OR phone_text=:phone
                ORDER BY created_at DESC
                LIMIT 100
            """),
                {"phone": phone}
            ).mappings().all()

        return _rb.render_template(
            "voice_caller_history.html",
            intake=intake,
            phone=phone,
            control=control,
            history=history
        )
    return voice_intake_caller_history


def install_0919(_rb):
    @_rb.app.route('/telephony')
    @_rb.login_required
    def telephony_console():

        u = _rb.current_user()

        ext = _rb.TelephonyExtension.query.filter_by(
            user_id=u.id,
            active=True
        ).first()

        return _rb.render_template(
            'telephony.html',
            telephony_user=u,
            telephony_extension=ext
        )
    return telephony_console


def install_0921(_rb):
    @_rb.app.route('/api/telephony/credentials')
    @_rb.login_required
    def telephony_credentials():

        u=_rb.current_user()

        ext=_rb.TelephonyExtension.query.filter_by(
            user_id=u.id,
            active=True
        ).first()

        if not ext:
            return _rb.jsonify(
                ok=False,
                error='TELEPHONY_NOT_ASSIGNED'
            ),403

        extension=str(ext.extension or '').strip()

        secrets_map=_rb._rb_sip_secret_map()

        password=secrets_map.get(
            'SIP_' + extension
        )

        if not password:
            return _rb.jsonify(
                ok=False,
                error='SIP_CREDENTIAL_NOT_AVAILABLE'
            ),503

        response=_rb.jsonify(
            ok=True,
            extension=extension,
            display_name=(
                u.full_name
                or u.username
            ),
            role=(
                u.role.code
                if u.role else ''
            ),

            sip_uri=(
                'sip:' +
                extension +
                '@ris.dynuddns.net'
            ),

            websocket=(
                'wss://ris.dynuddns.net/'
                'asterisk-ws'
            ),

            authorization_username=extension,
            authorization_password=password,

            reception='720',

            conference_rooms={
                'reception':'7301',
                'radiology':'7302',
                'operations':'7303',
                'it_pacs':'7304',
                'management':'7305',
                'case_discussion':'7390'
            }
        )

        response.headers['Cache-Control']='no-store, private'
        response.headers['Pragma']='no-cache'

        return response
    return telephony_credentials


def install_0923(_rb):
    @_rb.app.route("/api/public-call/config", methods=["GET"])
    def public_call_config():

        secrets_map = _rb._rb_sip_secret_map()

        password = secrets_map.get(
            "SIP_8999"
        )

        if not password:
            return _rb.jsonify(
                ok=False,
                error="PUBLIC_CALL_UNAVAILABLE"
            ),503

        response = _rb.jsonify(
            ok=True,
            extension="8999",
            sip_uri="sip:8999@ris.dynuddns.net",
            websocket="wss://ris.dynuddns.net/asterisk-ws",
            authorization_username="8999",
            authorization_password=password,

            reception="720",

            allowed_extensions=[
                "720",
                "8101",
                "8102",
                "8111",
                "8112"
            ]
        )

        response.headers[
            "Cache-Control"
        ] = "no-store, private"

        response.headers[
            "Pragma"
        ] = "no-cache"

        return response
    return public_call_config


def install_0929(_rb):
    @_rb.app.post("/api/public-call/request")
    def public_contact_request_create():

        data = _rb.request.get_json(
            silent=True
        ) or {}

        patient_name = _rb._rb_normalize_public_text(
            data.get("patient_name"),
            160
        )

        phone = _rb._rb_normalize_public_text(
            data.get("phone"),
            40
        )

        booking_reference = _rb._rb_normalize_public_text(
            data.get("booking_reference"),
            100
        )

        request_type = (
            _rb._rb_normalize_public_text(
                data.get("request_type"),
                40
            ).upper()
            or "OTHER"
        )

        message = _rb._rb_normalize_public_text(
            data.get("message"),
            2000
        )

        if not patient_name:
            return _rb.jsonify(
                ok=False,
                error="PATIENT_NAME_REQUIRED"
            ),400

        if not phone:
            return _rb.jsonify(
                ok=False,
                error="PHONE_REQUIRED"
            ),400

        reference = _rb._rb_public_reference()

        row = _rb.db.session.execute(
            _rb.db.text("""
            INSERT INTO public_contact_request
            (
                reference,
                patient_name,
                phone,
                booking_reference,
                request_type,
                message,
                status,
                source
            )
            VALUES
            (
                :reference,
                :patient_name,
                :phone,
                :booking_reference,
                :request_type,
                :message,
                'NEW',
                'WEB'
            )
            RETURNING id
        """),
            {
                "reference": reference,
                "patient_name": patient_name,
                "phone": phone,
                "booking_reference": booking_reference,
                "request_type": request_type,
                "message": message,
            }
        ).mappings().first()

        _rb.db.session.commit()

        return _rb.jsonify(
            ok=True,
            request_id=row["id"],
            reference=reference
        )
    return public_contact_request_create


def install_0930(_rb):
    @_rb.app.post("/api/public-chat/start")
    def public_chat_start():

        data = _rb.request.get_json(
            silent=True
        ) or {}

        request_id = data.get(
            "request_id"
        )

        if not request_id:
            return _rb.jsonify(
                ok=False,
                error="REQUEST_ID_REQUIRED"
            ),400

        exists = _rb.db.session.execute(
            _rb.db.text("""
            SELECT id
            FROM public_contact_request
            WHERE id=:id
        """),
            {
                "id": request_id
            }
        ).mappings().first()

        if not exists:
            return _rb.jsonify(
                ok=False,
                error="REQUEST_NOT_FOUND"
            ),404

        token = _rb._rb_secrets.token_urlsafe(
            32
        )

        row = _rb.db.session.execute(
            _rb.db.text("""
            INSERT INTO public_chat_session
            (
                public_token,
                contact_request_id,
                state
            )
            VALUES
            (
                :token,
                :request_id,
                'BOT'
            )
            RETURNING id
        """),
            {
                "token": token,
                "request_id": request_id,
            }
        ).mappings().first()

        _rb.db.session.execute(
            _rb.db.text("""
            INSERT INTO public_chat_message
            (
                session_id,
                sender_type,
                message
            )
            VALUES
            (
                :session_id,
                'BOT',
                :message
            )
        """),
            {
                "session_id": row["id"],
                "message":
                    "أهلاً بك. كيف يمكنني مساعدتك؟ "
                    "يمكنك أيضاً كتابة: موظف، "
                    "للتحويل إلى الاستقبال."
            }
        )

        _rb.db.session.commit()

        return _rb.jsonify(
            ok=True,
            token=token,
            state="BOT"
        )
    return public_chat_start


def install_0931(_rb):
    @_rb.app.get("/api/public-chat/<token>/messages")
    def public_chat_messages(token):

        session_row = _rb.db.session.execute(
            _rb.db.text("""
            SELECT
                id,
                state,
                assigned_user_id
            FROM public_chat_session
            WHERE public_token=:token
        """),
            {
                "token": token
            }
        ).mappings().first()

        if not session_row:
            return _rb.jsonify(
                ok=False,
                error="CHAT_NOT_FOUND"
            ),404

        rows = _rb.db.session.execute(
            _rb.db.text("""
            SELECT
                id,
                sender_type,
                message,
                created_at
            FROM public_chat_message
            WHERE session_id=:session_id
            ORDER BY id
        """),
            {
                "session_id":
                    session_row["id"]
            }
        ).mappings().all()

        return _rb.jsonify(
            ok=True,
            state=session_row["state"],
            assigned_user_id=
                session_row["assigned_user_id"],
            messages=[
                {
                    "id": x["id"],
                    "sender_type":
                        x["sender_type"],
                    "message":
                        x["message"],
                    "created_at":
                        x["created_at"].isoformat()
                        if x["created_at"]
                        else None,
                }
                for x in rows
            ]
        )
    return public_chat_messages


def install_0932(_rb):
    @_rb.app.post("/api/public-chat/<token>/message")
    def public_chat_message(token):

        data = _rb.request.get_json(
            silent=True
        ) or {}

        message = _rb._rb_normalize_public_text(
            data.get("message"),
            2000
        )

        if not message:
            return _rb.jsonify(
                ok=False,
                error="MESSAGE_REQUIRED"
            ),400

        chat = _rb.db.session.execute(
            _rb.db.text("""
            SELECT
                id,
                contact_request_id,
                state,
                bot_failures
            FROM public_chat_session
            WHERE public_token=:token
        """),
            {
                "token": token
            }
        ).mappings().first()

        if not chat:
            return _rb.jsonify(
                ok=False,
                error="CHAT_NOT_FOUND"
            ),404

        _rb.db.session.execute(
            _rb.db.text("""
            INSERT INTO public_chat_message
            (
                session_id,
                sender_type,
                message
            )
            VALUES
            (
                :session_id,
                'PATIENT',
                :message
            )
        """),
            {
                "session_id": chat["id"],
                "message": message,
            }
        )

        state = chat["state"]

        if (
            state == "BOT"
            and _rb._rb_human_requested(message)
        ):

            state = "WAITING_HUMAN"

            _rb.db.session.execute(
                _rb.db.text("""
                UPDATE public_chat_session
                SET
                    state='WAITING_HUMAN',
                    updated_at=NOW()
                WHERE id=:id
            """),
                {
                    "id": chat["id"]
                }
            )

            _rb.db.session.execute(
                _rb.db.text("""
                UPDATE public_contact_request
                SET
                    status='WAITING_HUMAN',
                    updated_at=NOW()
                WHERE id=:id
            """),
                {
                    "id":
                        chat["contact_request_id"]
                }
            )

            reply = (
                "تم تحويل المحادثة إلى موظف. "
                "سيتم الرد عليك من الاستقبال عند توفر موظف."
            )

            _rb.db.session.execute(
                _rb.db.text("""
                INSERT INTO public_chat_message
                (
                    session_id,
                    sender_type,
                    message
                )
                VALUES
                (
                    :session_id,
                    'SYSTEM',
                    :message
                )
            """),
                {
                    "session_id": chat["id"],
                    "message": reply,
                }
            )

        elif state == "BOT":

            understood, reply = (
                _rb._rb_public_bot_answer(
                    message
                )
            )

            failures = (
                0
                if understood
                else int(
                    chat["bot_failures"] or 0
                ) + 1
            )

            if failures >= 2:

                state = "WAITING_HUMAN"

                reply = (
                    "سأحول المحادثة إلى موظف "
                    "ليساعدك بشكل أفضل."
                )

                _rb.db.session.execute(
                    _rb.db.text("""
                    UPDATE public_chat_session
                    SET
                        state='WAITING_HUMAN',
                        bot_failures=:failures,
                        updated_at=NOW()
                    WHERE id=:id
                """),
                    {
                        "id": chat["id"],
                        "failures": failures,
                    }
                )

                _rb.db.session.execute(
                    _rb.db.text("""
                    UPDATE public_contact_request
                    SET
                        status='WAITING_HUMAN',
                        updated_at=NOW()
                    WHERE id=:id
                """),
                    {
                        "id":
                            chat["contact_request_id"]
                    }
                )

            else:

                _rb.db.session.execute(
                    _rb.db.text("""
                    UPDATE public_chat_session
                    SET
                        bot_failures=:failures,
                        updated_at=NOW()
                    WHERE id=:id
                """),
                    {
                        "id": chat["id"],
                        "failures": failures,
                    }
                )

            _rb.db.session.execute(
                _rb.db.text("""
                INSERT INTO public_chat_message
                (
                    session_id,
                    sender_type,
                    message
                )
                VALUES
                (
                    :session_id,
                    'BOT',
                    :message
                )
            """),
                {
                    "session_id": chat["id"],
                    "message": reply,
                }
            )

        _rb.db.session.commit()

        return _rb.jsonify(
            ok=True,
            state=state
        )
    return public_chat_message


def install_0933(_rb):
    @_rb.app.route("/communications")
    @_rb.login_required
    def communications_dashboard():

        if not _rb._rb_staff_role_allowed():
            _rb.abort(403)

        return _rb.render_template(
            "communications_dashboard.html"
        )
    return communications_dashboard


def install_0935(_rb):
    @_rb.app.post("/api/staff/communications/<int:request_id>/claim")
    @_rb.login_required
    def staff_communications_claim(request_id):

        if not _rb._rb_staff_role_allowed():
            _rb.abort(403)

        u = _rb.current_user()

        _rb.db.session.execute(
            _rb.db.text("""
            UPDATE public_contact_request
            SET
                assigned_user_id=:uid,
                status='IN_PROGRESS',
                updated_at=NOW()
            WHERE id=:id
        """),
            {
                "uid": u.id,
                "id": request_id,
            }
        )

        _rb.db.session.execute(
            _rb.db.text("""
            UPDATE public_chat_session
            SET
                assigned_user_id=:uid,
                state='HUMAN',
                updated_at=NOW()
            WHERE contact_request_id=:id
        """),
            {
                "uid": u.id,
                "id": request_id,
            }
        )

        _rb.db.session.execute(
            _rb.db.text("""
            INSERT INTO public_chat_message
            (
                session_id,
                sender_type,
                sender_user_id,
                message
            )
            SELECT
                id,
                'SYSTEM',
                :uid,
                'تم انضمام موظف الاستقبال إلى المحادثة.'
            FROM public_chat_session
            WHERE contact_request_id=:id
        """),
            {
                "uid": u.id,
                "id": request_id,
            }
        )

        _rb.db.session.commit()

        return _rb.jsonify(
            ok=True
        )
    return staff_communications_claim


def install_0936(_rb):
    @_rb.app.post("/api/staff/communications/<int:request_id>/confirm")
    @_rb.login_required
    def staff_communications_confirm(request_id):

        if not _rb._rb_staff_role_allowed():
            _rb.abort(403)

        u = _rb.current_user()

        data = _rb.request.get_json(
            silent=True
        ) or {}

        patient_name = _rb._rb_normalize_public_text(
            data.get("patient_name"),
            160
        )

        phone = _rb._rb_normalize_public_text(
            data.get("phone"),
            40
        )

        booking_reference = (
            _rb._rb_normalize_public_text(
                data.get("booking_reference"),
                100
            )
        )

        request_type = (
            _rb._rb_normalize_public_text(
                data.get("request_type"),
                40
            ).upper()
            or "OTHER"
        )

        _rb.db.session.execute(
            _rb.db.text("""
            UPDATE public_contact_request
            SET
                patient_name=:patient_name,
                phone=:phone,
                booking_reference=:booking_reference,
                request_type=:request_type,
                confirmed=TRUE,
                confirmed_by_user_id=:uid,
                confirmed_at=NOW(),
                status='CONFIRMED',
                updated_at=NOW()
            WHERE id=:id
        """),
            {
                "id": request_id,
                "uid": u.id,
                "patient_name": patient_name,
                "phone": phone,
                "booking_reference":
                    booking_reference,
                "request_type": request_type,
            }
        )

        _rb.db.session.commit()

        return _rb.jsonify(
            ok=True
        )
    return staff_communications_confirm


def install_0937(_rb):
    @_rb.app.post("/api/staff/communications/<int:request_id>/reject")
    @_rb.login_required
    def staff_communications_reject(request_id):

        if not _rb._rb_staff_role_allowed():
            _rb.abort(403)

        u = _rb.current_user()

        _rb.db.session.execute(
            _rb.db.text("""
            UPDATE public_contact_request
            SET
                status='REJECTED',
                rejected_by_user_id=:uid,
                rejected_at=NOW(),
                updated_at=NOW()
            WHERE id=:id
        """),
            {
                "id": request_id,
                "uid": u.id,
            }
        )

        _rb.db.session.commit()

        return _rb.jsonify(
            ok=True
        )
    return staff_communications_reject


def install_0939(_rb):
    @_rb.app.post("/api/staff/chat/<int:request_id>/message")
    @_rb.login_required
    def staff_chat_message(request_id):

        if not _rb._rb_staff_role_allowed():
            _rb.abort(403)

        u = _rb.current_user()

        data = _rb.request.get_json(
            silent=True
        ) or {}

        message = _rb._rb_normalize_public_text(
            data.get("message"),
            2000
        )

        if not message:
            return _rb.jsonify(
                ok=False,
                error="MESSAGE_REQUIRED"
            ),400

        session_row = _rb.db.session.execute(
            _rb.db.text("""
            SELECT id
            FROM public_chat_session
            WHERE contact_request_id=:id
        """),
            {
                "id": request_id
            }
        ).mappings().first()

        if not session_row:
            return _rb.jsonify(
                ok=False,
                error="CHAT_NOT_FOUND"
            ),404

        _rb.db.session.execute(
            _rb.db.text("""
            INSERT INTO public_chat_message
            (
                session_id,
                sender_type,
                sender_user_id,
                message
            )
            VALUES
            (
                :session_id,
                'STAFF',
                :uid,
                :message
            )
        """),
            {
                "session_id":
                    session_row["id"],
                "uid": u.id,
                "message": message,
            }
        )

        _rb.db.session.execute(
            _rb.db.text("""
            UPDATE public_chat_session
            SET
                state='HUMAN',
                assigned_user_id=:uid,
                updated_at=NOW()
            WHERE id=:id
        """),
            {
                "id": session_row["id"],
                "uid": u.id,
            }
        )

        _rb.db.session.commit()

        return _rb.jsonify(
            ok=True
        )
    return staff_chat_message


def install_0942(_rb):
    @_rb.app.post("/api/public-call/request/<int:request_id>/details")
    def public_contact_request_details(request_id):

        data = _rb.request.get_json(
            silent=True
        ) or {}

        date_of_birth = (
            str(data.get("date_of_birth") or "").strip()
            or None
        )

        age_years = data.get("age_years")

        try:
            age_years = (
                int(age_years)
                if age_years not in (None, "")
                else None
            )
        except Exception:
            age_years = None

        exam_name = _rb._rb_normalize_public_text(
            data.get("exam_name"),
            240
        )

        insurance_company = _rb._rb_normalize_public_text(
            data.get("insurance_company"),
            200
        )

        insurance_member_no = _rb._rb_normalize_public_text(
            data.get("insurance_member_no"),
            120
        )

        medical_approval_no = _rb._rb_normalize_public_text(
            data.get("medical_approval_no"),
            160
        )

        medical_approval_status = (
            _rb._rb_normalize_public_text(
                data.get("medical_approval_status"),
                40
            ).upper()
            or "NOT_DECLARED"
        )

        allowed_approval = {
            "NOT_DECLARED",
            "NOT_REQUIRED",
            "REQUIRED",
            "PENDING",
            "PATIENT_HAS_APPROVAL",
        }

        if medical_approval_status not in allowed_approval:
            medical_approval_status = "NOT_DECLARED"

        payment_preference = (
            _rb._rb_normalize_public_text(
                data.get("payment_preference"),
                50
            ).upper()
            or None
        )

        notification_email_address = (
            _rb._rb_normalize_public_text(
                data.get("notification_email_address"),
                240
            )
            or None
        )

        _rb.db.session.execute(
            _rb.db.text("""
            UPDATE public_contact_request
            SET
                date_of_birth=:date_of_birth,
                age_years=:age_years,
                exam_name=:exam_name,

                insurance_company=:insurance_company,
                insurance_member_no=:insurance_member_no,

                medical_approval_no=:medical_approval_no,
                medical_approval_status=:medical_approval_status,

                payment_preference=:payment_preference,

                notification_whatsapp=:notification_whatsapp,
                notification_sms=:notification_sms,
                notification_email=:notification_email,
                notification_web_chat=:notification_web_chat,
                notification_email_address=:notification_email_address,

                updated_at=NOW()

            WHERE id=:request_id
        """),
            {
                "request_id": request_id,

                "date_of_birth": date_of_birth,
                "age_years": age_years,
                "exam_name": exam_name,

                "insurance_company": insurance_company,
                "insurance_member_no": insurance_member_no,

                "medical_approval_no": medical_approval_no,
                "medical_approval_status":
                    medical_approval_status,

                "payment_preference":
                    payment_preference,

                "notification_whatsapp":
                    bool(data.get("notification_whatsapp")),

                "notification_sms":
                    bool(data.get("notification_sms")),

                "notification_email":
                    bool(data.get("notification_email")),

                "notification_web_chat":
                    bool(data.get(
                        "notification_web_chat",
                        True
                    )),

                "notification_email_address":
                    notification_email_address,
            }
        )

        _rb.db.session.commit()

        return _rb.jsonify(
            ok=True
        )
    return public_contact_request_details


def install_0943(_rb):
    @_rb.app.post(
        "/api/public-call/request/"
        "<int:request_id>/attachments"
    )
    def public_contact_attachment_upload(request_id):

        exists = _rb.db.session.execute(
            _rb.db.text("""
            SELECT id
            FROM public_contact_request
            WHERE id=:id
        """),
            {"id": request_id}
        ).mappings().first()

        if not exists:
            return _rb.jsonify(
                ok=False,
                error="REQUEST_NOT_FOUND"
            ),404

        files = _rb.request.files.getlist(
            "files"
        )

        if not files:
            return _rb.jsonify(
                ok=False,
                error="NO_FILES"
            ),400

        if len(files) > 10:
            return _rb.jsonify(
                ok=False,
                error="TOO_MANY_FILES"
            ),400

        attachment_type = (
            str(
                _rb.request.form.get(
                    "attachment_type",
                    "OTHER"
                )
            )
            .strip()
            .upper()
        )

        if attachment_type not in _rb._RB_PUBLIC_ATTACHMENT_TYPES:
            attachment_type = "OTHER"

        description = _rb._rb_normalize_public_text(
            _rb.request.form.get("description"),
            300
        )

        root = _rb._rb_public_attachment_root()

        request_dir = _rb._rb_os.path.join(
            root,
            str(request_id)
        )

        _rb._rb_os.makedirs(
            request_dir,
            exist_ok=True
        )

        uploaded = []

        for f in files:

            original = str(
                f.filename or ""
            ).strip()

            if not original:
                continue

            ext = _rb._rb_safe_upload_extension(
                original
            )

            if ext not in _rb._RB_ALLOWED_UPLOAD_EXTENSIONS:
                return _rb.jsonify(
                    ok=False,
                    error="FILE_TYPE_NOT_ALLOWED",
                    filename=original
                ),400

            mime = str(
                f.mimetype or ""
            ).lower()

            if (
                mime
                and mime not in
                _rb._RB_ALLOWED_UPLOAD_MIMES
            ):
                return _rb.jsonify(
                    ok=False,
                    error="MIME_NOT_ALLOWED",
                    filename=original
                ),400

            blob = f.read(
                10 * 1024 * 1024 + 1
            )

            if len(blob) > 10 * 1024 * 1024:
                return _rb.jsonify(
                    ok=False,
                    error="FILE_TOO_LARGE",
                    filename=original
                ),413

            stored = (
                _rb._rb_uuid.uuid4().hex
                + ext
            )

            destination = _rb._rb_os.path.join(
                request_dir,
                stored
            )

            with open(
                destination,
                "wb"
            ) as out:
                out.write(blob)

            row = _rb.db.session.execute(
                _rb.db.text("""
                INSERT INTO public_contact_attachment
                (
                    contact_request_id,
                    attachment_type,
                    description,
                    original_filename,
                    stored_filename,
                    mime_type,
                    size_bytes
                )
                VALUES
                (
                    :request_id,
                    :attachment_type,
                    :description,
                    :original_filename,
                    :stored_filename,
                    :mime_type,
                    :size_bytes
                )
                RETURNING id
            """),
                {
                    "request_id":
                        request_id,

                    "attachment_type":
                        attachment_type,

                    "description":
                        description,

                    "original_filename":
                        original,

                    "stored_filename":
                        stored,

                    "mime_type":
                        mime,

                    "size_bytes":
                        len(blob),
                }
            ).mappings().first()

            uploaded.append({
                "id": row["id"],
                "filename": original,
            })

        _rb.db.session.commit()

        return _rb.jsonify(
            ok=True,
            uploaded=uploaded
        )
    return public_contact_attachment_upload
