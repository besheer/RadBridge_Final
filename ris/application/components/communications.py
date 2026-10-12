"""Runtime-bound application.components.communications; dependencies are supplied at composition.

Legacy behavior is preserved; new policies belong in the independent domain layer.
"""

def install_0007(_rb):
    def _notification_exists(order_id,channel,recipient):
        return _rb.NotificationEvent.query.filter_by(
            order_id=order_id,channel=channel,recipient=recipient
        ).first()
    return _notification_exists


def install_0010(_rb):
    def send_notification_job(job):
        """Provider adapter. Failure never changes report FINAL state."""
        order=job.order
        patient=order.patient if order else None
        portal_url=_rb._final_portal_url(order) if order else _rb.RIS_PUBLIC_URL
        job.attempts=int(job.attempts or 0)+1
        try:
            if job.channel=='EMAIL':
                if not _rb.SMTP_ENABLED:
                    raise RuntimeError('SMTP disabled')
                body=(
                    f"Your radiology report is ready.\n"
                    f"Accession: {order.accession}\n"
                    f"Secure report link: {portal_url}\n"
                )
                msg=_rb.EmailMessage()
                msg['Subject']='Radiology report ready'
                msg['From']=_rb.SMTP_FROM
                msg['To']=job.recipient
                msg.set_content(body)
                with _rb.smtplib.SMTP(_rb.SMTP_HOST,_rb.SMTP_PORT,timeout=20) as smtp:
                    if _rb.SMTP_TLS: smtp.starttls()
                    if _rb.SMTP_USER: smtp.login(_rb.SMTP_USER,_rb.SMTP_PASSWORD)
                    smtp.send_message(msg)

            elif job.channel=='TELEGRAM':
                if not _rb.TELEGRAM_ENABLED:
                    raise RuntimeError('Telegram disabled')
                text=f"FINAL report ready | {order.accession} | {patient.name if patient else ''}"
                r=_rb.requests.post(
                    f'https://api.telegram.org/bot{_rb.TELEGRAM_BOT_TOKEN}/sendMessage',
                    json={'chat_id':job.recipient,'text':text},
                    timeout=15
                )
                r.raise_for_status()

            elif job.channel=='WHATSAPP':
                if not _rb.WHATSAPP_ENABLED:
                    raise RuntimeError('WhatsApp disabled')
                text=(
                    f"تم اعتماد التقرير النهائي للفحص {order.accession}. "
                    f"رابط التقرير الآمن: {portal_url}"
                )
                headers={}
                if _rb.WHATSAPP_API_KEY:
                    headers['apikey']=_rb.WHATSAPP_API_KEY
                payload={
                    'number':job.recipient,
                    'text':text,
                    'instance':_rb.WHATSAPP_INSTANCE,
                    'order_id':order.id
                }
                r=_rb.requests.post(_rb.WHATSAPP_API_URL,json=payload,headers=headers,timeout=20)
                r.raise_for_status()
            else:
                raise RuntimeError('Unsupported notification channel')

            job.status='SENT'
            job.sent_at=_rb.datetime.utcnow()
            job.last_error=''
            _rb.audit('NOTIFICATION_SENT','order',order.id,f'{job.channel} {job.recipient}')
            return True
        except Exception as exc:
            job.status='FAILED'
            job.last_error=str(exc)[:1000]
            _rb.audit('NOTIFICATION_FAILED','order',order.id,f'{job.channel}: {job.last_error}')
            return False
    return send_notification_job


def install_0011(_rb):
    def process_notification_queue(limit=25):
        jobs=_rb.NotificationEvent.query.filter(
            _rb.NotificationEvent.status.in_(['PENDING','FAILED']),
            _rb.NotificationEvent.attempts<5
        ).order_by(_rb.NotificationEvent.id.asc()).limit(limit).all()
        for job in jobs:
            _rb.send_notification_job(job)
        _rb.db.session.commit()
        return len(jobs)
    return process_notification_queue


def install_0261(_rb):
    def ensure_chat_member(thread,user_id):
        row=_rb.ChatThreadMember.query.filter_by(thread_id=thread.id,user_id=user_id).first()
        if not row:
            row=_rb.ChatThreadMember(thread_id=thread.id,user_id=user_id);_rb.db.session.add(row)
        return row
    return ensure_chat_member


