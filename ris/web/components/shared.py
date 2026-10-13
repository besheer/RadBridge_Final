"""Runtime-bound web.components.shared; dependencies are supplied at composition.

Legacy behavior is preserved; new policies belong in the independent domain layer.
"""

def install_0004(_rb):
    def lang():
        try:
            return _rb.current_ui_language()
        except Exception:
            v=_rb.session.get('ui_lang') or _rb.session.get('lang') or 'en'
            return v if v in ('en','ar') else 'en'
    return lang


def install_0008(_rb):
    def queue_final_delivery(order):
        """Create FINAL-only portal and notification jobs. Safe and idempotent."""
        report=getattr(order,'report',None)
        if not order or (order.status or '').upper()!='FINAL':
            return 0
        if not report or (report.status or '').upper()!='FINAL':
            return 0

        token=_rb._active_portal_token(order)
        portal_url=_rb.RIS_PUBLIC_URL + _rb.url_for('patient_portal',token=token)
        patient=order.patient
        created=0

        patient_message=(
            f"تم اعتماد التقرير النهائي للفحص {order.accession}. "
            f"يمكنك فتح التقرير من الرابط الآمن التالي: {portal_url}"
        )
        staff_message=(
            f"FINAL report ready | {order.accession} | "
            f"{patient.name if patient else ''}"
        )

        if _rb.WHATSAPP_ENABLED and patient and patient.phone:
            if not _rb._notification_exists(order.id,'WHATSAPP',patient.phone):
                _rb.db.session.add(_rb.NotificationEvent(
                    order_id=order.id,channel='WHATSAPP',recipient=patient.phone,
                    status='PENDING',attempts=0,last_error=''
                )); created+=1

        if _rb.SMTP_ENABLED and patient and getattr(patient,'email',''):
            if not _rb._notification_exists(order.id,'EMAIL',patient.email):
                _rb.db.session.add(_rb.NotificationEvent(
                    order_id=order.id,channel='EMAIL',recipient=patient.email,
                    status='PENDING',attempts=0,last_error=''
                )); created+=1

        if _rb.TELEGRAM_ENABLED and _rb.TELEGRAM_STAFF_CHAT_ID:
            if not _rb._notification_exists(order.id,'TELEGRAM',_rb.TELEGRAM_STAFF_CHAT_ID):
                _rb.db.session.add(_rb.NotificationEvent(
                    order_id=order.id,channel='TELEGRAM',recipient=_rb.TELEGRAM_STAFF_CHAT_ID,
                    status='PENDING',attempts=0,last_error=''
                )); created+=1

        # Store messages in audit, not medical report content in chat.
        _rb.audit('FINAL_DELIVERY_QUEUED','order',order.id,
              f'portal={portal_url} jobs={created}')
        _rb.db.session.flush()
        return created
    return queue_final_delivery


def install_0009(_rb):
    def _final_portal_url(order):
        token=_rb._active_portal_token(order)
        return _rb.RIS_PUBLIC_URL + _rb.url_for('patient_portal',token=token)
    return _final_portal_url


def install_0023(_rb):
    def _export_csv(d,name):
        x=_rb.io.StringIO();w=_rb.csv.writer(x);w.writerow([d['title']]);w.writerow(['Period',d['filters']['start'],d['filters']['end']]);w.writerow([]);w.writerow(d['headers'])
        for row in d['rows']:w.writerow(row)
        return _rb.send_file(_rb.io.BytesIO(x.getvalue().encode('utf-8-sig')),as_attachment=True,download_name=name+'.csv',mimetype='text/csv; charset=utf-8')
    return _export_csv