def install_0263(_rb):
    def unread_chat_count(user=None):
        user=user or _rb.current_user()
        if not user:return 0
        total=0
        for m in _rb.ChatThreadMember.query.filter_by(user_id=user.id,muted=False).all():
            q=_rb.ChatMessage.query.filter_by(thread_id=m.thread_id).filter(_rb.ChatMessage.sender_id!=user.id,_rb.ChatMessage.deleted_at.is_(None))
            if m.last_read_at:q=q.filter(_rb.ChatMessage.created_at>m.last_read_at)
            total+=q.count()
        return total
    return unread_chat_count


def install_0334(_rb):
    def call_configured_ai_provider(order):
        cfg=_rb.ai_provider_setting()
        if not cfg: return None,'No AI provider enabled'
        if not cfg.base_url: return None,'AI provider URL not configured'
        try:
            import requests
            headers={'Content-Type':'application/json'}
            key=_rb.os.environ.get('RIS_AI_API_KEY','')
            if key: headers['Authorization']='Bearer '+key
            r=requests.post(cfg.base_url.rstrip('/')+'/generate',
                json={'model':cfg.model_name,'input':_rb.generate_ai_draft_payload(order)},
                headers=headers,timeout=max(5,int(cfg.timeout_seconds or 60)))
            r.raise_for_status()
            d=r.json()
            return {
              'findings':str(d.get('findings') or ''),
              'impression':str(d.get('impression') or ''),
              'comparison':str(d.get('comparison') or ''),
              'safety_notes':str(d.get('safety_notes') or '')
            },''
        except Exception as e:
            return None,str(e)[:500]
    return call_configured_ai_provider


def install_0339(_rb):
    def seed_communication_defaults():
        for code,en,ar,ch,event,subject,body in _rb.DEFAULT_COMM_TEMPLATES:
            if not _rb.CommunicationTemplate.query.filter_by(code=code).first():
                _rb.db.session.add(_rb.CommunicationTemplate(
                    code=code,name_en=en,name_ar=ar,channel=ch,event_key=event,
                    subject_template=subject,body_template=body,active=True
                ))
        for ch,env in [('WHATSAPP','RIS_WHATSAPP_TOKEN'),('TELEGRAM','RIS_TELEGRAM_BOT_TOKEN'),('EMAIL','RIS_SMTP_PASSWORD')]:
            if not _rb.CommunicationChannelSetting.query.filter_by(channel=ch).first():
                _rb.db.session.add(_rb.CommunicationChannelSetting(channel=ch,enabled=False,secret_env_name=env))
        _rb.db.session.commit()
    return seed_communication_defaults


def install_0340(_rb):
    def communication_context(patient,order=None,receipt=None,extra=None):
        ctx={
          'patient_name':patient.name or '',
          'patient_id':patient.patient_id or '',
          'mobile':patient.phone or '',
          'email':getattr(patient,'email','') or '',
          'procedure':getattr(order,'procedure','') if order else '',
          'accession':getattr(order,'accession','') if order else '',
          'scheduled':str(getattr(order,'scheduled','') or '') if order else '',
          'receipt_no':getattr(receipt,'receipt_no','') if receipt else '',
          'amount':str(getattr(receipt,'amount','') or '') if receipt else '',
        }
        if extra: ctx.update(extra)
        return ctx
    return communication_context


def install_0343(_rb):
    def communication_setting(channel):
        return _rb.CommunicationChannelSetting.query.filter_by(channel=channel.upper()).first()
    return communication_setting