def install_0024(_rb):
    def _export_xlsx(d,name):
        wb=_rb.Workbook();ws=wb.active;ws.title='Report';ws['A1']=d['title'];ws['A1'].font=_rb.Font(size=16,bold=True);ws['A2']=f"Period: {d['filters']['start']} to {d['filters']['end']}"
        for c,h in enumerate(d['headers'],1):
            x=ws.cell(4,c,h);x.font=_rb.Font(bold=True,color='FFFFFF');x.fill=_rb.PatternFill('solid',fgColor='1F4E78');x.alignment=_rb.Alignment(horizontal='center')
        for rr,row in enumerate(d['rows'],5):
            for cc,v in enumerate(row,1):ws.cell(rr,cc,v)
        for c in range(1,max(len(d['headers']),1)+1):
            vals=[len(str(ws.cell(r,c).value or '')) for r in range(1,ws.max_row+1)];ws.column_dimensions[_rb.get_column_letter(c)].width=min(max(max(vals or [10])+2,10),38)
        b=_rb.io.BytesIO();wb.save(b);b.seek(0)
        return _rb.send_file(b,as_attachment=True,download_name=name+'.xlsx',mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    return _export_xlsx


def install_0025(_rb):
    def _export_pdf(d,name):
        b=_rb.io.BytesIO();doc=_rb.SimpleDocTemplate(b,pagesize=_rb.A4,rightMargin=20,leftMargin=20,topMargin=25,bottomMargin=25);styles=_rb.getSampleStyleSheet()
        story=[_rb.Paragraph(d['title'],styles['Title']),_rb.Paragraph(f"Period: {d['filters']['start']} to {d['filters']['end']}",styles['Normal']),_rb.Spacer(1,10)]
        data=[d['headers']]+[[str(v if v is not None else '') for v in row] for row in d['rows']]
        if not d['headers']:data=[['No data']]
        t=_rb.Table(data,repeatRows=1);t.setStyle(_rb.TableStyle([('BACKGROUND',(0,0),(-1,0),_rb.colors.HexColor('#1F4E78')),('TEXTCOLOR',(0,0),(-1,0),_rb.colors.white),('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),('FONTSIZE',(0,0),(-1,-1),7),('GRID',(0,0),(-1,-1),.25,_rb.colors.HexColor('#D9E2F3')),('VALIGN',(0,0),(-1,-1),'TOP')]))
        story.append(t);doc.build(story);b.seek(0);return _rb.send_file(b,as_attachment=True,download_name=name+'.pdf',mimetype='application/pdf')
    return _export_pdf


def install_0031(_rb):
    def _portal_url_for_order(order):
        token=_rb._active_portal_token(order);_rb.db.session.flush()
        return _rb.RIS_PUBLIC_URL+_rb.url_for('patient_portal',token=token)
    return _portal_url_for_order


def install_0111(_rb):
    def require_perm(perm):
        def deco(fn):
            @_rb.wraps(fn)
            def w(*a, **kw):
                if not _rb.current_user(): return _rb.redirect(_rb.url_for('login', next=_rb.request.path))
                if not _rb.has_perm(perm): _rb.abort(403)
                return fn(*a, **kw)
            return w
        return deco
    return require_perm


def install_0120(_rb):
    def _rb_calendar_redirect(scheduled=None,branch_id=None,device_id=None):
        kw={}
        if scheduled is not None: kw['date']=scheduled.date().isoformat()
        if branch_id: kw['branch_id']=branch_id
        if device_id: kw['device_id']=device_id
        return _rb.redirect(_rb.url_for('schedule_calendar',**kw))
    return _rb_calendar_redirect


def install_0155(_rb):
    @_rb.login_required
    def api_pricing():
        proc=_rb.Procedure.query.get(_rb.request.args.get('procedure_id',type=int))
        contract=_rb.Contract.query.get(_rb.request.args.get('contract_id',type=int)) if _rb.request.args.get('contract_id') else None
        if not proc: return _rb.jsonify({'ok':False}),400
        gross,effective,patient_share,company_share,share_pct=_rb.price_order(proc,contract)
        return _rb.jsonify({'ok':True,'gross':gross,'contract_price':effective,'patient_share':patient_share,
                        'company_share':company_share,'patient_share_percent':share_pct,
                        'approval_required':bool(contract.approval_required) if contract else False})
    return api_pricing


def install_0187(_rb):
    def flash_exam_transition_blocked(order, decision, current, target):
        details = getattr(decision, 'details', None)
        if details is not None:
            _rb.flash({'order_id': order.id, 'details': details}, 'exam-completion-blocked')
        else:
            _rb.flash(f'Invalid workflow transition: {current} → {target}. Reason: {decision.reason}.','danger')
    return flash_exam_transition_blocked


def install_0188(_rb):
    def _apply_exam_transition(order,target,role_code,override=False):
        import procedure_staff_workflow as staff
        mod=_rb._reporting_support_sys.modules[_rb.__name__]
        from flask import has_request_context
        if getattr(order,'procedure_id',None):
            staff.lock_policy(mod,order.procedure_id)
            if has_request_context() and _rb.current_user() and _rb.current_user().role and _rb.current_user().role.code.upper() in ('NURSING','TECHNICIAN'):staff.scoped(mod,order)
        current=(order.exam_status or 'ORDERED').upper()

        # Legacy BOOKED cases enter the technician workflow at ORDERED.
        policy_current=(
            'ORDERED'
            if role_code in ('TECHNICIAN','SERVICE')
            and current=='BOOKED'
            and target=='IN_PROGRESS'
            else current
        )

        pacs_gate_ok=False
        if target=='REPORTING':
            pacs_gate_ok,_reason=_rb.pacs_demographic_gate(order)

        decision=_rb.exam_transition_gate(
            role_code=role_code,
            current_exam_status=policy_current,
            target_exam_status=target,
            order_status=order.status,
            override=override,
            pacs_gate_ok=pacs_gate_ok,
        )

        if not decision.allowed:
            return decision,current

        import procedure_staff_workflow as staff
        mod=_rb._reporting_support_sys.modules[_rb.__name__]
        p=staff.policy(mod,order)
        if target in ('IN_PROGRESS','EXAM_COMPLETED') and (p.get('invalid') or p['mode']!='EXAM'):
            from technician_image_policy import ImageCompletionDecision
            return ImageCompletionDecision(False,'This procedure permits notes and consumables only',{}),current
        if target=='IN_PROGRESS' and getattr(order,'procedure_id',None):staff.freeze(mod,order)
        if target=='EXAM_COMPLETED':
            result,_evidence=_rb.technician_completion_evidence(order)
            if not result['allowed']:
                from technician_image_policy import ImageCompletionDecision
                return ImageCompletionDecision(False,result['reason'],result),current
            _rb.audit('EXAM_COMPLETION_IMAGES_VERIFIED','order',order.id,_rb.json.dumps(result,sort_keys=True))
            if result['warning']: _rb.flash(result['warning'],'warning')

        # Reporting is an operational phase; it never reopens completed acquisition.
        from workflow_engine import acquisition_state_after_transition
        order.exam_status=acquisition_state_after_transition(target)
        if target=='REPORTING':
            _rb.audit('ACQUISITION_PRESERVED_FOR_REPORTING','order',order.id,
                  f'acquisition={order.exam_status}; reporting=STARTED')
        order.status=_rb.order_status_for_exam_transition(
            order.status,
            target,
        )

        if target=='IN_PROGRESS':
            order.exam_started_at=order.exam_started_at or _rb.datetime.utcnow()
        elif target=='EXAM_COMPLETED':
            order.exam_completed_at=order.exam_completed_at or _rb.datetime.utcnow()

        return decision,current
    return _apply_exam_transition


def install_0253(_rb):
    def current_ui_language():
        u=_rb.current_user()
        if u:
            p=_rb.UserProfile.query.filter_by(user_id=u.id).first()
            if p and p.ui_language in ('ar','en'):
                return p.ui_language
        lang=_rb.session.get('ui_lang','en')
        return lang if lang in ('ar','en') else 'en'
    return current_ui_language


def install_0305(_rb):
    def executive_analytics_filters():
        from datetime import date,timedelta,datetime as _dt
        today=date.today()
        try:start=_dt.strptime(_rb.request.args.get('start') or '','%Y-%m-%d').date()
        except Exception:start=today-timedelta(days=29)
        try:end=_dt.strptime(_rb.request.args.get('end') or '','%Y-%m-%d').date()
        except Exception:end=today
        if end<start:start,end=end,start
        return {
            'start':start,'end':end,
            'start_dt':_dt.combine(start,_dt.min.time()),
            'end_dt':_dt.combine(end+timedelta(days=1),_dt.min.time()),
            'branch_id':_rb.request.args.get('branch_id',type=int),
            'modality':(_rb.request.args.get('modality') or '').strip().upper(),
            'doctor_id':_rb.request.args.get('doctor_id',type=int),
            'device_id':_rb.request.args.get('device_id',type=int),
            'contract_id':_rb.request.args.get('contract_id',type=int),
        }
    return executive_analytics_filters


def install_0309(_rb):
    def management_date_range():
        from datetime import date,timedelta,datetime as _dt
        today=date.today()
        try: start=_dt.strptime(_rb.request.args.get('start') or '','%Y-%m-%d').date()
        except Exception: start=today-timedelta(days=29)
        try: end=_dt.strptime(_rb.request.args.get('end') or '','%Y-%m-%d').date()
        except Exception: end=today
        if end<start: start,end=end,start
        return start,end,_dt.combine(start,_dt.min.time()),_dt.combine(end+timedelta(days=1),_dt.min.time())
    return management_date_range


def install_0337(_rb):
    def safe_url_for_endpoint(endpoint):
        try:
            return _rb.url_for(endpoint)
        except Exception:
            return '#'
    return safe_url_for_endpoint


def install_0338(_rb):
    def common_search_filters():
        return {
            'q':(_rb.request.args.get('q') or '').strip(),
            'branch_id':_rb.request.args.get('branch_id',type=int),
            'modality':(_rb.request.args.get('modality') or '').strip().upper(),
            'priority':(_rb.request.args.get('priority') or '').strip().upper(),
            'has_priors':_rb.request.args.get('has_priors')=='1',
            'has_documents':_rb.request.args.get('has_documents')=='1',
        }
    return common_search_filters


def install_0411(_rb):
    def _rb_v5462_direct_attachments(patient,order=None,appointment=None):
        files=_rb.request.files.getlist('attachment_files')
        cats=_rb.request.form.getlist('attachment_categories')
        notes=_rb.request.form.getlist('attachment_notes')
        saved=[]
        allowed=('.pdf','.jpg','.jpeg','.png','.webp','.tif','.tiff',
                 '.doc','.docx','.odt','.dcm','.dicom','.zip')
        for i,f in enumerate(files):
            if not f or not f.filename: continue
            ext=_rb.os.path.splitext(f.filename)[1].lower()
            if ext not in allowed:
                raise ValueError(f'Unsupported attachment type: {f.filename}')
            cat=(cats[i] if i<len(cats) and cats[i] else 'OTHER').upper()
            note=(notes[i] if i<len(notes) else '').strip()
            ref=order.id if order else appointment.id if appointment else 'registration'
            folder=_rb.os.path.join(_rb.ATTACHMENT_DIR,str(patient.id),str(ref))
            _rb.os.makedirs(folder,exist_ok=True)
            stored=_rb.generated_attachment_filename(order.id if order else None,cat,f.filename)
            path=_rb.os.path.join(folder,stored)
            f.save(path); saved.append(path)
            _rb.db.session.add(_rb.Attachment(
                patient_id=patient.id,
                order_id=(order.id if order else None),
                appointment_id=(appointment.id if appointment else None),
                category=cat,original_name=f.filename,stored_path=path,
                mime_type=f.mimetype or '',notes=note,uploaded_by=_rb.current_user().id
            ))
        return saved
    return _rb_v5462_direct_attachments


def install_0412(_rb):
    def _rb_v5462_attach_ocr(patient,intake_id,order=None,appointment=None):
        if not intake_id: return
        intake=_rb.SmartIntakeSession.query.get(intake_id)
        if not intake: return
        chosen=set()
        for raw in (_rb.request.form.get('ocr_document_ids') or '').split(','):
            try: chosen.add(int(raw))
            except Exception: pass
        catmap={
          'IDENTITY':'IDENTITY','INSURANCE_CARD':'INSURANCE_CARD',
          'PRESCRIPTION':'PRESCRIPTION','APPROVAL':'APPROVAL',
          'PREVIOUS_REPORT':'PREVIOUS_REPORT','PREVIOUS_IMAGES':'PREVIOUS_IMAGES',
          'QUESTIONNAIRE':'QUESTIONNAIRE','CONSENT':'CONSENT'
        }
        for doc in _rb.SmartIntakeDocument.query.filter_by(intake_id=intake.id).all():
            if chosen and doc.id not in chosen: continue
            if doc.status=='REJECTED': continue
            doc.status='APPROVED'
            doc.reviewed_by=_rb.current_user().id
            doc.reviewed_at=_rb.datetime.utcnow()
            if not doc.review_notes:
                doc.review_notes='Accepted from unified registration workspace.'
            if not _rb.Attachment.query.filter_by(patient_id=patient.id,stored_path=doc.file_path).first():
                _rb.db.session.add(_rb.Attachment(
                    patient_id=patient.id,
                    order_id=(order.id if order else None),
                    appointment_id=(appointment.id if appointment else None),
                    category=catmap.get(doc.document_type,'OTHER'),
                    original_name=doc.original_name or f'OCR-{doc.id}',
                    stored_path=doc.file_path,mime_type=doc.mime_type or '',
                    notes='OCR intake document',uploaded_by=_rb.current_user().id
                ))
            if not doc.patient_document_id:
                pd=_rb.PatientDocument(
                    patient_id=patient.id,
                    order_id=(order.id if order else None),
                    document_type=doc.document_type or 'OTHER',
                    category='SMART_INTAKE',
                    file_path=doc.file_path,
                    original_name=doc.original_name or '',
                    extracted_text=doc.ocr_text or '',
                    extraction_status='COMPLETED' if doc.ocr_text else 'NOT_EXTRACTED',
                    review_status='APPROVED',
                    reviewer_id=_rb.current_user().id,
                    review_notes=doc.review_notes or '',
                    uploaded_by=_rb.current_user().id,
                    reviewed_at=_rb.datetime.utcnow()
                )
                _rb.db.session.add(pd); _rb.db.session.flush()
                doc.patient_document_id=pd.id
        intake.patient_id=patient.id
    return _rb_v5462_attach_ocr


def install_0463(_rb):
    def analytics_query():
        q=_rb.Order.query
        start=_rb.request.args.get('start','').strip()
        end=_rb.request.args.get('end','').strip()
        branch_id=_rb.request.args.get('branch_id',type=int)
        modality=_rb.request.args.get('modality','').strip()
        contract_id=_rb.request.args.get('contract_id',type=int)
        if start:
            q=q.filter(_rb.Order.scheduled >= _rb.datetime.fromisoformat(start))
        if end:
            q=q.filter(_rb.Order.scheduled < _rb.datetime.fromisoformat(end) + __import__('datetime').timedelta(days=1))
        if branch_id: q=q.filter(_rb.Order.branch_id==branch_id)
        if modality: q=q.filter(_rb.Order.modality==modality)
        if contract_id: q=q.filter(_rb.Order.contract_id==contract_id)
        return q
    return analytics_query


def install_0464(_rb):
    @_rb.require_perm('analytics.view')
    def analytics():
        q=_rb.analytics_query()
        rows=q.order_by(_rb.Order.scheduled.desc()).limit(5000).all()

        total=len(rows)
        gross=sum(float(x.contract_price or x.gross_price or 0) for x in rows)
        patient_share=sum(float(x.patient_share or 0) for x in rows)
        company_share=sum(float(x.company_share or 0) for x in rows)
        paid=sum(float(x.paid_amount or 0) for x in rows)
        outstanding=sum(max(_rb.order_balance(x),0) for x in rows)

        by_mod={}
        by_status={}
        by_proc={}
        by_branch={}
        for x in rows:
            mod=x.modality or 'OTHER'
            by_mod[mod]=by_mod.get(mod,0)+1

            status=x.status or 'UNKNOWN'
            by_status[status]=by_status.get(status,0)+1

            key=(x.proc.name if x.proc else x.procedure) or 'Unknown'
            by_proc[key]=by_proc.get(key,0)+1

            branch=(x.branch.name if x.branch else 'No Branch')
            by_branch[branch]=by_branch.get(branch,0)+1

        top_procs=sorted(by_proc.items(), key=lambda z:z[1], reverse=True)[:15]

        # Report turnaround time: scheduled study time -> final report time.
        tats=[]
        for x in rows:
            if x.report and x.report.finalized_at and x.scheduled:
                try:
                    hours=(x.report.finalized_at-x.scheduled).total_seconds()/3600.0
                    if hours >= 0:
                        tats.append(hours)
                except Exception:
                    pass
        avg_tat=(sum(tats)/len(tats)) if tats else 0.0

        # Consumables cost for the currently filtered orders.
        consumable_cost=0.0
        order_ids=[x.id for x in rows]
        if order_ids:
            usages=_rb.OrderConsumable.query.filter(_rb.OrderConsumable.order_id.in_(order_ids)).all()
            for u in usages:
                try:
                    consumable_cost += float(u.qty or 0) * float(u.consumable.unit_cost or 0)
                except Exception:
                    pass

        # Appointment statistics honor date / branch filters where applicable.
        aq=_rb.Appointment.query
        start=_rb.request.args.get('start','').strip()
        end=_rb.request.args.get('end','').strip()
        branch_id=_rb.request.args.get('branch_id',type=int)

        if start:
            aq=aq.filter(_rb.Appointment.scheduled >= _rb.datetime.fromisoformat(start))
        if end:
            aq=aq.filter(_rb.Appointment.scheduled < _rb.datetime.fromisoformat(end) + _rb.timedelta(days=1))
        if branch_id:
            aq=aq.filter(_rb.Appointment.branch_id == branch_id)

        appointment_stats={}
        for a in aq.all():
            status=a.status or 'UNKNOWN'
            appointment_stats[status]=appointment_stats.get(status,0)+1

        return _rb.render_template(
            'analytics.html',
            rows=rows,
            total=total,
            gross=gross,
            patient_share=patient_share,
            company_share=company_share,
            paid=paid,
            outstanding=outstanding,
            avg_tat=avg_tat,
            consumable_cost=consumable_cost,
            appointment_stats=appointment_stats,
            by_mod=sorted(by_mod.items()),
            by_status=sorted(by_status.items()),
            by_branch=sorted(by_branch.items(), key=lambda z:z[1], reverse=True),
            top_procs=top_procs,
            branches=_rb.Branch.query.order_by(_rb.Branch.name).all(),
            contracts=_rb.Contract.query.order_by(_rb.Contract.name).all()
        )
    return analytics


def install_0465(_rb):
    @_rb.require_perm('export.view')
    def analytics_export_csv():
        rows=_rb.analytics_query().order_by(_rb.Order.scheduled.desc()).all()
        s=_rb.io.StringIO(); w=_rb.csv.writer(s)
        w.writerow(['Accession','Patient ID','Patient','Scheduled','Branch','Modality','Procedure','Contract','Gross/Contract Price','Patient Share','Company Share','Paid','Status'])
        for x in rows:
            w.writerow([x.accession,x.patient.patient_id,x.patient.name,x.scheduled.isoformat(sep=' '),
                x.branch.name if x.branch else '',x.modality,x.proc.name if x.proc else x.procedure,
                x.contract.name if x.contract else 'Cash / Private',
                x.contract_price or x.gross_price or 0,x.patient_share or 0,x.company_share or 0,x.paid_amount or 0,x.status])
        return _rb.send_file(_rb.io.BytesIO(s.getvalue().encode('utf-8-sig')),as_attachment=True,
            download_name='ris-analytics.csv',mimetype='text/csv; charset=utf-8')
    return analytics_export_csv


def install_0576(_rb):
    def cancellation_reason():
        reason=(_rb.request.form.get('reason') or '').strip()
        if len(reason)<5:_rb.abort(400,'Cancellation reason must contain at least 5 characters.')
        return reason[:1000]
    return cancellation_reason


def install_0592(_rb):
    def granular_delete_ris_case_only_execute(order, typed_accession, reason):
        """Dependency-safe RIS Case Data Only execution.

    Preserves Patient, PACS images, reports/report files (reports must already be zero),
    attachments/documents, and audit history. The Order row is deleted last.
    """
        from sqlalchemy import inspect as _ris_inspect, text as _ris_text

        user=_rb.current_user()
        reason=str(reason or '').strip()
        typed_accession=str(typed_accession or '').strip()
        expected_accession=str(getattr(order,'accession','') or '').strip()

        if not _rb._delete_reports_only_is_super_admin(user):
            _rb.abort(403)
        if len(reason) < 5:
            return _rb._ris_case_only_blocked_response(order,reason,'REASON_REQUIRED',['REASON_REQUIRED'],400)
        if not typed_accession or typed_accession != expected_accession:
            return _rb._ris_case_only_blocked_response(
                order,reason,'ACCESSION_CONFIRMATION_MISMATCH',['ACCESSION_CONFIRMATION_MISMATCH'],409
            )

        initial_patient_id=int(getattr(order,'patient_id',0) or 0)
        if not initial_patient_id or _rb.db.session.get(_rb.Patient,initial_patient_id) is None:
            return _rb._ris_case_only_blocked_response(order,reason,'PATIENT_NOT_FOUND',['PATIENT_NOT_FOUND'],409)

        initial_dependencies=_rb._ris_case_only_dependency_rows(order)
        initial_reports=_rb.Report.query.filter_by(order_id=order.id).order_by(_rb.Report.id).all()
        initial_report_rows=[{'id':r.id,'status':getattr(r,'status',None)} for r in initial_reports]
        initial_preview=_rb.granular_delete_ris_case_only_execution_preview_snapshot(
            order,initial_dependencies,initial_report_rows
        )
        if not initial_preview.get('can_prepare_execution'):
            return _rb._ris_case_only_blocked_response(
                order,reason,'RIS_CASE_DATA_PREFLIGHT_BLOCKED',initial_preview.get('blockers') or ['PREFLIGHT_BLOCKED'],409
            )

        def _signature(preview):
            return tuple(sorted(
                (str(r.get('table') or ''),str(r.get('column') or ''),r.get('count'),
                 str(r.get('action') or ''),bool(r.get('blocking')))
                for r in (preview.get('rows') or [])
            ))

        initial_signature=_signature(initial_preview)
        pacs_before={
            'pacs_study_id':getattr(order,'pacs_study_id',None),
            'pacs_image_count':getattr(order,'pacs_image_count',None),
            'pacs_status':getattr(order,'pacs_status',None),
            'study_instance_uid':getattr(order,'study_instance_uid',None),
        }

        try:
            locked_order=(_rb.Order.query.filter_by(id=order.id).with_for_update().first())
            if locked_order is None:
                raise RuntimeError('ORDER_NOT_FOUND_AFTER_LOCK')
            if int(getattr(locked_order,'patient_id',0) or 0) != initial_patient_id:
                raise RuntimeError('PATIENT_CHANGED_AFTER_PREFLIGHT')
            locked_patient=_rb.db.session.get(_rb.Patient,initial_patient_id)
            if locked_patient is None:
                raise RuntimeError('PATIENT_NOT_FOUND_AFTER_LOCK')

            final_dependencies=_rb._ris_case_only_dependency_rows(locked_order)
            final_reports=_rb.Report.query.filter_by(order_id=locked_order.id).order_by(_rb.Report.id).with_for_update().all()
            final_report_rows=[{'id':r.id,'status':getattr(r,'status',None)} for r in final_reports]
            final_preview=_rb.granular_delete_ris_case_only_execution_preview_snapshot(
                locked_order,final_dependencies,final_report_rows
            )
            final_blockers=list(final_preview.get('blockers') or [])
            if _signature(final_preview) != initial_signature:
                final_blockers.append('DEPENDENCY_SET_CHANGED_AFTER_PREFLIGHT')
            if str(getattr(locked_order,'accession','') or '').strip() != expected_accession:
                final_blockers.append('ACCESSION_CHANGED_AFTER_PREFLIGHT')
            for key,value in pacs_before.items():
                if getattr(locked_order,key,None) != value:
                    final_blockers.append('PACS_LINK_STATE_CHANGED_AFTER_PREFLIGHT')
                    break
            final_blockers=list(dict.fromkeys(final_blockers))
            if final_blockers or not final_preview.get('can_prepare_execution'):
                _rb.db.session.rollback()
                return _rb._ris_case_only_blocked_response(
                    order,reason,'FINAL_REVALIDATION_BLOCKED',final_blockers or ['FINAL_PREFLIGHT_BLOCKED'],409
                )

            inspector=_ris_inspect(_rb.db.session.connection())
            preparer=_rb.db.engine.dialect.identifier_preparer
            table_names=set(inspector.get_table_names())

            # Expired report leases are stale operational locks. Active leases already block.
            expired_lease_deleted=0
            if 'report_edit_lease' in table_names:
                lease_result=_rb.db.session.execute(
                    _ris_text(
                        'DELETE FROM report_edit_lease WHERE order_id = :order_id AND expires_at <= :now'
                    ),
                    {'order_id':int(locked_order.id),'now':_rb.datetime.utcnow()},
                )
                expired_lease_deleted=max(int(getattr(lease_result,'rowcount',0) or 0),0)

            nullified={}
            deleted={}

            # Use ORM bulk DML for active mapped dependencies so the SQLAlchemy
            # identity map stays synchronized with the database. The executor may
            # be invoked in a session that already contains Attachment/ClinicalNote
            # instances (for example, tests or admin workflows). Raw SQL can leave
            # those instances stale even when the database row was changed.
            mapper_registry=getattr(_rb.db.Model,'registry',None)
            mapped_models={}
            if mapper_registry is not None:
                for mapper in mapper_registry.mappers:
                    mapped_table=getattr(mapper,'local_table',None)
                    mapped_name=getattr(mapped_table,'name',None)
                    if mapped_name:
                        mapped_models[str(mapped_name)]=mapper.class_

            for row in sorted(final_preview.get('rows') or [], key=lambda r:(str(r.get('table')),str(r.get('column')))):
                count=int(row.get('count') or 0)
                if not count:
                    continue
                table=str(row.get('table') or '')
                column=str(row.get('column') or '')
                action=str(row.get('action') or '')
                policy=_rb._RIS_CASE_ONLY_DEPENDENCY_POLICY.get((table,column))
                if policy is None or policy[1] != action:
                    raise RuntimeError('POLICY_CHANGED_DURING_EXECUTION')

                model=mapped_models.get(table)
                if model is None:
                    raise RuntimeError('ACTIVE_DEPENDENCY_MODEL_NOT_FOUND: '+table)
                model_column=getattr(model,column,None)
                if model_column is None:
                    raise RuntimeError('ACTIVE_DEPENDENCY_COLUMN_NOT_FOUND: '+table+'.'+column)

                # Mutate mapped rows as ORM instances instead of issuing bulk DML.
                # This keeps both scalar FK state and relationship/unit-of-work state
                # coherent when the request session already contains these objects.
                # The destructive admin path favors correctness and auditability over
                # bulk-DML speed; second-order FK checks already fail closed above.
                matched_rows=(
                    _rb.db.session.query(model)
                    .filter(model_column == int(locked_order.id))
                    .all()
                )
                affected=len(matched_rows)
                if affected != count:
                    raise RuntimeError(
                        'ACTION_ROWCOUNT_MISMATCH: '+table+'.'+column+
                        ': expected='+str(count)+', actual='+str(affected)
                    )

                if action == 'NULLIFY_ORDER_LINK':
                    for matched_row in matched_rows:
                        setattr(matched_row,column,None)
                    _rb.db.session.flush()
                    nullified[table+'.'+column]=affected
                elif action == 'DELETE_CASE_ROW':
                    for matched_row in matched_rows:
                        _rb.db.session.delete(matched_row)
                    _rb.db.session.flush()
                    deleted[table+'.'+column]=affected
                elif action == 'BLOCK':
                    raise RuntimeError('BLOCKING_DEPENDENCY_REACHED_EXECUTOR')

            _rb.db.session.flush()
            _rb.db.session.expire_all()

            remaining=_rb._ris_case_only_dependency_rows(locked_order)
            remaining_active=[
                r for r in remaining
                if r.get('count') is None or int(r.get('count') or 0) > 0
            ]
            if remaining_active:
                raise RuntimeError(
                    'DIRECT_DEPENDENCY_POSTCHECK_FAILED: '+','.join(
                        str(r.get('table'))+'.'+str(r.get('column')) for r in remaining_active
                    )
                )

            order_id=int(locked_order.id)
            patient_id=int(locked_patient.id)
            _rb.db.session.delete(locked_order)
            _rb.db.session.flush()

            if _rb.db.session.get(_rb.Order,order_id) is not None:
                raise RuntimeError('ORDER_DELETE_POSTCHECK_FAILED')
            if _rb.db.session.get(_rb.Patient,patient_id) is None:
                raise RuntimeError('PATIENT_PRESERVATION_POSTCHECK_FAILED')

            _rb.audit(
                'RIS_CASE_DATA_DELETED_ADMIN',
                'order',
                order_id,
                (
                    f"accession={expected_accession}; patient_id={patient_id}; "
                    f"nullified={sum(nullified.values())}; deleted_case_rows={sum(deleted.values())}; "
                    f"expired_leases_deleted={expired_lease_deleted}; "
                    f"pacs_study_id={pacs_before.get('pacs_study_id') or ''}; "
                    f"pacs_image_count={pacs_before.get('pacs_image_count') or 0}; "
                    f"reason={reason}"
                ),
            )
            _rb.db.session.commit()
            return {
                'ok':True,
                'deleted':True,
                'order_id':order_id,
                'accession':expected_accession,
                'patient_preserved':True,
                'pacs_images_preserved':True,
                'audit_history_preserved':True,
                'nullified_row_count':sum(nullified.values()),
                'deleted_case_row_count':sum(deleted.values()),
                'expired_lease_count_deleted':expired_lease_deleted,
                'nullified':nullified,
                'deleted_rows':deleted,
            },200
        except Exception as exc:
            _rb.db.session.rollback()
            try:
                _rb.audit(
                    'RIS_CASE_DATA_DELETE_FAILED_ADMIN','order',getattr(order,'id',''),
                    f"accession={expected_accession}; error={type(exc).__name__}; reason={reason}",
                )
                _rb.db.session.commit()
            except Exception:
                _rb.db.session.rollback()
            return {
                'ok':False,'deleted':False,'error':'RIS_CASE_DATA_DELETE_FAILED',
                'failure_type':type(exc).__name__,
            },500
    return granular_delete_ris_case_only_execute


def install_0603(_rb):
    def granular_delete_full_case_orchestration_execute(
        order,
        typed_accession,
        reason,
    ):
        """Execute the validated Full Case sequence with fail-closed staging.

    Required order: PACS Images Only -> Reports Only -> RIS Case Data Only.
    Each underlying executor retains its own final revalidation and audit trail.
    Successful irreversible stages are never silently rolled back or replayed.
    """
        user=_rb.current_user()
        if not _rb._delete_reports_only_is_super_admin(user):
            _rb.abort(403)

        reason=str(reason or '').strip()
        typed_accession=str(typed_accession or '').strip()
        accession=str(getattr(order,'accession','') or '').strip()
        order_id=int(order.id)
        patient_id=int(getattr(order,'patient_id',0) or 0)

        if not _rb._full_case_orchestration_execution_enabled():
            return _rb._full_case_orchestration_failure(
                order_id,accession,reason,'INITIAL_PREFLIGHT',
                'FULL_CASE_EXECUTION_DISABLED',409,
            )
        if len(reason) < 5:
            return _rb._full_case_orchestration_failure(
                order_id,accession,reason,'INITIAL_PREFLIGHT','REASON_REQUIRED',400,
            )
        if not accession or typed_accession != accession:
            return _rb._full_case_orchestration_failure(
                order_id,accession,reason,'INITIAL_PREFLIGHT',
                'ACCESSION_CONFIRMATION_MISMATCH',409,
            )
        if str(getattr(order,'status','') or '').strip().upper() not in ('CANCELLED','CANCELED'):
            return _rb._full_case_orchestration_failure(
                order_id,accession,reason,'INITIAL_PREFLIGHT','ORDER_NOT_CANCELLED',409,
            )
        if not patient_id or _rb.db.session.get(_rb.Patient,patient_id) is None:
            return _rb._full_case_orchestration_failure(
                order_id,accession,reason,'INITIAL_PREFLIGHT','PATIENT_NOT_FOUND',409,
            )

        initial_snapshot=_rb.granular_delete_order_preview_snapshot(order)
        plan=initial_snapshot.get('full_case_orchestration') or {}
        if not plan.get('can_execute_full_case'):
            return _rb._full_case_orchestration_failure(
                order_id,accession,reason,'INITIAL_PREFLIGHT',
                'FULL_CASE_PREFLIGHT_BLOCKED',409,
                details={'blockers':list(plan.get('blockers') or [])},
            )

        stage_map={
            str(row.get('code')):str(row.get('state'))
            for row in (plan.get('stages') or [])
        }
        completed=[]
        stage_results=[]

        try:
            _rb.audit(
                'FULL_CASE_DELETE_REQUESTED_ADMIN','order',order_id,
                (
                    f"accession={accession}; sequence=PACS_IMAGES_ONLY>REPORTS_ONLY>RIS_CASE_DATA_ONLY; "
                    f"reason={reason}"
                ),
            )
            _rb.db.session.commit()
        except Exception as exc:
            _rb.db.session.rollback()
            return _rb._full_case_orchestration_failure(
                order_id,accession,reason,'INITIAL_AUDIT',
                'FULL_CASE_REQUEST_AUDIT_FAILED',500,
                details={'failure_type':type(exc).__name__},
            )

        # Stage 1: PACS Images Only. COMPLETE/NOT_REQUIRED are explicit safe skips.
        pacs_state=stage_map.get('PACS_IMAGES_ONLY','BLOCKED')
        if pacs_state == 'READY':
            current=_rb.db.session.get(_rb.Order,order_id)
            if current is None:
                return _rb._full_case_orchestration_failure(
                    order_id,accession,reason,'PACS_IMAGES_ONLY','ORDER_DISAPPEARED',409,completed
                )
            result,status=_rb.granular_delete_images_only_execute(
                current,typed_accession,reason
            )
            stage_results.append({'stage':'PACS_IMAGES_ONLY','status':status,'result':result})
            if status != 200 or not result.get('ok'):
                return _rb._full_case_orchestration_failure(
                    order_id,accession,reason,'PACS_IMAGES_ONLY',
                    result.get('error') or 'PACS_IMAGES_STAGE_FAILED',status,completed,
                    details={'stage_result':result},
                )
            completed.append('PACS_IMAGES_ONLY')
        elif pacs_state in ('COMPLETE','NOT_REQUIRED'):
            completed.append('PACS_IMAGES_ONLY_SKIPPED_'+pacs_state)
            stage_results.append({'stage':'PACS_IMAGES_ONLY','status':200,'result':{'ok':True,'skipped':True,'state':pacs_state}})
        else:
            return _rb._full_case_orchestration_failure(
                order_id,accession,reason,'PACS_IMAGES_ONLY','PACS_STAGE_NOT_READY',409,completed,
                details={'state':pacs_state},
            )

        # Stage 2: Reports Only. Re-query after PACS stage; the underlying executor
        # performs its own locked final revalidation and same-filesystem quarantine.
        current=_rb.db.session.get(_rb.Order,order_id)
        if current is None:
            return _rb._full_case_orchestration_failure(
                order_id,accession,reason,'REPORTS_ONLY','ORDER_DISAPPEARED',409,completed
            )
        report_count=_rb.Report.query.filter_by(order_id=order_id).count()
        if report_count:
            result,status=_rb.granular_delete_reports_only_execute(
                current,typed_accession,reason
            )
            stage_results.append({'stage':'REPORTS_ONLY','status':status,'result':result})
            if status != 200 or not result.get('ok'):
                return _rb._full_case_orchestration_failure(
                    order_id,accession,reason,'REPORTS_ONLY',
                    result.get('error') or 'REPORTS_STAGE_FAILED',status,completed,
                    details={'stage_result':result},
                )
            completed.append('REPORTS_ONLY')
        else:
            completed.append('REPORTS_ONLY_SKIPPED_COMPLETE')
            stage_results.append({'stage':'REPORTS_ONLY','status':200,'result':{'ok':True,'skipped':True,'state':'COMPLETE'}})

        # Stage 3: RIS Case Data Only. This executor removes the Order last and
        # preserves Patient/Audit while requiring reports to be zero.
        current=_rb.db.session.get(_rb.Order,order_id)
        if current is None:
            return _rb._full_case_orchestration_failure(
                order_id,accession,reason,'RIS_CASE_DATA_ONLY','ORDER_DISAPPEARED',409,completed
            )
        result,status=_rb.granular_delete_ris_case_only_execute(
            current,typed_accession,reason
        )
        stage_results.append({'stage':'RIS_CASE_DATA_ONLY','status':status,'result':result})
        if status != 200 or not result.get('ok'):
            return _rb._full_case_orchestration_failure(
                order_id,accession,reason,'RIS_CASE_DATA_ONLY',
                result.get('error') or 'RIS_CASE_STAGE_FAILED',status,completed,
                details={'stage_result':result},
            )
        completed.append('RIS_CASE_DATA_ONLY')

        postcheck=_rb._full_case_orchestration_final_postcheck(order_id,patient_id)
        if not postcheck.get('ok'):
            return _rb._full_case_orchestration_failure(
                order_id,accession,reason,'FINAL_POSTCHECK',
                'FULL_CASE_FINAL_POSTCHECK_FAILED',500,completed,
                details={'postcheck':postcheck,'stage_results':stage_results},
            )

        try:
            _rb.audit(
                'FULL_CASE_DELETED_ADMIN','order',order_id,
                (
                    f"accession={accession}; patient_id={patient_id}; "
                    f"stages={','.join(completed)}; patient_preserved=yes; "
                    f"order_removed=yes; reports_zero=yes; reason={reason}"
                ),
            )
            _rb.db.session.commit()
        except Exception as exc:
            _rb.db.session.rollback()
            return {
                'ok':False,
                'deleted':True,
                'full_case_deleted':True,
                'order_id':order_id,
                'accession':accession,
                'completed_stages':completed,
                'stage_results':stage_results,
                'postcheck':postcheck,
                'error':'FINAL_AUDIT_FAILED_AFTER_DELETE',
                'failure_type':type(exc).__name__,
            },500

        return {
            'ok':True,
            'deleted':True,
            'full_case_deleted':True,
            'order_id':order_id,
            'accession':accession,
            'patient_id':patient_id,
            'patient_preserved':True,
            'audit_history_preserved':True,
            'pacs_images_deleted_or_not_required':True,
            'reports_deleted':True,
            'ris_case_deleted':True,
            'completed_stages':completed,
            'stage_results':stage_results,
            'postcheck':postcheck,
        },200
    return granular_delete_full_case_orchestration_execute


def install_0626(_rb):
    def correction_execution_http_error(
        exc,
    ):
        text=str(exc)

        if isinstance(exc,PermissionError):
            _rb.abort(403,text)

        if text in (
            'CORRECTION_EXECUTION_ALREADY_EXISTS',
            'CORRECTION_EXECUTION_STALE_VERSION',
            'CORRECTION_EXECUTION_STALE_SNAPSHOT',
            'CORRECTION_REQUEST_NO_LONGER_APPROVED',
        ):
            _rb.abort(409,text)

        _rb.abort(400,text)
    return correction_execution_http_error


def install_0726(_rb):
    def _saved_view_page_or_404(page_key):
        key=(page_key or '').strip().upper()
        if key not in _rb.SAVED_VIEW_PAGES:
            _rb.abort(404)
        from staff_worklist_filters import page_access
        page_access(_rb._reporting_support_sys.modules[_rb.__name__],key)
        return key
    return _saved_view_page_or_404


def install_0838(_rb):
    def _apply_discovered_node_policy(row,payload):
        if not _rb.dicom_ingress_policy_ready():
            _rb.abort(409,description='Orthanc ingress enforcement is not verified')
        # Never take over a pre-existing or independently administered modality.
        previous=_rb._managed_dicom_modality(row.id)
        if previous is not None and previous.get('AET')!=row.ae_title:
            _rb.abort(409,description='Managed modality identity changed in Orthanc')
        if payload is not None:
            response=_rb.requests.get(f'{_rb.PACS_ORTHANC_URL}/modalities?expand',
                                  auth=_rb._orthanc_auth(),timeout=10)
            response.raise_for_status()
            for key,other in response.json().items():
                if key!=_rb.modality_key(row.id) and other.get('AET')==payload['AET']:
                    _rb.abort(409,description='AE Title already belongs to another modality')
        elif previous is None:
            _rb.abort(409,description='Node is not registered under RadBridge control')
        try:
            _rb._write_managed_dicom_modality(row.id,payload)
            if payload is None:
                row.status='BLOCKED'
                _rb.audit('DICOM_INGRESS_BLOCK','discovered_dicom_node',row.id,
                      f'{row.ae_title}@{row.host}')
            else:
                row.ae_title=payload['AET'];row.host=payload['Host'];row.port=payload['Port']
                row.status='APPROVED';row.approved_at=_rb.datetime.utcnow()
                row.approved_by=_rb.current_user().id
                _rb.audit('DICOM_INGRESS_APPROVE','discovered_dicom_node',row.id,
                      f'{row.ae_title}@{row.host};find={payload["AllowFind"]};store={payload["AllowStore"]}')
            _rb.db.session.commit()
        except Exception:
            _rb.db.session.rollback()
            try:
                _rb._write_managed_dicom_modality(row.id,previous)
            except Exception as rollback_error:
                _rb.app.logger.critical('DICOM node rollback failed for id %s: %s',row.id,rollback_error)
            raise
    return _apply_discovered_node_policy