def install_0344(_rb):
    def send_patient_communication(row):
        cfg=_rb.communication_setting(row.channel)
        if not cfg or not cfg.enabled:
            row.status='FAILED'; row.error_text='Channel disabled'; _rb.db.session.commit()
            return False,'Channel disabled'
        try:
            if row.channel=='EMAIL':
                import smtplib
                from email.message import EmailMessage
                secret=_rb.os.environ.get(cfg.secret_env_name or 'RIS_SMTP_PASSWORD','')
                msg=EmailMessage()
                msg['Subject']=row.subject or 'RIS Notification'
                msg['From']=cfg.sender or cfg.smtp_user
                msg['To']=row.recipient
                msg.set_content(row.body or '')
                with smtplib.SMTP(cfg.smtp_host,int(cfg.smtp_port or 587),timeout=30) as server:
                    if cfg.smtp_tls: server.starttls()
                    if cfg.smtp_user: server.login(cfg.smtp_user,secret)
                    server.send_message(msg)
                row.status='SENT'; row.sent_at=_rb.datetime.utcnow(); row.error_text=''
                _rb.db.session.commit(); return True,''
            elif row.channel=='TELEGRAM':
                import requests
                token=_rb.os.environ.get(cfg.secret_env_name or 'RIS_TELEGRAM_BOT_TOKEN','')
                if not token: raise RuntimeError('Telegram token missing')
                r=requests.post(
                    f'https://api.telegram.org/bot{token}/sendMessage',
                    json={'chat_id':row.recipient,'text':row.body},
                    timeout=30
                )
                r.raise_for_status()
                data=r.json()
                row.provider_message_id=str((data.get('result') or {}).get('message_id',''))
                row.status='SENT'; row.sent_at=_rb.datetime.utcnow(); row.error_text=''
                _rb.db.session.commit(); return True,''
            elif row.channel=='WHATSAPP':
                import requests
                token=_rb.os.environ.get(cfg.secret_env_name or 'RIS_WHATSAPP_TOKEN','')
                if not cfg.base_url: raise RuntimeError('WhatsApp API URL missing')
                headers={'Content-Type':'application/json'}
                if token: headers['Authorization']='Bearer '+token
                payload={'to':row.recipient,'message':row.body,'sender':cfg.sender}
                r=requests.post(cfg.base_url,json=payload,headers=headers,timeout=30)
                r.raise_for_status()
                try:
                    data=r.json()
                    row.provider_message_id=str(data.get('id') or data.get('message_id') or '')
                except Exception:
                    pass
                row.status='SENT'; row.sent_at=_rb.datetime.utcnow(); row.error_text=''
                _rb.db.session.commit(); return True,''
            else:
                raise RuntimeError('Unsupported channel')
        except Exception as e:
            row.status='FAILED'; row.error_text=str(e)[:1000]; _rb.db.session.commit()
            return False,row.error_text
    return send_patient_communication


def install_0375(_rb):
    def create_ris_notification(
        order,
        event_type,
        title,
        body,
        severity='WARNING',
        role_code='',
        user_id=None,
        commit=True
    ):
        n=_rb.RISNotification(
            order_id=order.id,
            branch_id=order.branch_id,
            severity=severity,
            event_type=event_type,
            title=title,
            body=body,
            role_code=role_code,
            user_id=user_id,
            status='NEW'
        )
        _rb.db.session.add(n)
        if commit:
            _rb.db.session.commit()
        return n
    return create_ris_notification


def install_0398(_rb):
    def call_ocr_provider(doc):
        cfg=_rb.enabled_ocr_provider()
        if not cfg:
            return None,'OCR_NOT_CONFIGURED: No OCR provider is enabled'
        if (cfg.validation_status not in ('READY','READY_WITH_WARNINGS') or
                cfg.validation_config_hash!=_rb.ocr_configuration_hash(cfg)):
            return None,'OCR_NOT_VALIDATED: Provider settings must pass validation after the latest configuration change'
        key=_rb.os.environ.get(cfg.secret_env_name or 'RIS_OCR_API_KEY','')
        try:
            payload=_rb.ocr_extract_file(
                cfg,
                key,
                doc.file_path,
                original_name=doc.original_name,
                mime_type=doc.mime_type or 'application/octet-stream',
                document_type=doc.document_type,
                environ=_rb.os.environ,
            )
            text=str(payload.get('text') or '')
            fields=payload.get('fields') or {}
            conf=float(payload.get('confidence') or 0)
            if doc.document_type=='IDENTITY':
                base=_rb._simple_identity_extract(text)
                base.update(fields)

                # RB_FULL_REG_OCR_DEMOGRAPHICS_V1
                # Keep provider values, but enrich a valid Egyptian
                # National ID with its encoded DOB and sex for registration.
                normalized=_rb.normalize_intake_identity(base)
                for field_key in ('national_id','dob','sex'):
                    if normalized.get(field_key) and not base.get(field_key):
                        base[field_key]=normalized[field_key]

                fields=base
            return {'text':text,'fields':fields,'confidence':conf},''
        except _rb.OCRProviderError as e:
            return None,f'{e.code}: {e.message}'[:500]
        except Exception:
            _rb.app.logger.exception('Unexpected OCR adapter failure')
            return None,'OCR_INTERNAL_ERROR: Unexpected OCR adapter failure'
    return call_ocr_provider

