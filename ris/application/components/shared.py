"""Runtime-bound application.components.shared; dependencies are supplied at composition.

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


def install_0001(_rb):
    def _validate_production_secrets():
        if _rb.RADBRIDGE_ENV != 'production':
            return
        weak = []
        if not _rb.app.secret_key or _rb.app.secret_key == 'change-me-now':
            weak.append('SECRET_KEY')
        if not _rb.ORTHANC_PASSWORD or _rb.ORTHANC_PASSWORD == 'ChangeMe_PACS_2026':
            weak.append('ORTHANC_PASSWORD')
        if weak:
            raise RuntimeError(
                'Unsafe production configuration: set strong values for ' + ', '.join(weak)
            )
    return _validate_production_secrets


def install_0004(_rb):
    def lang():
        try:
            return _rb.current_ui_language()
        except Exception:
            v=_rb.session.get('ui_lang') or _rb.session.get('lang') or 'en'
            return v if v in ('en','ar') else 'en'
    return lang


def install_0005(_rb):
    def tr(key):
        return _rb.I18N.get(_rb.lang(), _rb.I18N['en']).get(key,key)
    return tr


def install_0006(_rb):
    def _active_portal_token(order):
        now=_rb.datetime.utcnow()
        row=_rb.PortalAccessToken.query.filter_by(order_id=order.id,revoked=False).filter(
            _rb.PortalAccessToken.expires_at>now
        ).order_by(_rb.PortalAccessToken.id.desc()).first()
        if row:
            return row.token
        token=_rb.secrets.token_urlsafe(32)
        _rb.db.session.add(_rb.PortalAccessToken(
            order_id=order.id,
            token=token,
            expires_at=now+_rb.timedelta(days=_rb.PATIENT_PORTAL_TOKEN_DAYS),
            revoked=False
        ))
        _rb.db.session.flush()
        return token
    return _active_portal_token


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


def install_0013(_rb):
    def exam_transition_allowed(current,target):
        return _rb.can_transition('SUPER_ADMIN',current,target,override=False).allowed
    return exam_transition_allowed


def install_0016(_rb):
    def _money(v):
        try:return round(float(v or 0),2)
        except:return 0.0
    return _money


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


def install_0026(_rb):
    def get_company_profile():
        row=_rb.CompanyProfile.query.first()
        if not row:
            row=_rb.CompanyProfile();_rb.db.session.add(row);_rb.db.session.flush()
        return row
    return get_company_profile


def install_0027(_rb):
    def get_default_sticker_template():
        row=_rb.StickerTemplate.query.filter_by(is_default=True,active=True).first()
        if not row:
            row=_rb.StickerTemplate(name='Patient Sticker Bilingual',active=True,is_default=True,
                width_mm=_rb.STICKER_DEFAULT_WIDTH_MM,height_mm=_rb.STICKER_DEFAULT_HEIGHT_MM,bilingual=True,
                fields_json=_rb.json.dumps(_rb.DEFAULT_STICKER_FIELDS),
                labels_json=_rb.json.dumps(_rb.DEFAULT_STICKER_LABELS,ensure_ascii=False))
            _rb.db.session.add(row);_rb.db.session.flush()
        return row
    return get_default_sticker_template


def install_0028(_rb):
    def _sticker_fields(t):
        try:return _rb.json.loads(t.fields_json or '[]') or _rb.DEFAULT_STICKER_FIELDS
        except:return _rb.DEFAULT_STICKER_FIELDS
    return _sticker_fields


def install_0029(_rb):
    def _sticker_labels(t):
        try:
            x=_rb.json.loads(t.labels_json or '{}')
            return {**_rb.DEFAULT_STICKER_LABELS,**x}
        except:return _rb.DEFAULT_STICKER_LABELS
    return _sticker_labels


def install_0030(_rb):
    def _sticker_value(order,key):
        p=order.patient
        return str({
          'patient_name':p.name,'patient_id':p.patient_id,'accession':order.accession,
          'exam':(order.proc.name if order.proc else order.procedure),
          'datetime':order.scheduled.strftime('%d/%m/%Y %H:%M') if order.scheduled else '',
          'branch':order.branch.name if order.branch else '',
          'modality':order.modality or '','phone':p.phone or '','worklist_name':p.worklist_name or ''
        }.get(key,'') or '')
    return _sticker_value


def install_0031(_rb):
    def _portal_url_for_order(order):
        token=_rb._active_portal_token(order);_rb.db.session.flush()
        return _rb.RIS_PUBLIC_URL+_rb.url_for('patient_portal',token=token)
    return _portal_url_for_order


def install_0034(_rb):
    def _study_tags(st):
        mt=st.get('MainDicomTags') or {};pt=st.get('PatientMainDicomTags') or {}
        return {'study_id':st.get('ID',''),'accession':str(mt.get('AccessionNumber','') or ''),
          'study_date':str(mt.get('StudyDate','') or ''),
          'modality':str(mt.get('ModalitiesInStudy') or mt.get('Modality') or ''),
          'patient_id':str(pt.get('PatientID','') or ''),'patient_name':str(pt.get('PatientName','') or ''),
          'dob':str(pt.get('PatientBirthDate','') or ''),
          'sex':str(pt.get('PatientSex','') or '').strip().upper()[:1],
          'instances':len(st.get('Instances') or [])}
    return _study_tags


def install_0039(_rb):
    def _study_tags_extended(st):
        tags=_rb._study_tags(st)
        mt=st.get('MainDicomTags') or {}
        detail=_rb._orthanc_study_detail(tags['study_id']) if tags.get('study_id') else {}
        dmt=detail.get('MainDicomTags') or {}
        source_ae=''
        if detail:
            for series_id in detail.get('Series',[]):
                series=_rb._orthanc_series_detail(series_id)
                instances=series.get('Instances') or []
                if instances:
                    source_ae=_rb._orthanc_instance_remote_aet(instances[0])
                    if source_ae:
                        break
        tags.update({
          'study_instance_uid':str(mt.get('StudyInstanceUID') or dmt.get('StudyInstanceUID') or ''),
          'study_description':str(mt.get('StudyDescription') or dmt.get('StudyDescription') or ''),
          # RemoteAET is authoritative for routing. StationName and InstitutionName
          # describe the acquisition device/site and must not select an intake center.
          'source_ae':str(source_ae or mt.get('StationName') or mt.get('InstitutionName') or ''),
        })
        if detail:
            tags['instances']=sum(len((_rb._orthanc_series_detail(x).get('Instances') or [])) for x in detail.get('Series',[]))
        return tags
    return _study_tags_extended


def install_0047(_rb):
    def approve_discovered_node(row,branch_id=None,node_type=None,port=None,notes=''):
        row.status='APPROVED'
        row.branch_id=branch_id or row.branch_id
        row.node_type=(node_type or row.node_type or 'MODALITY').upper()
        if port:
            row.port=int(port)
        row.notes=notes or row.notes
        row.approved_at=_rb.datetime.utcnow()
        row.approved_by=(_rb.current_user().id if _rb.current_user() else None)
        # Register as a destination only when there is enough routing information.
        if row.host and row.port and row.port>0:
            key=_rb.re.sub(r'[^a-z0-9_-]','-',row.ae_title.lower())[:60]
            dest=_rb.DicomDestination.query.filter_by(key=key).first()
            if not dest:
                dest=_rb.DicomDestination(
                    key=key,name=row.ae_title,ae_title=row.ae_title,host=row.host,port=row.port,
                    destination_type=('WORKSTATION' if row.node_type=='VIEWER' else 'MODALITY'),
                    branch_id=row.branch_id,active=True,allow_manual_send=True)
                _rb.db.session.add(dest);_rb.db.session.flush()
            else:
                dest.ae_title=row.ae_title;dest.host=row.host;dest.port=row.port
                dest.branch_id=row.branch_id;dest.active=True
            try:
                _rb.sync_destination_to_orthanc(dest)
            except Exception:
                pass
        return row
    return approve_discovered_node


def install_0049(_rb):
    def enqueue_transfer(order,study_id,destination,reason='MANUAL',created_by=None):
        # Auto-routing is idempotent, but MANUAL/RESEND must always create a fresh job.
        # This lets a technician deliberately resend the same study to the same target.
        if str(reason or '').upper()=='AUTO_ROUTE':
            existing=_rb.PacsTransferJob.query.filter_by(
              orthanc_study_id=study_id,destination_id=destination.id,status='SUCCESS',reason='AUTO_ROUTE').first()
            if existing:return existing
        total=int(getattr(order,'pacs_image_count',0) or 0) if order else 0
        job=_rb.PacsTransferJob(order_id=(order.id if order else None),orthanc_study_id=study_id,
          destination_id=destination.id,reason=reason,status='PENDING',created_by=created_by,
          progress_total=total,progress_sent=0)
        _rb.db.session.add(job);_rb.db.session.flush();return job
    return enqueue_transfer


def install_0050(_rb):
    def enqueue_auto_routes_for_inbox(inbox):
        if not inbox.order_id:return 0
        order=_rb.Order.query.get(inbox.order_id);count=0
        for rule in _rb.PacsRoutingRule.query.filter_by(active=True).all():
            if rule.branch_id and order.branch_id!=rule.branch_id:continue
            if rule.modality and str(order.modality or '').upper()!=str(rule.modality).upper():continue
            if rule.source_ae and str(order.station_ae or '').upper()!=str(rule.source_ae).upper():continue
            if not rule.destination or not rule.destination.active:continue
            _rb.enqueue_transfer(order,inbox.orthanc_study_id,rule.destination,'AUTO_ROUTE')
            count+=1
        return count
    return enqueue_auto_routes_for_inbox


def install_0053(_rb):
    def workflow_command_snapshot():
        now=_rb.datetime.utcnow()
        no_images=[];unassigned=[];assignment_delay=[];problems=[]
        rows=_rb.Order.query.filter(_rb.Order.status.notin_(['FINAL','CANCELLED'])).order_by(_rb.Order.scheduled.desc()).limit(800).all()
        for o in rows:
            image_count=int(o.pacs_image_count or 0)
            if o.exam_completed_at and image_count<=0 and now-o.exam_completed_at>_rb.timedelta(minutes=10):
                no_images.append(o);problems.append((o,'EXAM COMPLETED / NO IMAGES','CRITICAL' if now-o.exam_completed_at>_rb.timedelta(minutes=30) else 'WARNING'))
            if image_count>0 and not o.assigned_doctor_id:
                unassigned.append(o)
                ref=o.pacs_last_seen_at or o.exam_completed_at or o.scheduled
                if ref and now-ref>_rb.timedelta(minutes=5):
                    assignment_delay.append(o);problems.append((o,'IMAGES RECEIVED / NOT ASSIGNED','WARNING'))
            if str(o.pacs_status or '').upper()=='PACS_OFFLINE':
                problems.append((o,'PACS OFFLINE','CRITICAL'))
        return {'orders':rows,'no_images':no_images,'unassigned':unassigned,'assignment_delay':assignment_delay,
          'problems':problems,'pacs_online':_rb.orthanc_ok()}
    return workflow_command_snapshot


def install_0054(_rb):
    def doctor_can_take_open_case(user,order):
        if not user or not user.role or user.role.code not in ('RADIOLOGIST','DOCTOR'):return False,'NOT_RADIOLOGIST'
        if order.assigned_doctor_id and order.assigned_doctor_id!=user.id:return False,'ALREADY_ASSIGNED'
        if not _rb.readiness_allows_auto_assign(order):return False,'CASE_NOT_READY'
        policy=_rb.assignment_offer_policy()
        if policy:
            eligible=[u.id for u in _rb.assignment_candidate_users(order,policy)]
            if user.id not in eligible:return False,'NOT_ELIGIBLE_BY_ASSIGNMENT_RULES'
        return True,'OK'
    return doctor_can_take_open_case


def install_0056(_rb):
    def enqueue_event(event_type,entity_type='',entity_id='',payload=None):
        row=_rb.EventOutbox(
            event_type=str(event_type or '').upper(),
            entity_type=str(entity_type or ''),
            entity_id=str(entity_id or ''),
            payload_json=_rb.json.dumps(payload or {},ensure_ascii=False),
            status='PENDING',
            attempts=0
        )
        _rb.db.session.add(row)
        return row
    return enqueue_event


def install_0057(_rb):
    def pending_outbox_events(limit=100):
        return _rb.EventOutbox.query.filter_by(status='PENDING').order_by(_rb.EventOutbox.id.asc()).limit(limit).all()
    return pending_outbox_events


def install_0068(_rb):
    def _hhmm_minutes(value):
        try:
            h,m=[int(x) for x in value.split(':',1)]
            return h*60+m
        except Exception:
            return 0
    return _hhmm_minutes


def install_0069(_rb):
    def generate_slots(device, proc, day):
        schedule=_rb.DeviceSchedule.query.filter_by(device_id=device.id,weekday=day.weekday(),active=True).first()
        if not schedule:
            return []
        duration=max(5,int(proc.duration_min or 20))
        start=_rb._hhmm_minutes(schedule.start_time)
        end=_rb._hhmm_minutes(schedule.end_time)
        break_start=_rb._hhmm_minutes(schedule.break_start) if schedule.break_start else None
        break_end=_rb._hhmm_minutes(schedule.break_end) if schedule.break_end else None
        slots=[]
        cursor=start
        while cursor+duration<=end:
            st=_rb.datetime.combine(day,_rb.datetime.min.time())+_rb.timedelta(minutes=cursor)
            en=st+_rb.timedelta(minutes=duration)
            if break_start is not None and break_end is not None and cursor < break_end and cursor+duration > break_start:
                cursor=max(cursor+duration,break_end)
                continue
            blocked=_rb.DeviceBlock.query.filter(
                _rb.DeviceBlock.device_id==device.id,
                _rb.DeviceBlock.start_at < en,
                _rb.DeviceBlock.end_at > st
            ).first() is not None
            booked=_rb.Appointment.query.filter(
                _rb.Appointment.device_id==device.id,
                _rb.Appointment.status.in_(['BOOKED','CONFIRMED','ARRIVED']),
                _rb.Appointment.scheduled >= st,
                _rb.Appointment.scheduled < en
            ).first() is not None
            slots.append({'start':st,'end':en,'label':f'{st:%H:%M} - {en:%H:%M}','available':not blocked and not booked})
            cursor += duration
        return slots
    return generate_slots


def install_0070(_rb):
    def _safe_token(value):
        value=str(value or '').strip()
        value=_rb.re.sub(r'[^A-Za-z0-9_-]+','_',value)
        return value.strip('_') or 'NA'
    return _safe_token


def install_0073(_rb):
    def _error_id():
        return 'ERR-' + _rb.datetime.utcnow().strftime('%y%m%d-%H%M%S') + '-' + _rb.secrets.token_hex(2).upper()
    return _error_id


def install_0080(_rb):
    def audit_as_user(user, action, entity='', entity_id='', details=''):
        """Write an audit event explicitly attributed to a verified user."""
        _rb.db.session.add(_rb.AuditLog(
            user_id=(user.id if user else None),
            username=(user.username if user else 'SYSTEM'),
            action=action,
            entity=entity,
            entity_id=str(entity_id or ''),
            details=str(details or '')[:4000],
            ip=_rb._security_audit_ip()
        ))
    return audit_as_user


def install_0089(_rb):
    def latest_final_version(report):
        return _rb.ReportVersion.query.filter_by(report_id=report.id,action='UPLOAD_FINAL').order_by(
            _rb.ReportVersion.version_no.desc()).first()
    return latest_final_version


def install_0093(_rb):
    def _normalize_compare(value):
        return _rb.re.sub(r'[^A-Za-z0-9]+','',str(value or '')).upper()
    return _normalize_compare


def install_0094(_rb):
    def detect_labeled_value(text, labels):
        if not text:
            return ''
        for label in labels:
            m=_rb.re.search(
                rf'{label}\s*[:#\-]?\s*([A-Za-z0-9._/\-]+)',
                text,
                flags=_rb.re.I
            )
            if m:
                return m.group(1).strip()
        return ''
    return detect_labeled_value


def install_0096(_rb):
    def _csv_values(value):
        return {x.strip().upper() for x in str(value or '').split(',') if x.strip()}
    return _csv_values


def install_0098(_rb):
    def doctor_active_case_count(user_id):
        return _rb.Order.query.filter(
            _rb.Order.assigned_doctor_id==user_id,
            _rb.Order.status.notin_(['FINAL','CANCELLED'])
        ).count()
    return doctor_active_case_count


def install_0099(_rb):
    def eligible_doctors_for_order(order):
        profiles=_rb.DoctorAssignmentProfile.query.filter_by(auto_assign=True,available=True).all()
        eligible=[]
        for p in profiles:
            user=p.user
            if not user or not getattr(user,'active',True):
                continue
            from clinical_scope import allowed as clinical_scope_allowed
            if not clinical_scope_allowed(_rb._reporting_support_sys.modules[__name__],user,order):continue
            modalities=_rb._csv_values(p.modalities)
            branches=_rb._csv_values(p.branches)
            specialties=_rb._csv_values(p.specialties)

            if modalities and str(order.modality or '').upper() not in modalities:
                continue
            if branches and str(order.branch_id or '').upper() not in branches:
                continue

            active_count=_rb.doctor_active_case_count(user.id)
            if active_count >= int(p.max_active_cases or 20):
                continue

            eligible.append((p,user,active_count))
        return eligible
    return eligible_doctors_for_order


def install_0102(_rb):
    def arabic_to_latin_name(value):
        value=str(value or '').strip()
        out=[]
        for ch in value:
            if ch in _rb.ARABIC_NAME_MAP:
                out.append(_rb.ARABIC_NAME_MAP[ch])
            elif ch.isascii():
                out.append(ch)
            elif ch.isspace():
                out.append(' ')
        return _rb.re.sub(r'\s+',' ',' '.join(''.join(out).split())).strip().upper()
    return arabic_to_latin_name


def install_0103(_rb):
    def normalized_worklist_name(original_name, manual_value=''):
        """Return a Latin, human-editable name suitable for DICOM MWL."""
        candidate=str(manual_value or '').replace('^',' ').strip()
        if not candidate:
            candidate=_rb.arabic_to_latin_name(original_name)
        elif _rb.re.search(r'[\u0600-\u06FF]',candidate):
            candidate=_rb.arabic_to_latin_name(candidate)
        candidate=_rb.re.sub(r"[^A-Za-z0-9 '\-]+",' ',candidate)
        return _rb.re.sub(r'\s+',' ',candidate).strip().upper()
    return normalized_worklist_name


def install_0107(_rb):
    def normalized_person_name(value):
        return _rb.re.sub(r'[^A-Z0-9\u0600-\u06FF]+','',str(value or '').upper())
    return normalized_person_name


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


def install_0113(_rb):
    def audit(action, entity='', entity_id='', details=''):
        u=_rb.current_user()
        _rb.db.session.add(_rb.AuditLog(user_id=(u.id if u else None), username=(u.username if u else 'SYSTEM'),
            action=action, entity=entity, entity_id=str(entity_id or ''), details=details[:4000],
            ip=_rb._security_audit_ip()))
    return audit


def install_0120(_rb):
    def _rb_calendar_redirect(scheduled=None,branch_id=None,device_id=None):
        kw={}
        if scheduled is not None: kw['date']=scheduled.date().isoformat()
        if branch_id: kw['branch_id']=branch_id
        if device_id: kw['device_id']=device_id
        return _rb.redirect(_rb.url_for('schedule_calendar',**kw))
    return _rb_calendar_redirect


def install_0121(_rb):
    def new_accession():
        # DICOM AccessionNumber is VR SH and must not exceed 16 characters.
        # RB + YYMMDDHH + 6 random hex chars = exactly 16 characters.
        return 'RB' + _rb.datetime.now().strftime('%y%m%d%H') + _rb.secrets.token_hex(3).upper()
    return new_accession


def install_0124(_rb):
    def route_device(branch_id, modality):
        rows=_rb.Device.query.filter_by(branch_id=branch_id,modality=modality,active=True).order_by(_rb.Device.priority.asc(),_rb.Device.id.asc()).all()
        for d in rows:
            if getattr(d,'booking_enabled',True) and (getattr(d,'operational_status','ACTIVE') or 'ACTIVE').upper()=='ACTIVE':
                return d
        return None
    return route_device


def install_0125(_rb):
    def price_order(proc, contract):
        gross=float(proc.base_price or 0)
        if not contract:
            return gross,gross,gross,0.0,0.0
        cp=_rb.ContractPrice.query.filter_by(contract_id=contract.id,procedure_id=proc.id).first()
        effective=float(cp.price if cp else gross*(1-(contract.discount_percent or 0)/100.0))
        share_pct=float(cp.patient_share_percent if cp and cp.patient_share_percent is not None else contract.patient_share_percent or 0)
        patient=round(effective*share_pct/100.0,2)
        company=round(effective-patient,2)
        return gross,effective,patient,company,share_pct
    return price_order


def install_0129(_rb):
    def next_version(report):
        last=_rb.ReportVersion.query.filter_by(report_id=report.id).order_by(_rb.ReportVersion.version_no.desc()).first()
        return (last.version_no+1) if last else 1
    return next_version


def install_0130(_rb):
    def add_version(order,report,action,docx_path=None,pdf_path=None,change_summary=''):
        u=_rb.current_user()
        role=(u.role.code if u and u.role else 'SYSTEM')
        path=pdf_path or docx_path or report.pdf_path or report.docx_path or report.source_path
        digest='';size=0
        if path and _rb.os.path.exists(path):
            try:
                import hashlib
                h=hashlib.sha256()
                with open(path,'rb') as f:
                    for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
                digest=h.hexdigest();size=_rb.os.path.getsize(path)
            except Exception:pass
        _rb.db.session.add(_rb.ReportVersion(report_id=report.id,accession=order.accession,version_no=_rb.next_version(report),
            action=action,findings=report.findings or '',impression=report.impression or '',
            radiologist=report.radiologist or '',docx_path=docx_path,pdf_path=pdf_path,
            created_by=(u.id if u else None),created_role=role,change_summary=change_summary,
            sha256=digest,file_size=size))
    return add_version


def install_0131(_rb):
    def make_docx(order, report=None):
        doc=_rb.Document(); doc.add_heading('RADIOLOGY REPORT',0)
        t=doc.add_table(rows=6,cols=2)
        vals=[('Patient',order.patient.name),('Patient ID',order.patient.patient_id),('Accession',order.accession),
              ('Study',f'{order.modality} - {order.procedure}'),('Branch',order.branch.name if order.branch else ''),
              ('Date',order.scheduled.strftime('%Y-%m-%d %H:%M'))]
        for row,(a,b) in zip(t.rows,vals): row.cells[0].text=a; row.cells[1].text=b
        doc.add_paragraph(f'RIS_ACCESSION: {order.accession}')
        doc.add_heading('FINDINGS',level=1); doc.add_paragraph((report.findings if report else '') or '\n\n')
        doc.add_heading('IMPRESSION',level=1); doc.add_paragraph((report.impression if report else '') or '\n\n')
        doc.add_paragraph('\nRadiologist: '+((report.radiologist if report else '') or '____________________'))
        buf=_rb.io.BytesIO(); doc.save(buf); buf.seek(0); return buf
    return make_docx


def install_0132(_rb):
    def make_pdf(order, report, path):
        c=_rb.canvas.Canvas(path,pagesize=_rb.A4); w,h=_rb.A4; y=h-55
        c.setFont('Helvetica-Bold',16); c.drawString(55,y,'RADIOLOGY REPORT'); y-=35
        c.setFont('Helvetica',10)
        for line in [f'Patient: {order.patient.name}',f'Patient ID: {order.patient.patient_id}',f'Accession: {order.accession}',
                     f'Study: {order.modality} - {order.procedure}',f'Radiologist: {report.radiologist}']:
            c.drawString(55,y,line[:110]); y-=17
        for title,content in [('FINDINGS',report.findings or ''),('IMPRESSION',report.impression or '')]:
            y-=10; c.setFont('Helvetica-Bold',11); c.drawString(55,y,title); y-=18; c.setFont('Helvetica',10)
            for para in content.splitlines() or ['']:
                for i in range(0,max(1,len(para)),95):
                    if y<70: c.showPage(); y=h-55; c.setFont('Helvetica',10)
                    c.drawString(55,y,para[i:i+95]); y-=14
        c.save()
    return make_pdf


def install_0133(_rb):
    def extract_docx_sections(path):
        doc=_rb.Document(path); lines=[p.text.strip() for p in doc.paragraphs]
        findings=[]; impression=[]; radiologist=''; section=None
        for line in lines:
            up=line.upper()
            if up=='FINDINGS': section='findings'; continue
            if up=='IMPRESSION': section='impression'; continue
            if up.startswith('RIS_ACCESSION:'): continue
            if up.startswith('RADIOLOGIST:'):
                radiologist=line.split(':',1)[1].strip() if ':' in line else ''; section=None; continue
            if section=='findings': findings.append(line)
            elif section=='impression': impression.append(line)
        return '\n'.join(findings).strip(),'\n'.join(impression).strip(),radiologist
    return extract_docx_sections


def install_0134(_rb):
    def save_uploaded_word(order, report, file_storage, action):
        """
    Deprecated legacy clinical writer.

    All report content must use commit_report_version().
    Verification and finalization must use the canonical
    report state-transition service.
    """
        raise RuntimeError(
            'LEGACY_REPORT_WRITER_DISABLED'
        )
    return save_uploaded_word


def install_0135(_rb):
    def case_json(order,report):
        latest_version = _rb._rb_latest_report_version(report)

        return {
            'version_no': (
                int(latest_version.version_no)
                if latest_version
                else 0
            ),'id':order.id,'accession':order.accession,
          'patient':{'id':order.patient.patient_id,'name':order.patient.name,'dob':order.patient.dob,'sex':order.patient.sex},
          'modality':order.modality,'procedure':order.procedure,'scheduled':order.scheduled.isoformat(),
          'order_status':order.status,
          'report':{'status':report.status,'findings':report.findings or '','impression':report.impression or '',
                    'radiologist':report.radiologist or '','updated_at':report.updated_at.isoformat() if report.updated_at else None},
          'pacs_url':_rb.ORTHANC_PUBLIC_URL,'template_url':f'{_rb.RIS_PUBLIC_URL}/reports/{order.id}/word'}
    return case_json


def install_0137(_rb):
    def ui_phrase(text, language=None):
        from ui_localization import translate
        return translate(text, language or _rb.current_ui_language())
    return ui_phrase


def install_0138(_rb):
    def flash(message, category='message'):
        # Structured workflow messages keep their evidence payload intact.
        return _rb._flask_flash(_rb.ui_phrase(message) if isinstance(message, str) else message, category)
    return flash


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


def install_0140(_rb):
    def inject_language():
        return {'ui_lang':_rb.lang(),'t':_rb.tr}
    return inject_language


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
        mod=_rb._reporting_support_sys.modules[__name__]
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
        mod=_rb._reporting_support_sys.modules[__name__]
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


def install_0200(_rb):
    def normalize_doctor_worklist_layout(payload):
        payload=payload if isinstance(payload,dict) else {}
        allowed=set(_rb.DOCTOR_WORKLIST_COLUMN_KEYS)
        order=[]
        order_input=payload.get('order') if isinstance(payload.get('order'),list) else []
        for key in order_input:
            if isinstance(key,str) and key in allowed and key not in order:
                order.append(key)
        order.extend(key for key in _rb.DOCTOR_WORKLIST_COLUMN_KEYS if key not in order)
        visible=[]
        visible_input=payload.get('visible') if isinstance(payload.get('visible'),list) else []
        for key in visible_input:
            if key in allowed and key not in visible:
                visible.append(key)
        if not visible:
            visible=['priority','accession','patient_worklist','procedure','modality',
                     'images','pacs_status','report_status','sla_status','action']
        widths={}
        widths_input=payload.get('widths') if isinstance(payload.get('widths'),dict) else {}
        for key,value in widths_input.items():
            if key in allowed and isinstance(value,(int,float)):
                widths[key]=max(72,min(520,int(value)))
        pinned=[]
        pinned_input=payload.get('pinned') if isinstance(payload.get('pinned'),list) else []
        for key in pinned_input:
            if key in allowed and key in visible and key not in pinned:
                pinned.append(key)
        density=payload.get('density') if payload.get('density') in ('compact','comfortable') else 'compact'
        return {'version':2,'order':order,'visible':visible,'widths':widths,
                'pinned':pinned[:3],'density':density}
    return normalize_doctor_worklist_layout


def install_0202(_rb):
    def doctor_workspace_user(user):
        return bool(user and user.active and user.role and user.role.code.upper() in
            ('RADIOLOGIST','DOCTOR','CONSULTANT','RADIOLOGY_CONSULTANT','SUPER_ADMIN','ADMIN'))
    return doctor_workspace_user


def install_0203(_rb):
    def doctor_case_access_allowed(user,order):
        if not user or not user.active or not order:
            return False
        if not _rb.doctor_workspace_user(user):
            return False
        from clinical_scope import allowed as clinical_scope_allowed
        if not clinical_scope_allowed(_rb._reporting_support_sys.modules[__name__],user,order):
            return False
        role=(user.role.code if user.role else '').upper()
        if role in ('SUPER_ADMIN','ADMIN'):
            return True
        return order.assigned_doctor_id==user.id
    return doctor_case_access_allowed


def install_0235(_rb):
    def _hhmm_to_minutes(value,default):
        try:
            h,m=[int(x) for x in str(value or default).split(':',1)]
            return h*60+m
        except Exception:
            h,m=[int(x) for x in default.split(':',1)]
            return h*60+m
    return _hhmm_to_minutes


def install_0248(_rb):
    def dictionary_label(key,lang='en',fallback=''):
        row=_rb.DictionaryEntry.query.filter_by(key=key,active=True).first()
        if not row:return fallback or key
        return row.label_ar if lang=='ar' and row.label_ar else row.label_en or fallback or key
    return dictionary_label


def install_0249(_rb):
    def seed_dictionary_and_ribbon():
        for key,module,en,ar in _rb.DEFAULT_DICTIONARY:
            if not _rb.DictionaryEntry.query.filter_by(key=key).first():
                _rb.db.session.add(_rb.DictionaryEntry(key=key,module=module,label_en=en,label_ar=ar,active=True))
        for key,en,ar,icon,route,perm,ctx,order_no in _rb.DEFAULT_RIBBON_ACTIONS:
            if not _rb.RibbonAction.query.filter_by(action_key=key).first():
                _rb.db.session.add(_rb.RibbonAction(action_key=key,label_en=en,label_ar=ar,icon=icon,route_name=route,required_permission=perm,context=ctx,order_no=order_no,active=True))
        _rb.db.session.commit()
    return seed_dictionary_and_ribbon


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


def install_0254(_rb):
    def ui_text(key,fallback=''):
        lang=_rb.current_ui_language()
        row=_rb.DictionaryEntry.query.filter_by(key=key,active=True).first()
        if row:
            return (row.label_ar or row.label_en or fallback or key) if lang=='ar' else (row.label_en or fallback or key)
        d=_rb.DEFAULT_UI_MAP.get(key)
        if d:
            return d['ar'] if lang=='ar' else d['en']
        return fallback or key
    return ui_text


def install_0255(_rb):
    def status_text(value):
        value=str(value or '').upper()
        return _rb.ui_text('status.'+value,value.replace('_',' ').title())
    return status_text


def install_0256(_rb):
    def seed_full_ui_dictionary():
        added=0
        for key,module,en,ar in _rb.DEFAULT_UI_DICTIONARY:
            if not _rb.DictionaryEntry.query.filter_by(key=key).first():
                _rb.db.session.add(_rb.DictionaryEntry(key=key,module=module,label_en=en,label_ar=ar,active=True))
                added+=1
        if added:
            _rb.db.session.commit()
        return added
    return seed_full_ui_dictionary


def install_0257(_rb):
    def ribbon_actions_for_user(user=None,context='GLOBAL'):
        user=user or _rb.current_user()
        if not user:
            return []
        actions=_rb.RibbonAction.query.filter_by(active=True).order_by(_rb.RibbonAction.order_no).all()
        custom={x.ribbon_action_id:x for x in _rb.UserRibbonAction.query.filter_by(user_id=user.id).all()}
        out=[]
        for a in actions:
            if a.context not in ('GLOBAL',context):
                continue
            if a.required_permission and not _rb.has_perm(a.required_permission):
                continue
            c=custom.get(a.id)
            if c and not c.visible:
                continue
            out.append({
                'action':a,
                'order_no':c.order_no if c else a.order_no
            })
        return sorted(out,key=lambda x:x['order_no'])
    return ribbon_actions_for_user


def install_0258(_rb):
    def ensure_journey(order,stage='REGISTERED',notes=''):
        stage=(stage or 'REGISTERED').upper()
        cur=_rb.JourneyEvent.query.filter_by(order_id=order.id,completed_at=None).order_by(_rb.JourneyEvent.id.desc()).first()
        if cur and cur.stage==stage:return cur
        if cur:cur.completed_at=_rb.datetime.utcnow()
        ev=_rb.JourneyEvent(order_id=order.id,stage=stage,user_id=(_rb.current_user().id if _rb.current_user() else None),notes=notes or '')
        _rb.db.session.add(ev);return ev
    return ensure_journey


def install_0259(_rb):
    def journey_snapshot(order):
        # Journey is a projection, not an independently writable lifecycle.
        evs=_rb.JourneyEvent.query.filter_by(order_id=order.id).order_by(_rb.JourneyEvent.entered_at).all()
        report=getattr(order,'report',None)
        stage=_rb.derive_journey_stage(
            order_status=order.status,
            exam_status=order.exam_status,
            pacs_status=order.pacs_status,
            pacs_image_count=order.pacs_image_count,
            report_status=(report.status if report else 'UNREPORTED'),
            report_delivered=bool(order.report_delivered),
            images_delivered=bool(order.images_delivered),
        )

        cur=next((x for x in reversed(evs) if x.completed_at is None and x.stage==stage),None)

        entered_at=None
        if cur:
            entered_at=cur.entered_at
        elif stage=='TECHNICIAN':
            entered_at=order.exam_started_at
        elif stage=='EXAM_DONE':
            entered_at=order.exam_completed_at
        elif stage=='PACS_RECEIVED':
            entered_at=order.pacs_last_seen_at
        elif stage in ('REPORTING','FINALIZED') and report:
            entered_at=(report.finalized_at if stage=='FINALIZED' else report.updated_at)
        elif stage=='DELIVERED':
            entered_at=order.report_delivered_at or order.images_delivered_at
        else:
            entered_at=order.created_at or order.scheduled

        return {
            'events':evs,
            'current':cur,
            'stage':stage,
            'entered_at':entered_at,
        }
    return journey_snapshot


def install_0260(_rb):
    def role_dashboard_kind(user=None):
        user=user or _rb.current_user();code=(user.role.code if user and user.role else '').upper()
        if code=='RECEPTION':return 'RECEPTION'
        if code=='TECHNICIAN':return 'TECHNICIAN'
        if code in ('RADIOLOGIST','DOCTOR'):return 'DOCTOR'
        if code=='CASHIER':return 'CASHIER'
        if code in ('NURSE','NURSING'):return 'NURSING'
        return 'MANAGEMENT'
    return role_dashboard_kind


def install_0262(_rb):
    def get_or_create_case_thread(order):
        row=_rb.ChatThread.query.filter_by(thread_type='CASE',order_id=order.id,active=True).first()
        if not row:
            row=_rb.ChatThread(thread_type='CASE',title=f'Case {order.accession}',order_id=order.id,created_by=(_rb.current_user().id if _rb.current_user() else None));_rb.db.session.add(row);_rb.db.session.flush()
        if _rb.current_user():_rb.ensure_chat_member(row,_rb.current_user().id)
        return row
    return get_or_create_case_thread


def install_0265(_rb):
    def normalize_phone(v):
        x=_rb.re.sub(r'\D','',v or '')
        if x.startswith('0020'): x=x[2:]
        if x.startswith('20') and len(x)>10: x='0'+x[2:]
        return x
    return normalize_phone


def install_0267(_rb):
    def document_timeline(patient):
        events=[]
        for o in _rb.Order.query.filter_by(patient_id=patient.id).order_by(_rb.Order.id.desc()).all():
            dt=getattr(o,'scheduled',None) or getattr(o,'created_at',None)
            events.append({'kind':'EXAM','date':dt,'title':getattr(o,'procedure','Examination'),'order':o})
        for d in _rb.PatientDocument.query.filter_by(patient_id=patient.id).order_by(_rb.PatientDocument.created_at.desc()).all():
            label=_rb.DOCUMENT_TYPES.get(d.document_type,(d.document_type,d.document_type,'OTHER'))
            events.append({'kind':'DOCUMENT','date':d.created_at,'title':label[1] if _rb.current_ui_language()=='ar' else label[0],'document':d})
        events.sort(key=lambda x:x['date'] or _rb.datetime.min,reverse=True)
        return events
    return document_timeline


def install_0268(_rb):
    def extract_document_text_basic(path):
        # Safe local baseline. PDF/image OCR engine can be configured later.
        ext=_rb.os.path.splitext(path)[1].lower()
        if ext=='.txt':
            try:
                return open(path,'r',encoding='utf-8',errors='ignore').read()[:100000],'DONE'
            except Exception:
                return '','FAILED'
        return '','OCR_REQUIRED'
    return extract_document_text_basic


def install_0269(_rb):
    def build_document_matches(doc):
        _rb.DocumentMatch.query.filter_by(document_id=doc.id).delete()
        text=(doc.extracted_text or '').lower()
        p=doc.patient
        candidates=[
          ('patient_name',p.name or ''),
          ('national_id',getattr(p,'national_id','') or ''),
          ('phone',p.phone or '')
        ]
        if doc.order:
            candidates.append(('examination',getattr(doc.order,'procedure','') or ''))
        for field,value in candidates:
            if not value: continue
            hit=str(value).lower() in text if text else False
            _rb.db.session.add(_rb.DocumentMatch(document_id=doc.id,field_name=field,extracted_value=(value if hit else ''),ris_value=str(value),confidence=(1.0 if hit else 0.0),match_status=('MATCH' if hit else 'REVIEW')))
    return build_document_matches


def install_0270(_rb):
    def seed_v521_functional_defaults():
        for key,en,ar,dtype,minl,maxl,exact,required,visible in _rb.DEFAULT_V521_FIELD_RULES:
            row=_rb.FieldRule.query.filter_by(field_key=key).first()
            if not row:
                _rb.db.session.add(_rb.FieldRule(
                    field_key=key,label_en=en,label_ar=ar,data_type=dtype,
                    min_length=minl,max_length=maxl,exact_length=exact,
                    required=required,visible=visible,read_only=False,allow_spaces=True,
                    regex_pattern=r'\S+(?:\s+\S+){2,}' if key=='patient.name' else None
                ))
        _rb.db.session.commit()
    return seed_v521_functional_defaults


def install_0271(_rb):
    def studio_shortcut_context():
        u=_rb.current_user()
        return {'user_id':getattr(u,'id',None),'branch_id':getattr(u,'branch_id',None)}
    return studio_shortcut_context


def install_0279(_rb):
    def safe_export_name(value):
        return _rb.re.sub(r'[^A-Za-z0-9._-]+','_',str(value or 'export')).strip('_')[:100] or 'export'
    return safe_export_name


def install_0280(_rb):
    def destructive_confirmation_token(action,count=0):
        action=(action or '').upper().replace('_',' ')
        return f'{action} {int(count or 0)}'.strip()
    return destructive_confirmation_token


def install_0286(_rb):
    def next_transfer_no():
        prefix=_rb.datetime.utcnow().strftime('TR%Y%m%d')
        last=_rb.StockTransfer.query.filter(_rb.StockTransfer.transfer_no.like(prefix+'%')).order_by(_rb.StockTransfer.id.desc()).first()
        n=1
        if last:
            try:n=int(last.transfer_no[-4:])+1
            except Exception:n=last.id+1
        return f'{prefix}{n:04d}'
    return next_transfer_no


def install_0303(_rb):
    def performing_doctor_for_order(order):
        row=_rb.OrderPerformingDoctor.query.filter_by(order_id=order.id).first()
        if row:return row.doctor
        assignment=_rb.CaseAssignment.query.filter_by(order_id=order.id,active=True).first()
        return assignment.doctor if assignment else None
    return performing_doctor_for_order


def install_0304(_rb):
    def performing_doctor_share_for_order(order):
        from replacement_settlements import effective_share
        frozen=effective_share(_rb._reporting_support_sys.modules[__name__],order)
        if frozen is not None:return frozen
        doctor=_rb.performing_doctor_for_order(order)
        if not doctor:return 0.0,None,None
        candidates=[]
        for r in _rb.PerformingDoctorShareRule.query.filter_by(doctor_user_id=doctor.id,active=True).all():
            if r.branch_id and r.branch_id!=order.branch_id: continue
            if r.modality and r.modality!=order.modality: continue
            if r.procedure_id and r.procedure_id!=order.procedure_id: continue
            if r.contract_id and r.contract_id!=order.contract_id: continue
            score=(8 if r.procedure_id else 0)+(4 if r.contract_id else 0)+(2 if r.modality else 0)+(1 if r.branch_id else 0)
            candidates.append((score,r))
        if not candidates:return 0.0,None,doctor
        rule=sorted(candidates,key=lambda x:x[0],reverse=True)[0][1]
        if rule.basis=='GROSS': base=float(order.gross_price or 0)
        elif rule.basis=='CONTRACT': base=float(order.contract_price or order.gross_price or 0)
        else: base=_rb.effective_patient_due(order)
        value=float(rule.value or 0)
        share=base*value/100.0 if rule.rule_type=='PERCENT' else value
        return round(share,2),rule,doctor
    return performing_doctor_share_for_order


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


def install_0306(_rb):
    def executive_orders(filters):
        q=_rb.Order.query.filter(_rb.Order.scheduled>=filters['start_dt'],_rb.Order.scheduled<filters['end_dt'])
        if filters['branch_id']:q=q.filter(_rb.Order.branch_id==filters['branch_id'])
        if filters['modality']:q=q.filter(_rb.Order.modality==filters['modality'])
        if filters['doctor_id']:q=q.filter(_rb.Order.assigned_doctor_id==filters['doctor_id'])
        if filters['device_id']:q=q.filter(_rb.Order.device_id==filters['device_id'])
        if filters['contract_id']:q=q.filter(_rb.Order.contract_id==filters['contract_id'])
        return q.order_by(_rb.Order.scheduled).all()
    return executive_orders


def install_0307(_rb):
    def _chart_rows(counter,label_lookup=None,limit=None):
        items=list(counter.items())
        items.sort(key=lambda x:x[1],reverse=True)
        if limit:items=items[:limit]
        return [{'label':(label_lookup.get(k,k) if label_lookup else k),'value':v} for k,v in items]
    return _chart_rows


def install_0308(_rb):
    def executive_analytics_payload(filters):
        from collections import defaultdict
        from datetime import timedelta
        orders=_rb.executive_orders(filters)
        order_ids=[o.id for o in orders]
        total=len(orders)
        revenue=sum(float(o.contract_price or o.gross_price or 0) for o in orders)
        paid=sum(float(o.paid_amount or 0) for o in orders)
        completed=sum(1 for o in orders if str(o.exam_status or o.status or '').upper() in ('COMPLETED','DONE','FINAL','REPORTED'))
        completion_rate=round(completed*100/total,1) if total else 0

        new_patients=_rb.Patient.query.filter(_rb.Patient.created_at>=filters['start_dt'],_rb.Patient.created_at<filters['end_dt']).count()
        reports={}
        if order_ids:
            reports={r.order_id:r for r in _rb.Report.query.filter(_rb.Report.order_id.in_(order_ids)).all()}
        tats=[]
        status_counts=defaultdict(int);modality_counts=defaultdict(int);branch_counts=defaultdict(int)
        doctor_counts=defaultdict(int);device_counts=defaultdict(int);daily_counts=defaultdict(int);daily_revenue=defaultdict(float)

        for o in orders:
            day=o.scheduled.strftime('%Y-%m-%d')
            daily_counts[day]+=1
            daily_revenue[day]+=float(o.contract_price or o.gross_price or 0)
            modality_counts[o.modality or 'OTHER']+=1
            branch_counts[o.branch_id or 0]+=1
            doctor_counts[o.assigned_doctor_id or 0]+=1
            device_counts[o.device_id or 0]+=1
            status_counts[str(o.exam_status or o.status or 'UNKNOWN').upper()]+=1
            rp=reports.get(o.id)
            if rp and rp.finalized_at and o.scheduled:
                mins=(rp.finalized_at-o.scheduled).total_seconds()/60
                if mins>=0:tats.append(mins)

        avg_tat=round(sum(tats)/len(tats),1) if tats else 0

        branches={b.id:b.name for b in _rb.Branch.query.all()}
        doctors={u.id:(u.full_name or u.username) for u in _rb.User.query.all()}
        devices={d.id:d.name for d in _rb.Device.query.all()}
        branches[0]='Unassigned';doctors[0]='Unassigned';devices[0]='Unassigned'

        # Fill every date so the line chart has no gaps.
        d=filters['start']
        daily=[];rev_daily=[]
        while d<=filters['end']:
            key=d.isoformat()
            daily.append({'label':key[5:],'value':daily_counts.get(key,0)})
            rev_daily.append({'label':key[5:],'value':round(daily_revenue.get(key,0),2)})
            d+=timedelta(days=1)

        return {
            'kpi':{
                'total_exams':total,'new_patients':new_patients,'avg_tat':avg_tat,
                'completion_rate':completion_rate,'revenue':round(revenue,2),'paid':round(paid,2)
            },
            'daily_exams':daily,
            'daily_revenue':rev_daily,
            'modalities':_rb._chart_rows(modality_counts),
            'branches':_rb._chart_rows(branch_counts,branches),
            'doctors':_rb._chart_rows(doctor_counts,doctors,8),
            'devices':_rb._chart_rows(device_counts,devices,8),
            'statuses':_rb._chart_rows(status_counts),
        }
    return executive_analytics_payload


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


def install_0310(_rb):
    def management_orders_query(start_dt,end_dt):
        return _rb.Order.query.filter(_rb.Order.scheduled>=start_dt,_rb.Order.scheduled<end_dt)
    return management_orders_query


def install_0311(_rb):
    def management_summary(start_dt,end_dt):
        orders=_rb.management_orders_query(start_dt,end_dt).all()
        total=len(orders); finalized=assigned=urgent=delayed=0
        revenue=patient_share=company_share=0.0
        branch_counts={}; modality_counts={}; referrer_counts={}; tat_values=[]
        for o in orders:
            revenue+=float(getattr(o,'contract_price',0) or getattr(o,'gross_price',0) or 0)
            patient_share+=float(getattr(o,'patient_share',0) or 0)
            company_share+=float(getattr(o,'company_share',0) or 0)
            branch_counts[o.branch_id]=branch_counts.get(o.branch_id,0)+1
            modality_counts[o.modality or 'OTHER']=modality_counts.get(o.modality or 'OTHER',0)+1
            if o.referring_doctor_id:
                referrer_counts[o.referring_doctor_id]=referrer_counts.get(o.referring_doctor_id,0)+1
            if getattr(o,'priority','ROUTINE') in ('URGENT','STAT'): urgent+=1
            if _rb.CaseAssignment.query.filter_by(order_id=o.id,active=True).first(): assigned+=1
            rp=_rb.Report.query.filter_by(order_id=o.id).order_by(_rb.Report.id.desc()).first()
            if rp and str(rp.status or '').upper()=='FINAL': finalized+=1
            try:
                snap=_rb.case_delay_snapshot(o)
                if snap.get('overdue'): delayed+=1
                if snap.get('total_min') is not None: tat_values.append(float(snap.get('total_min') or 0))
            except Exception: pass
        return {
          'total':total,'finalized':finalized,'assigned':assigned,'unassigned':max(0,total-assigned),
          'urgent':urgent,'delayed':delayed,'revenue':revenue,'patient_share':patient_share,
          'company_share':company_share,'avg_tat':(sum(tat_values)/len(tat_values) if tat_values else 0),
          'branch_counts':branch_counts,'modality_counts':modality_counts,'referrer_counts':referrer_counts
        }
    return management_summary


def install_0314(_rb):
    def studio_shortcuts_for(placement,context=None):
        context=context or {}
        u=_rb.current_user()
        q=_rb.StudioShortcut.query.filter_by(active=True,placement=placement.upper())
        rows=q.order_by(_rb.StudioShortcut.sort_order,_rb.StudioShortcut.id).all()
        out=[]
        for x in rows:
            if x.user_id and (not u or x.user_id!=u.id): continue
            if x.branch_id and getattr(u,'branch_id',None)!=x.branch_id: continue
            if x.permission_code and not _rb.has_perm(x.permission_code): continue
            if x.role_code and getattr(u,'role','')!=x.role_code: continue
            target=x.target or ''
            values={
              'order_id':context.get('order_id',''),
              'patient_id':context.get('patient_id',''),
              'accession':context.get('accession',''),
              'user_id':getattr(u,'id','') if u else '',
              'branch_id':getattr(u,'branch_id','') if u else ''
            }
            for key,val in values.items():
                target=target.replace('{'+key+'}',str(val))
            # Do not render a context shortcut if its required object is absent.
            if ('{order_id}' in (x.target or '') and not context.get('order_id')) or \
               ('{patient_id}' in (x.target or '') and not context.get('patient_id')):
                continue
            out.append((x,target,_rb.STUDIO_ICON_MAP.get(x.icon,'🔗')))
        return out
    return studio_shortcuts_for


def install_0325(_rb):
    def company_legal_for_order(order):
        row=_rb.CompanyLegalProfile.query.filter_by(branch_id=getattr(order,'branch_id',None)).first()
        if row: return row
        return _rb.CompanyLegalProfile.query.filter(_rb.CompanyLegalProfile.branch_id.is_(None)).first()
    return company_legal_for_order


def install_0326(_rb):
    def replace_docx_placeholders(doc,values):
        def replace_in_paragraph(p):
            full=''.join(r.text for r in p.runs)
            changed=full
            for k,v in values.items():
                changed=changed.replace('{{'+k+'}}',str(v or ''))
            if changed!=full:
                if p.runs:
                    p.runs[0].text=changed
                    for r in p.runs[1:]: r.text=''
                else:
                    p.add_run(changed)
        for p in doc.paragraphs:
            replace_in_paragraph(p)
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    for p in cell.paragraphs:
                        replace_in_paragraph(p)
        for section in doc.sections:
            for p in section.header.paragraphs:
                replace_in_paragraph(p)
            for p in section.footer.paragraphs:
                replace_in_paragraph(p)
        return doc
    return replace_docx_placeholders


def install_0327(_rb):
    def ai_provider_setting():
        return _rb.AIProviderSetting.query.filter_by(enabled=True).order_by(_rb.AIProviderSetting.id).first()
    return ai_provider_setting


def install_0328(_rb):
    def related_prior_orders(order,limit=20):
        q=_rb.Order.query.filter(_rb.Order.patient_id==order.patient_id,_rb.Order.id!=order.id)
        if order.modality:
            q=q.filter(_rb.Order.modality==order.modality)
        return q.order_by(_rb.Order.scheduled.desc(),_rb.Order.id.desc()).limit(limit).all()
    return related_prior_orders


def install_0329(_rb):
    def external_priors_for_order(order):
        q=_rb.ExternalPriorStudy.query.filter_by(patient_id=order.patient_id)
        if order.modality:
            q=q.filter(_rb.or_(_rb.ExternalPriorStudy.modality=='',_rb.ExternalPriorStudy.modality==order.modality))
        return q.order_by(_rb.ExternalPriorStudy.study_date.desc(),_rb.ExternalPriorStudy.created_at.desc()).limit(50).all()
    return external_priors_for_order


def install_0331(_rb):
    def score_prior_match(patient,meta):
        if not meta: return 0.0,'REVIEW'
        score=0.0
        checks=0
        if meta.get('patient_id'):
            checks+=1
            if str(meta['patient_id']).strip()==str(patient.patient_id or '').strip(): score+=0.45
        if meta.get('patient_name'):
            checks+=1
            a=_rb.re.sub(r'\s+',' ',str(meta['patient_name']).lower()).strip()
            b=_rb.re.sub(r'\s+',' ',str(patient.name or '').lower()).strip()
            if a==b: score+=0.35
            elif a and b and (a in b or b in a): score+=0.20
        if meta.get('dob') and getattr(patient,'dob',None):
            checks+=1
            if str(meta['dob']).replace('-','')==str(patient.dob).replace('-',''): score+=0.20
        if score>=0.75: return score,'MATCH'
        if score<=0.20 and checks>=2: return score,'MISMATCH'
        return score,'REVIEW'
    return score_prior_match


def install_0332(_rb):
    def selected_prior_context(order):
        rows=_rb.PriorStudySelection.query.filter_by(order_id=order.id,include_in_ai=True).all()
        out=[]
        for x in rows:
            if x.prior_order_id:
                p=_rb.Order.query.get(x.prior_order_id)
                if p:
                    r=_rb.get_report(p)
                    out.append({'type':'RIS_PRIOR','date':str(p.scheduled or ''),'accession':p.accession,
                      'procedure':p.procedure,'findings':r.findings if r else '','impression':r.impression if r else ''})
            elif x.external_prior_id:
                p=_rb.ExternalPriorStudy.query.get(x.external_prior_id)
                if p:
                    out.append({'type':'EXTERNAL_PRIOR','date':str(p.study_date or ''),
                      'modality':p.modality,'description':p.study_description,'match_status':p.match_status})
        return out
    return selected_prior_context


def install_0333(_rb):
    def generate_ai_draft_payload(order):
        return {
          'instructions':(
            'Generate a radiology report DRAFT for physician review only. '
            'Use only the supplied clinical context and selected prior reports. '
            'Do not claim to have reviewed images unless image-derived findings are explicitly supplied. '
            'Return Findings, Impression, Comparison, and Safety Notes. '
            'Flag uncertainty and contradictions. Never finalize the report.'
          ),
          'case':_rb.ai_case_context(order)
        }
    return generate_ai_draft_payload


def install_0335(_rb):
    def quick_action_role(user=None):
        user=user or _rb.current_user()
        code=(user.role.code if user and user.role else '').upper()
        if code in ('RECEPTION','FRONT_DESK'): return 'RECEPTION'
        if code=='CASHIER': return 'CASHIER'
        if code in ('TECHNICIAN','TECH'): return 'TECHNICIAN'
        if code in ('NURSE','NURSING'): return 'NURSING'
        if code in ('RADIOLOGIST','DOCTOR'): return 'DOCTOR'
        return 'MANAGEMENT'
    return quick_action_role


def install_0336(_rb):
    def role_quick_actions(user=None):
        return _rb.ROLE_QUICK_ACTION_PRESETS.get(_rb.quick_action_role(user), _rb.ROLE_QUICK_ACTION_PRESETS['MANAGEMENT'])
    return role_quick_actions


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


def install_0341(_rb):
    def render_comm_text(text,ctx):
        out=str(text or '')
        for k,v in ctx.items():
            out=out.replace('{{'+str(k)+'}}',str(v or ''))
        return out
    return render_comm_text


def install_0347(_rb):
    def normalize_person_name(v):
        return _rb.re.sub(r'\s+',' ',str(v or '').replace('^',' ').strip().lower())
    return normalize_person_name


def install_0348(_rb):
    def normalize_date(v):
        return _rb.re.sub(r'\D','',str(v or ''))[:8]
    return normalize_date


def install_0349(_rb):
    def demographic_verification(order,pacs_meta):
        checks=[]
        score=0.0
        weight_total=0.0

        def add(name,risv,dicomv,weight,normalizer=lambda x:str(x or '').strip()):
            nonlocal score,weight_total
            a=normalizer(risv); b=normalizer(dicomv)
            if not a or not b:
                checks.append({'field':name,'ris':str(risv or ''),'dicom':str(dicomv or ''),'status':'MISSING'})
                return
            weight_total+=weight
            ok=(a==b)
            if ok: score+=weight
            checks.append({'field':name,'ris':str(risv or ''),'dicom':str(dicomv or ''),'status':'MATCH' if ok else 'MISMATCH'})

        add('Patient ID',order.patient.patient_id,pacs_meta.get('patient_id'),0.40,lambda x:str(x or '').strip())
        add('Patient Name',order.patient.name,pacs_meta.get('patient_name'),0.20,_rb.normalize_person_name)
        add('DOB',getattr(order.patient,'dob',''),pacs_meta.get('patient_birth_date'),0.20,_rb.normalize_date)
        add('Sex',getattr(order.patient,'sex',''),pacs_meta.get('patient_sex'),0.05,lambda x:str(x or '').strip().upper())
        add('Accession',order.accession,pacs_meta.get('accession'),0.15,lambda x:str(x or '').strip().upper())

        pct=(score/weight_total) if weight_total else 0.0
        hard_mismatch=any(x['field'] in ('Patient ID','DOB','Accession') and x['status']=='MISMATCH' for x in checks)
        if hard_mismatch:
            status='BLOCKED'
        elif pct>=0.90:
            status='VERIFIED'
        elif pct>=0.65:
            status='REVIEW_REQUIRED'
        else:
            status='BLOCKED'
        return {'status':status,'score':pct,'checks':checks}
    return demographic_verification


def install_0353(_rb):
    def ai_case_context(order):
        # Extend v5.22 context with verified image-derived findings only.
        notes=_rb.ClinicalNote.query.filter_by(order_id=order.id).order_by(_rb.ClinicalNote.created_at).all()
        imaging=_rb.latest_verified_imaging_analysis(order)
        ctx={
          'patient':{'name':order.patient.name,'patient_id':order.patient.patient_id,
                     'dob':str(order.patient.dob or ''),'sex':order.patient.sex or ''},
          'study':{'accession':order.accession,'modality':order.modality,'procedure':order.procedure,
                   'scheduled':str(order.scheduled or ''),'priority':order.priority or ''},
          'clinical_notes':[{'type':n.note_type,'text':n.text} for n in notes],
          'selected_priors':_rb.selected_prior_context(order)
        }
        if imaging:
            ctx['verified_image_ai']={
              'provider':imaging.provider_key,
              'model':imaging.model_name,
              'structured_findings':_rb.json.loads(imaging.structured_findings_json or '{}'),
              'summary':imaging.summary_text,
              'uncertainty':imaging.uncertainty_text
            }
        return ctx
    return ai_case_context


def install_0357(_rb):
    def doctor_is_online(user,minutes=5):
        st=_rb.doctor_availability(user)
        return bool(st.last_seen_at and st.last_seen_at >= _rb.datetime.utcnow()-_rb.timedelta(minutes=minutes) and st.state!='OFFLINE')
    return doctor_is_online


def install_0362(_rb):
    def case_return_snapshot(order_id):
        # RB_UNIFIED_ASSIGNMENT_DASHBOARD_STATE_V1
        latest_return=(
            _rb.CaseWorkflowEvent.query
            .filter_by(order_id=order_id,event_type='RETURNED')
            .order_by(_rb.CaseWorkflowEvent.created_at.desc(),_rb.CaseWorkflowEvent.id.desc())
            .first()
        )
        if not latest_return:
            return {
                'open':False,
                'return_event':None,
                'resolution_event':None,
                'owner':'',
                'reason':''
            }

        latest_resolution=(
            _rb.CaseWorkflowEvent.query
            .filter(
                _rb.CaseWorkflowEvent.order_id==order_id,
                _rb.CaseWorkflowEvent.event_type.in_(
                    ['RESOLVED','READY_FOR_REREVIEW']
                )
            )
            .order_by(
                _rb.CaseWorkflowEvent.created_at.desc(),
                _rb.CaseWorkflowEvent.id.desc()
            )
            .first()
        )

        resolved=bool(
            latest_resolution and (
                latest_resolution.created_at > latest_return.created_at
                or (
                    latest_resolution.created_at == latest_return.created_at
                    and latest_resolution.id > latest_return.id
                )
            )
        )

        return {
            'open':not resolved,
            'return_event':latest_return,
            'resolution_event':latest_resolution if resolved else None,
            'owner':latest_return.owner_role or '',
            'reason':latest_return.reason_code or ''
        }
    return case_return_snapshot


def install_0363(_rb):
    def case_return_is_open(order_id):
        return _rb.case_return_snapshot(order_id)['open']
    return case_return_is_open


def install_0368(_rb):
    def seed_quality_defaults():
        if _rb.ProcedureQualityRule.query.count()==0:
            for mod,pat,mn,warn,series in _rb.QUALITY_DEFAULTS:
                _rb.db.session.add(_rb.ProcedureQualityRule(modality=mod,procedure_pattern=pat,min_images=mn,
                    warning_images=warn,required_series=series,require_history=True,
                    require_attachments=False,require_pacs_study=True,block_auto_assign=True))
        if _rb.CaseReturnReason.query.count()==0:
            for code,label,route in [
              ('INCOMPLETE_IMAGES','Incomplete images','TECHNICIAN'),
              ('MISSING_SERIES','Missing series / sequence','TECHNICIAN'),
              ('WRONG_PROTOCOL','Wrong protocol','TECHNICIAN'),
              ('MOTION_ARTIFACT','Motion artifact / poor image quality','TECHNICIAN'),
              ('MISSING_HISTORY','Missing clinical history','RECEPTION'),
              ('MISSING_REFERRAL','Missing referral / attachment','RECEPTION'),
              ('DEMOGRAPHIC_MISMATCH','Patient demographic mismatch','RECEPTION'),
              ('NEED_PRIOR','Need prior/comparison study','RECEPTION'),
              ('OUTSIDE_SPECIALTY','Outside doctor specialty','ASSIGNMENT'),
              ('ADDITIONAL_IMAGING','Additional imaging required','TECHNICIAN'),
              ('OTHER','Other','SUPERVISOR')]:
                _rb.db.session.add(_rb.CaseReturnReason(code=code,label=label,route_to=route))
        if _rb.TATPolicy.query.count()==0:
            for p,total,report in [('STAT',30,15),('URGENT',60,30),('ROUTINE',120,60)]:
                _rb.db.session.add(_rb.TATPolicy(priority=p,total_tat_min=total,accept_to_final_min=report))
        if _rb.NotificationEscalationRule.query.count()==0:
            for ev,role,esc,mins in [
              ('INCOMPLETE_IMAGES','TECHNICIAN','BRANCH_MANAGER',15),
              ('MISSING_HISTORY','RECEPTION','BRANCH_MANAGER',15),
              ('MISSING_ATTACHMENTS','RECEPTION','BRANCH_MANAGER',20),
              ('ASSIGNMENT_TIMEOUT','ASSIGNMENT','BRANCH_MANAGER',10),
              ('STAT_OVERDUE','DOCTOR','BRANCH_MANAGER',5),
              ('RETURNED_TO_TECH','TECHNICIAN','BRANCH_MANAGER',15)]:
                _rb.db.session.add(_rb.NotificationEscalationRule(event_type=ev,first_role=role,escalate_role=esc,escalate_after_min=mins))
        _rb.db.session.commit()
    return seed_quality_defaults


def install_0382(_rb):
    def case_delay_snapshot(order):
        events=_rb.CaseWorkflowEvent.query.filter_by(order_id=order.id).order_by(_rb.CaseWorkflowEvent.created_at).all()
        now=_rb.datetime.utcnow()
        readiness=__import__('reception_readiness').view(order,_rb.CaseReadiness.query.filter_by(order_id=order.id).first())
        assignment=_rb.CaseAssignment.query.filter_by(order_id=order.id,active=True).order_by(_rb.CaseAssignment.assigned_at.desc()).first()
        final=None
        try:
            final=_rb.Report.query.filter_by(order_id=order.id,status='FINAL').order_by(_rb.Report.id.desc()).first()
        except Exception: pass
        registered=getattr(order,'created_at',None) or getattr(order,'scheduled',None)
        # A finalized report is the terminal TAT event.  Keep historical TAT
        # stable instead of allowing it to grow on every dashboard refresh.
        total_end=(
            final.finalized_at
            if final and final.finalized_at
            else now
        )
        total_min=max(
            0,
            int((total_end-registered).total_seconds()/60)
        ) if registered else 0
        policy=_rb.resolve_tat_policy(
            order.priority,
            order.modality
        )
        overdue=bool(policy and total_min>policy.total_tat_min and not final)
        if final:
            owner='COMPLETE';reason='FINALIZED'
        elif readiness and readiness.status=='BLOCKED':
            owner='TECHNICIAN' if readiness.incomplete_images or readiness.missing_pacs else 'RECEPTION'
            reason='CASE_INCOMPLETE'
        elif not assignment:
            owner='ASSIGNMENT';reason='WAITING_ASSIGNMENT'
        else:
            owner='DOCTOR';reason='WAITING_REPORT'
        return {'total_min':total_min,'overdue':overdue,'owner':owner,'reason':reason,
          'readiness':readiness.status if readiness else 'NOT_CHECKED','final':bool(final)}
    return case_delay_snapshot


def install_0385(_rb):
    def default_label_template(order):
        row=_rb.LabelTemplate.query.filter_by(branch_id=order.branch_id,active=True,is_default=True).first()
        if row: return row
        return _rb.LabelTemplate.query.filter_by(active=True,is_default=True).order_by(_rb.LabelTemplate.id).first()
    return default_label_template


def install_0387(_rb):
    def enabled_ocr_provider():
        return _rb.OCRProviderSetting.query.filter_by(enabled=True).order_by(_rb.OCRProviderSetting.id).first()
    return enabled_ocr_provider


def install_0389(_rb):
    def resolve_printer_profile(order,document_type,workstation_code=''):
        q=_rb.PrinterProfile.query.filter_by(document_type=document_type.upper(),active=True)
        rows=q.order_by(_rb.PrinterProfile.user_id.desc(),_rb.PrinterProfile.workstation_code.desc(),_rb.PrinterProfile.branch_id.desc()).all()
        uid=_rb.current_user().id if _rb.current_user() else None
        branch_id=getattr(order,'branch_id',None)
        wc=(workstation_code or '').strip()
        scored=[]
        for p in rows:
            if p.user_id and p.user_id!=uid: continue
            if p.branch_id and p.branch_id!=branch_id: continue
            if p.workstation_code and p.workstation_code!=wc: continue
            score=(8 if p.user_id else 0)+(4 if p.workstation_code else 0)+(2 if p.branch_id else 0)
            scored.append((score,p))
        return sorted(scored,key=lambda x:x[0],reverse=True)[0][1] if scored else None
    return resolve_printer_profile


def install_0390(_rb):
    def generated_attachment_filename(order_id, category, original_name):
        """Generate collision-resistant server filename while preserving original_name in DB/UI."""
        ext=_rb.os.path.splitext(original_name or '')[1].lower()
        if not _rb.re.fullmatch(r'\.[a-z0-9]{1,10}', ext or ''):
            ext=''
        cat=_rb.re.sub(r'[^A-Z0-9_-]','_',str(category or 'OTHER').upper())[:40] or 'OTHER'
        oid=str(order_id or 'GENERAL')
        return f"ATT_{oid}_{cat}_{_rb.uuid.uuid4().hex[:12]}{ext}"
    return generated_attachment_filename


def install_0392(_rb):
    def _simple_identity_extract(text):
        """
    Conservative identity extraction from OCR text.

    Extracts only suggestions for staff review.
    It must never convert arbitrary card/passport numbers into an
    Egyptian National ID.
    """
        text = str(text or '')
        out = {}

        # Normalize Arabic/Persian digits for numeric matching.
        digit_map = str.maketrans(
            '٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹',
            '01234567890123456789'
        )
        numeric_text = text.translate(digit_map)

        lines = [
            _rb.re.sub(r'\s+', ' ', line).strip()
            for line in text.splitlines()
            if _rb.re.sub(r'\s+', ' ', line).strip()
        ]

        # ---------------------------------------------------------
        # Egyptian National ID: exactly 14 standalone digits.
        # Do NOT treat passport/card numbers as national IDs.
        # ---------------------------------------------------------
        national_ids = _rb.re.findall(
            r'(?<!\d)([23]\d{13})(?!\d)',
            numeric_text
        )

        for candidate in national_ids:
            validation = _rb.validate_intake_identity({
                'national_id': candidate
            })

            # Keep the candidate only when normalization accepts it.
            normalized = _rb.normalize_intake_identity({
                'national_id': candidate
            }).get('national_id', '')

            if normalized:
                out['national_id'] = normalized
                break

        # ---------------------------------------------------------
        # Egyptian mobile number
        # ---------------------------------------------------------
        phone_match = _rb.re.search(
            r'(?<!\d)(01[0125]\d{8})(?!\d)',
            numeric_text
        )
        if phone_match:
            out['phone'] = phone_match.group(1)

        # ---------------------------------------------------------
        # Arabic patient name suggestion
        #
        # Conservative:
        # - Arabic characters/spaces only
        # - ignore obvious government/header lines
        # - require at least 3 name tokens
        # ---------------------------------------------------------
        arabic_stop = (
            'جمهورية مصر',
            'وزارة',
            'بطاقة',
            'الرقم القومي',
            'رقم البطاقة',
            'الجنسية',
            'تاريخ الميلاد',
            'محل الاقامة',
            'العنوان',
        )

        arabic_candidates = []

        for line in lines:
            if any(stop in line for stop in arabic_stop):
                continue

            if _rb.re.fullmatch(r'[\u0600-\u06FF\s]+', line):
                words = [w for w in line.split() if len(w) >= 2]

                if 3 <= len(words) <= 7:
                    arabic_candidates.append(
                        (' '.join(words), len(words))
                    )

        if arabic_candidates:
            arabic_candidates.sort(
                key=lambda item: (-item[1], lines.index(item[0])
                                  if item[0] in lines else 9999)
            )
            out['name'] = arabic_candidates[0][0]

        # ---------------------------------------------------------
        # English name fallback.
        # Used only if no reliable Arabic name was found.
        # ---------------------------------------------------------
        if not out.get('name'):
            english_stop = {
                'arab republic of egypt',
                'national id card',
                'card number',
                'identity card',
                'republic of egypt',
            }

            english_candidates = []

            for line in lines:
                low = line.lower()

                if low in english_stop:
                    continue

                if _rb.re.fullmatch(r"[A-Za-z][A-Za-z .'-]+", line):
                    words = [
                        w for w in _rb.re.split(r'\s+', line)
                        if len(w.strip(".'-")) >= 2
                    ]

                    if 3 <= len(words) <= 7:
                        english_candidates.append(
                            (' '.join(words), len(words))
                        )

            if english_candidates:
                english_candidates.sort(
                    key=lambda item: -item[1]
                )
                out['name'] = english_candidates[0][0]

        # ---------------------------------------------------------
        # Non-national identity/card/passport reference.
        #
        # Keep separate from national_id.
        # ---------------------------------------------------------
        reference_patterns = [
            r'(?<![A-Z0-9])([A-Z]{1,4}\d{5,16})(?![A-Z0-9])',
            r'(?<![A-Z0-9])([A-Z0-9]{8,20})(?![A-Z0-9])',
        ]

        references = []

        upper_text = numeric_text.upper()

        for pattern in reference_patterns:
            for value in _rb.re.findall(pattern, upper_text):
                if value == out.get('national_id'):
                    continue
                if value not in references:
                    references.append(value)

        if references:
            out['identity_reference'] = references[0]

        return out
    return _simple_identity_extract


def install_0407(_rb):
    def build_calendar_cells(appointments,slots,slot_minutes=15):
        """Return display and occupancy data for every device/time cell."""
        cells={}
        for appointment in appointments:
            if not appointment.device_id:
                continue
            if (appointment.status or '').upper() in ('CANCELLED','NO_SHOW'):
                continue
            duration=max(
                5,
                int(
                    appointment.duration_min
                    or (
                        appointment.procedure.duration_min
                        if appointment.procedure else 20
                    )
                    or 20
                ),
            )
            appointment_end=appointment.scheduled+_rb.timedelta(minutes=duration)
            for slot in slots:
                slot_end=slot+_rb.timedelta(minutes=slot_minutes)
                if appointment.scheduled>=slot_end or appointment_end<=slot:
                    continue
                key=f'{int(appointment.device_id)}|{slot.isoformat()}'
                cell=cells.setdefault(key,{'starts':[],'occupied':True})
                if slot<=appointment.scheduled<slot_end:
                    cell['starts'].append(appointment)
        return cells
    return build_calendar_cells


def install_0409(_rb):
    def _rb_v5462_proc_ids(form):
        out=[]
        for raw in form.getlist('procedure_ids'):
            try: pid=int(raw)
            except Exception: continue
            if pid not in out: out.append(pid)
        if not out:
            one=form.get('procedure_id',type=int)
            if one: out=[one]
        return out
    return _rb_v5462_proc_ids


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


def install_0414(_rb):
    def _rb_v5462_notes(order,form):
        parts=[]
        for label,key in (
            ('History','clinical_history'),
            ('Clinical note','clinical_note'),
            ('Questionnaire','questionnaire_note')
        ):
            value=(form.get(key) or '').strip()
            if value: parts.append(label+':\n'+value)
        if parts:
            _rb.db.session.add(_rb.ClinicalNote(
                order_id=order.id,author_user_id=_rb.current_user().id,
                note_type='RECEPTION',visibility='CLINICAL_TEAM',
                text='\n\n'.join(parts)
            ))
    return _rb_v5462_notes


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


def install_0493(_rb):
    def _command_center_control_defaults():
        return {
            'schema': 'radbridge.command_center.control.v1',
            'mode': 'LIVE',
            'normal_interval_seconds': 15,
            'live_interval_seconds': 2,
            'updated_at': None,
            'updated_by': '',
            'storage_configured': bool(
                _rb.os.environ.get(
                    'RADBRIDGE_COMMAND_CENTER_CONTROL_FILE'
                )
            ),
        }
    return _command_center_control_defaults


def install_0494(_rb):
    def _command_center_control_path():
        return str(
            _rb.os.environ.get(
                'RADBRIDGE_COMMAND_CENTER_CONTROL_FILE'
            )
            or ''
        ).strip()
    return _command_center_control_path


def install_0495(_rb):
    def command_center_control_state():

        state = _rb._command_center_control_defaults()

        path = _rb._command_center_control_path()

        if not path:
            return state

        try:
            with open(
                path,
                'r',
                encoding='utf-8'
            ) as handle:
                stored = _rb.json.load(handle)

            if not isinstance(stored, dict):
                return state

            mode = str(
                stored.get('mode')
                or state['mode']
            ).upper()

            if mode not in (
                'OFF',
                'NORMAL',
                'LIVE'
            ):
                mode = state['mode']

            try:
                normal_interval = int(
                    stored.get(
                        'normal_interval_seconds',
                        state['normal_interval_seconds']
                    )
                )
            except Exception:
                normal_interval = \
                    state['normal_interval_seconds']

            try:
                live_interval = int(
                    stored.get(
                        'live_interval_seconds',
                        state['live_interval_seconds']
                    )
                )
            except Exception:
                live_interval = \
                    state['live_interval_seconds']

            state.update({
                'mode': mode,
                'normal_interval_seconds': max(
                    5,
                    min(normal_interval, 120)
                ),
                'live_interval_seconds': max(
                    1,
                    min(live_interval, 10)
                ),
                'updated_at': stored.get(
                    'updated_at'
                ),
                'updated_by': str(
                    stored.get('updated_by')
                    or ''
                ),
                'storage_configured': True,
            })

        except FileNotFoundError:
            pass

        except Exception:
            _rb.app.logger.exception(
                'COMMAND_CENTER_CONTROL_READ_FAILED'
            )

        return state
    return command_center_control_state


def install_0496(_rb):
    def _command_center_write_control_state(
        mode,
        normal_interval_seconds=None,
        live_interval_seconds=None,
        updated_by=''
    ):

        path = _rb._command_center_control_path()

        if not path:
            return (
                False,
                'CONTROL_STORAGE_NOT_CONFIGURED'
            )

        mode = str(
            mode or ''
        ).upper()

        if mode not in (
            'OFF',
            'NORMAL',
            'LIVE'
        ):
            return (
                False,
                'INVALID_MONITORING_MODE'
            )

        current = _rb.command_center_control_state()

        try:
            normal_interval = int(
                normal_interval_seconds
                if normal_interval_seconds is not None
                else current[
                    'normal_interval_seconds'
                ]
            )

            live_interval = int(
                live_interval_seconds
                if live_interval_seconds is not None
                else current[
                    'live_interval_seconds'
                ]
            )

        except Exception:
            return (
                False,
                'INVALID_INTERVAL'
            )

        normal_interval = max(
            5,
            min(normal_interval, 120)
        )

        live_interval = max(
            1,
            min(live_interval, 10)
        )

        directory = _rb.os.path.dirname(path)

        try:
            if directory:
                _rb.os.makedirs(
                    directory,
                    exist_ok=True
                )

            payload = {
                'schema':
                    'radbridge.command_center.control.v1',

                'mode':
                    mode,

                'normal_interval_seconds':
                    normal_interval,

                'live_interval_seconds':
                    live_interval,

                'updated_at':
                    _rb.datetime.utcnow().isoformat()
                    + 'Z',

                'updated_by':
                    str(updated_by or ''),
            }

            temp_path = (
                path
                + '.tmp.'
                + str(_rb.os.getpid())
            )

            with open(
                temp_path,
                'w',
                encoding='utf-8'
            ) as handle:
                _rb.json.dump(
                    payload,
                    handle,
                    ensure_ascii=False,
                    sort_keys=True
                )

                handle.flush()
                _rb.os.fsync(
                    handle.fileno()
                )

            _rb.os.replace(
                temp_path,
                path
            )

            return (
                True,
                payload
            )

        except Exception:
            _rb.app.logger.exception(
                'COMMAND_CENTER_CONTROL_WRITE_FAILED'
            )

            return (
                False,
                'CONTROL_WRITE_FAILED'
            )
    return _command_center_write_control_state


def install_0499(_rb):
    def _rb_auto_protection_state_path():
        control_path = _rb._command_center_control_path()

        if not control_path:
            return ''

        return control_path + '.autoprotect.json'
    return _rb_auto_protection_state_path


def install_0500(_rb):
    def _rb_auto_protection_defaults():
        return {
            'enabled': True,
            'load_ratio_threshold': 0.80,
            'memory_percent_threshold': 85.0,
            'sustain_seconds': 120,
            'high_since': None,
            'last_triggered_at': None,
            'last_reason': '',
        }
    return _rb_auto_protection_defaults


def install_0501(_rb):
    def _rb_auto_protection_read_state():
        state = _rb._rb_auto_protection_defaults()

        path = _rb._rb_auto_protection_state_path()

        if not path:
            return state

        try:
            with open(
                path,
                'r',
                encoding='utf-8'
            ) as handle:
                stored = _rb.json.load(handle)

            if isinstance(stored, dict):
                state.update(stored)

        except FileNotFoundError:
            pass

        except Exception:
            _rb.app.logger.exception(
                'COMMAND_CENTER_AUTO_PROTECT_READ_FAILED'
            )

        return state
    return _rb_auto_protection_read_state


def install_0502(_rb):
    def _rb_auto_protection_write_state(state):
        path = _rb._rb_auto_protection_state_path()

        if not path:
            return False

        directory = _rb.os.path.dirname(path)

        try:
            if directory:
                _rb.os.makedirs(
                    directory,
                    exist_ok=True
                )

            temp_path = (
                path
                + '.tmp.'
                + str(_rb.os.getpid())
            )

            with open(
                temp_path,
                'w',
                encoding='utf-8'
            ) as handle:
                _rb.json.dump(
                    state,
                    handle,
                    ensure_ascii=False,
                    sort_keys=True
                )

                handle.flush()
                _rb.os.fsync(
                    handle.fileno()
                )

            _rb.os.replace(
                temp_path,
                path
            )

            return True

        except Exception:
            _rb.app.logger.exception(
                'COMMAND_CENTER_AUTO_PROTECT_WRITE_FAILED'
            )

            return False
    return _rb_auto_protection_write_state


def install_0503(_rb):
    def _rb_auto_protection_evaluate(
        host_metrics,
        container_metrics
    ):
        import time as _time

        control = _rb.command_center_control_state()
        state = _rb._rb_auto_protection_read_state()

        result = {
            'enabled': bool(
                state.get('enabled', True)
            ),
            'triggered': False,
            'action': None,
            'reason': '',
            'high_since': state.get('high_since'),
            'sustain_seconds': int(
                state.get('sustain_seconds') or 120
            ),
        }

        if not result['enabled']:
            return result

        if str(control.get('mode')).upper() != 'LIVE':
            if state.get('high_since') is not None:
                state['high_since'] = None
                _rb._rb_auto_protection_write_state(state)

            return result

        cpu_count = max(
            1,
            int(host_metrics.get('cpu_count') or 1)
        )

        load1 = host_metrics.get('load1')

        try:
            load_ratio = (
                float(load1) / float(cpu_count)
            )
        except Exception:
            load_ratio = 0.0

        mem_total_kb = (
            host_metrics.get('mem_total_kb')
        )

        mem_available_kb = (
            host_metrics.get('mem_available_kb')
        )

        memory_percent = 0.0

        try:
            if (
                mem_total_kb
                and mem_available_kb is not None
            ):
                memory_percent = (
                    (
                        float(mem_total_kb)
                        - float(mem_available_kb)
                    )
                    / float(mem_total_kb)
                ) * 100.0
        except Exception:
            memory_percent = 0.0

        load_threshold = float(
            state.get(
                'load_ratio_threshold',
                0.80
            )
        )

        memory_threshold = float(
            state.get(
                'memory_percent_threshold',
                85.0
            )
        )

        reasons = []

        if load_ratio >= load_threshold:
            reasons.append(
                'LOAD_RATIO_HIGH'
            )

        if memory_percent >= memory_threshold:
            reasons.append(
                'MEMORY_HIGH'
            )

        now = _time.time()

        if not reasons:
            if state.get('high_since') is not None:
                state['high_since'] = None
                state['last_reason'] = ''
                _rb._rb_auto_protection_write_state(state)

            return result

        if state.get('high_since') is None:
            state['high_since'] = now
            state['last_reason'] = ','.join(reasons)
            _rb._rb_auto_protection_write_state(state)

            result['high_since'] = now
            result['reason'] = state['last_reason']

            return result

        try:
            elapsed = (
                now
                - float(state.get('high_since'))
            )
        except Exception:
            elapsed = 0

        result['high_since'] = state.get('high_since')
        result['reason'] = ','.join(reasons)

        sustain_seconds = int(
            state.get('sustain_seconds') or 120
        )

        if elapsed < sustain_seconds:
            return result

        ok, write_result = \
            _rb._command_center_write_control_state(
                mode='NORMAL',
                updated_by='AUTO_PROTECTION',
            )

        if not ok:
            result['reason'] = (
                result['reason']
                + '; CONTROL_WRITE_FAILED'
            )
            return result

        triggered_at = (
            _rb.datetime.utcnow().isoformat()
            + 'Z'
        )

        state['high_since'] = None
        state['last_triggered_at'] = triggered_at
        state['last_reason'] = result['reason']

        _rb._rb_auto_protection_write_state(state)

        result['triggered'] = True
        result['action'] = 'LIVE_TO_NORMAL'

        return result
    return _rb_auto_protection_evaluate


def install_0504(_rb):
    def _rb_read_text(path):
        try:
            with open(path, 'r', encoding='utf-8') as handle:
                return handle.read().strip()
        except Exception:
            return ''
    return _rb_read_text


def install_0505(_rb):
    def _rb_int(value):
        try:
            return int(str(value).strip())
        except Exception:
            return None
    return _rb_int


def install_0506(_rb):
    def _rb_cgroup_metrics():
        data = {
            'memory_current_bytes': None,
            'memory_max_bytes': None,
            'pids_current': None,
            'cpu_usage_usec': None,
            'cpu_user_usec': None,
            'cpu_system_usec': None,
        }

        memory_current = _rb._rb_read_text(
            '/sys/fs/cgroup/memory.current'
        )
        memory_max = _rb._rb_read_text(
            '/sys/fs/cgroup/memory.max'
        )
        pids_current = _rb._rb_read_text(
            '/sys/fs/cgroup/pids.current'
        )
        cpu_stat = _rb._rb_read_text(
            '/sys/fs/cgroup/cpu.stat'
        )

        data['memory_current_bytes'] = \
            _rb._rb_int(memory_current)

        if memory_max and memory_max != 'max':
            data['memory_max_bytes'] = \
                _rb._rb_int(memory_max)

        data['pids_current'] = \
            _rb._rb_int(pids_current)

        if cpu_stat:
            for line in cpu_stat.splitlines():
                parts = line.split()
                if len(parts) != 2:
                    continue

                key, value = parts

                if key == 'usage_usec':
                    data['cpu_usage_usec'] = \
                        _rb._rb_int(value)

                elif key == 'user_usec':
                    data['cpu_user_usec'] = \
                        _rb._rb_int(value)

                elif key == 'system_usec':
                    data['cpu_system_usec'] = \
                        _rb._rb_int(value)

        return data
    return _rb_cgroup_metrics


def install_0507(_rb):
    def _rb_host_metrics():
        import os as _os
        import shutil as _shutil

        result = {
            'cpu_count': _os.cpu_count(),
            'load1': None,
            'load5': None,
            'load15': None,
            'mem_total_kb': None,
            'mem_available_kb': None,
            'disk_total_bytes': None,
            'disk_used_bytes': None,
            'disk_free_bytes': None,
        }

        try:
            load1, load5, load15 = _os.getloadavg()

            result['load1'] = load1
            result['load5'] = load5
            result['load15'] = load15

        except Exception:
            pass

        meminfo = _rb._rb_read_text('/proc/meminfo')

        if meminfo:
            for line in meminfo.splitlines():

                if line.startswith('MemTotal:'):
                    parts = line.split()
                    if len(parts) >= 2:
                        result['mem_total_kb'] = \
                            _rb._rb_int(parts[1])

                elif line.startswith('MemAvailable:'):
                    parts = line.split()
                    if len(parts) >= 2:
                        result['mem_available_kb'] = \
                            _rb._rb_int(parts[1])

        try:
            usage = _shutil.disk_usage('/')

            result['disk_total_bytes'] = usage.total
            result['disk_used_bytes'] = usage.used
            result['disk_free_bytes'] = usage.free

        except Exception:
            pass

        return result
    return _rb_host_metrics


def install_0532(_rb):
    def _strategy_action(value,default='WARN'):
        value=str(value or default).upper()

        if value not in (
            'BLOCK',
            'WARN',
            'ALLOW',
            'IGNORE',
            'COORDINATOR'
        ):
            return default

        return value
    return _strategy_action


def install_0533(_rb):
    def _strategy_snapshot(row):

        fields=(
            'name',
            'enabled',
            'priority',
            'branch_id',
            'modality',
            'procedure_pattern',
            'assignment_mode',
            'fallback_mode',
            'pacs_missing_action',
            'images_incomplete_action',
            'documents_missing_action',
            'notes_missing_action',
            'attachments_missing_action',
            'history_missing_action',
            'require_modality_match',
            'require_branch_match',
            'require_online',
            'prefer_online',
            'min_images',
            'min_completion_percent',
            'stable_seconds',
            'routine_timeout_seconds',
            'urgent_timeout_seconds',
            'stat_timeout_seconds',
            'busy_snooze_minutes',
            'max_offer_attempts',
            'active_from',
            'active_to',
            'version_no'
        )

        return {
            f:getattr(row,f,None)
            for f in fields
        }
    return _strategy_snapshot


def install_0534(_rb):
    def _strategy_change_summary(before, after):
        changes=[]

        fields=(
            'name',
            'enabled',
            'priority',
            'branch_id',
            'modality',
            'procedure_pattern',
            'assignment_mode',
            'fallback_mode',
            'pacs_missing_action',
            'images_incomplete_action',
            'documents_missing_action',
            'notes_missing_action',
            'attachments_missing_action',
            'history_missing_action',
            'require_modality_match',
            'require_branch_match',
            'require_online',
            'prefer_online',
            'min_images',
            'min_completion_percent',
            'stable_seconds',
            'routine_timeout_seconds',
            'urgent_timeout_seconds',
            'stat_timeout_seconds',
            'busy_snooze_minutes',
            'max_offer_attempts',
            'active_from',
            'active_to'
        )

        for field in fields:
            old=before.get(field)
            new=after.get(field)

            if old!=new:
                changes.append(
                    f'{field}: {old} -> {new}'
                )

        if not changes:
            return 'No functional changes'

        return '; '.join(changes)[:500]
    return _strategy_change_summary


def install_0576(_rb):
    def cancellation_reason():
        reason=(_rb.request.form.get('reason') or '').strip()
        if len(reason)<5:_rb.abort(400,'Cancellation reason must contain at least 5 characters.')
        return reason[:1000]
    return cancellation_reason


def install_0577(_rb):
    def _cancellation_literal_search_pattern(term):
        # Cancellation Center search values are identifiers/user text, not
        # caller-controlled LIKE patterns. Escape SQL LIKE metacharacters so
        # values such as '%' or '_' cannot broaden candidate selection.
        term=(term or '').strip()[:120]
        escaped=(
            term.replace('\\','\\\\')
                .replace('%','\\%')
                .replace('_','\\_')
        )
        return term,f'%{escaped}%'
    return _cancellation_literal_search_pattern


def install_0578(_rb):
    def cancellation_search_rows(term):
        term,pattern=_rb._cancellation_literal_search_pattern(term)
        if not term:return [],[]

        orders=(
            _rb.Order.query
            .join(_rb.Patient,_rb.Order.patient_id==_rb.Patient.id)
            .filter(_rb.db.or_(
                _rb.Order.accession.ilike(pattern,escape='\\'),
                _rb.Patient.patient_id.ilike(pattern,escape='\\'),
                _rb.Patient.name.ilike(pattern,escape='\\'),
                _rb.Patient.phone.ilike(pattern,escape='\\'),
            ))
            .order_by(_rb.Order.id.desc())
            .limit(50)
            .all()
        )

        appointments=(
            _rb.Appointment.query
            .join(_rb.Patient,_rb.Appointment.patient_id==_rb.Patient.id)
            .filter(_rb.db.or_(
                _rb.Patient.patient_id.ilike(pattern,escape='\\'),
                _rb.Patient.name.ilike(pattern,escape='\\'),
                _rb.Patient.phone.ilike(pattern,escape='\\'),
            ))
            .order_by(_rb.Appointment.id.desc())
            .limit(50)
            .all()
        )

        # Internal Order ID / Appointment ID are exact-only. Numeric patient IDs
        # or phone fragments still participate in the text search above.
        if term.isdigit():
            order=_rb.db.session.get(_rb.Order,int(term))
            appointment=_rb.db.session.get(_rb.Appointment,int(term))
            if order and order not in orders:orders.insert(0,order)
            if appointment and appointment not in appointments:appointments.insert(0,appointment)

        return orders[:50],appointments[:50]
    return cancellation_search_rows


def install_0579(_rb):
    def granular_delete_images_only_preflight(
        order,
        typed_accession,
        reason,
        cached_orthanc_response=None,
    ):
        blockers=[]

        user=_rb.current_user()

        if (
            not user
            or not getattr(user, 'role', None)
            or getattr(user.role, 'code', '') != 'SUPER_ADMIN'
        ):
            blockers.append('SUPER_ADMIN_REQUIRED')

        reason=(reason or '').strip()
        typed_accession=(typed_accession or '').strip()
        accession=(order.accession or '').strip()
        study_id=(order.pacs_study_id or '').strip()

        if len(reason) < 5:
            blockers.append('REASON_REQUIRED')

        if not accession:
            blockers.append('ORDER_ACCESSION_MISSING')
        elif typed_accession != accession:
            blockers.append('ACCESSION_CONFIRMATION_MISMATCH')

        if not study_id:
            blockers.append('PACS_STUDY_ID_MISSING')

        patient=_rb.db.session.get(_rb.Patient, order.patient_id)

        if not patient:
            blockers.append('PATIENT_MISSING')

        same_study_orders=[]

        if study_id:
            same_study_orders=(
                _rb.Order.query
                .filter(_rb.Order.pacs_study_id == study_id)
                .order_by(_rb.Order.id)
                .all()
            )

            others=[
                row
                for row in same_study_orders
                if row.id != order.id
            ]

            if others:
                blockers.append('PACS_STUDY_SHARED_BY_OTHER_ORDER')

        active_transfer_count=0

        if study_id:
            active_transfer_count=(
                _rb.PacsTransferJob.query
                .filter(
                    _rb.PacsTransferJob.order_id == order.id,
                    _rb.PacsTransferJob.orthanc_study_id == study_id,
                    _rb.PacsTransferJob.status.in_(
                        ('PENDING','SENDING')
                    ),
                )
                .count()
            )

            if active_transfer_count:
                blockers.append('ACTIVE_PACS_TRANSFER_JOB')

        orthanc_status=None
        orthanc_payload=None
        orthanc_error=''

        if study_id:
            try:
                response=(
                    cached_orthanc_response
                    if cached_orthanc_response is not None
                    else _rb.requests.get(
                        f'{_rb.PACS_ORTHANC_URL}/studies/{study_id}',
                        auth=_rb._orthanc_auth(),
                        timeout=10,
                    )
                )

                orthanc_status=response.status_code

                if response.status_code == 200:
                    orthanc_payload=response.json()
                else:
                    blockers.append('ORTHANC_STUDY_NOT_AVAILABLE')

            except Exception as exc:
                orthanc_error=type(exc).__name__
                blockers.append('ORTHANC_LOOKUP_FAILED')

        if orthanc_payload:
            tags=orthanc_payload.get('MainDicomTags') or {}
            patient_tags=orthanc_payload.get('PatientMainDicomTags') or {}

            orthanc_accession=(tags.get('AccessionNumber') or '').strip()
            orthanc_patient_id=(patient_tags.get('PatientID') or '').strip()
            orthanc_uid=(tags.get('StudyInstanceUID') or '').strip()

            ris_patient_id=(
                (patient.patient_id or '').strip()
                if patient
                else ''
            )

            ris_uid=(
                getattr(order, 'study_instance_uid', '')
                or ''
            ).strip()

            if not orthanc_accession or orthanc_accession != accession:
                blockers.append('ORTHANC_ACCESSION_MISMATCH')

            if (
                orthanc_patient_id
                and ris_patient_id
                and orthanc_patient_id != ris_patient_id
            ):
                blockers.append('ORTHANC_PATIENT_ID_MISMATCH')

            if (
                orthanc_uid
                and ris_uid
                and orthanc_uid != ris_uid
            ):
                blockers.append('ORTHANC_STUDY_UID_MISMATCH')

        return {
            'allowed': not blockers,
            'blockers': blockers,
            'reason': reason,
            'typed_accession': typed_accession,
            'accession': accession,
            'study_id': study_id,
            'patient': patient,
            'orthanc_status': orthanc_status,
            'orthanc_payload': orthanc_payload,
            'orthanc_error': orthanc_error,
            'same_study_order_count': len(same_study_orders),
            'active_transfer_count': active_transfer_count,
        }
    return granular_delete_images_only_preflight


def install_0580(_rb):
    def granular_delete_images_only_execute(
        order,
        typed_accession,
        reason,
        preflight=None,
        after_delete=None,
    ):
        order_id=order.id

        # Phase 2B callers may persist the exact preflight result in the
        # execution ledger before crossing the irreversible DELETE boundary.
        # Legacy/admin callers retain the original self-contained behavior.
        if preflight is None:
            preflight=_rb.granular_delete_images_only_preflight(
                order,
                typed_accession,
                reason,
            )

        if not preflight['allowed']:
            _rb.audit(
                'PACS_IMAGES_DELETE_BLOCKED_ADMIN',
                'order',
                order.id,
                (
                    f"accession={order.accession}; "
                    f"study={preflight['study_id']}; "
                    f"blockers={','.join(preflight['blockers'])}; "
                    f"reason={reason}"
                ),
            )
            _rb.db.session.commit()

            return {
                'ok': False,
                'deleted': False,
                'blockers': preflight['blockers'],
            }, 409

        # Final critical revalidation at the irreversible boundary.
        # The earlier preflight is persisted in the correction execution ledger,
        # but PACS/RIS state can change between that check and Orthanc DELETE.
        # Refresh the order and rerun the same safety contract immediately before
        # deletion; never cross the boundary on stale identity/transfer state.
        initial_study_id=(preflight.get('study_id') or '').strip()
        initial_accession=(preflight.get('accession') or '').strip()

        try:
            _rb.db.session.refresh(order)
        except Exception as exc:
            _rb.audit(
                'PACS_IMAGES_DELETE_BLOCKED_ADMIN',
                'order',
                order.id,
                (
                    f"accession={order.accession}; "
                    f"study={initial_study_id}; "
                    f"stage=FINAL_REVALIDATION_REFRESH; "
                    f"error={type(exc).__name__}; "
                    f"reason={reason}"
                ),
            )
            _rb.db.session.commit()

            return {
                'ok': False,
                'deleted': False,
                'ris_state_updated': False,
                'error': 'FINAL_REVALIDATION_FAILED',
                'blockers': ['ORDER_REFRESH_FAILED'],
            }, 409

        final_preflight=_rb.granular_delete_images_only_preflight(
            order,
            typed_accession,
            reason,
        )

        final_blockers=list(final_preflight.get('blockers') or ())
        final_study_id=(final_preflight.get('study_id') or '').strip()
        final_accession=(final_preflight.get('accession') or '').strip()

        if final_study_id != initial_study_id:
            final_blockers.append('PACS_STUDY_CHANGED_AFTER_PREFLIGHT')

        if final_accession != initial_accession:
            final_blockers.append('ACCESSION_CHANGED_AFTER_PREFLIGHT')

        if final_blockers:
            _rb.audit(
                'PACS_IMAGES_DELETE_BLOCKED_ADMIN',
                'order',
                order.id,
                (
                    f"accession={order.accession}; "
                    f"study={final_study_id}; "
                    f"stage=FINAL_REVALIDATION; "
                    f"blockers={','.join(final_blockers)}; "
                    f"reason={reason}"
                ),
            )
            _rb.db.session.commit()

            return {
                'ok': False,
                'deleted': False,
                'ris_state_updated': False,
                'error': 'FINAL_REVALIDATION_BLOCKED',
                'blockers': final_blockers,
            }, 409

        study_id=final_study_id
        image_count_before=order.pacs_image_count or 0
        study_uid=(
            getattr(order, 'study_instance_uid', '')
            or ''
        )

        _rb.audit(
            'PACS_IMAGES_DELETE_REQUESTED_ADMIN',
            'order',
            order.id,
            (
                f"accession={order.accession}; "
                f"patient_id={order.patient.patient_id if order.patient else ''}; "
                f"study={study_id}; "
                f"study_uid={study_uid}; "
                f"image_count_before={image_count_before}; "
                f"reason={reason}"
            ),
        )
        _rb.db.session.commit()

        try:
            response=_rb.requests.delete(
                f'{_rb.PACS_ORTHANC_URL}/studies/{study_id}',
                auth=_rb._orthanc_auth(),
                timeout=20,
            )
        except Exception as exc:
            _rb.audit(
                'PACS_IMAGES_DELETE_FAILED_ADMIN',
                'order',
                order.id,
                (
                    f"accession={order.accession}; "
                    f"study={study_id}; "
                    f"stage=ORTHANC_DELETE_EXCEPTION; "
                    f"error={type(exc).__name__}; "
                    f"reason={reason}"
                ),
            )
            _rb.db.session.commit()

            return {
                'ok': False,
                'deleted': False,
                'error': 'ORTHANC_DELETE_FAILED',
            }, 502

        if response.status_code != 200:
            _rb.audit(
                'PACS_IMAGES_DELETE_FAILED_ADMIN',
                'order',
                order.id,
                (
                    f"accession={order.accession}; "
                    f"study={study_id}; "
                    f"stage=ORTHANC_DELETE_HTTP; "
                    f"http={response.status_code}; "
                    f"reason={reason}"
                ),
            )
            _rb.db.session.commit()

            return {
                'ok': False,
                'deleted': False,
                'error': 'ORTHANC_DELETE_REJECTED',
                'http_status': response.status_code,
            }, 502

        # Orthanc accepted the DELETE. Persist VERIFYING before the
        # post-delete absence check or any RIS PACS-state mutation.
        if after_delete is not None:
            after_delete()

        try:
            verify=_rb.requests.get(
                f'{_rb.PACS_ORTHANC_URL}/studies/{study_id}',
                auth=_rb._orthanc_auth(),
                timeout=10,
            )
        except Exception as exc:
            _rb.audit(
                'PACS_IMAGES_DELETE_FAILED_ADMIN',
                'order',
                order.id,
                (
                    f"accession={order.accession}; "
                    f"study={study_id}; "
                    f"stage=ORTHANC_VERIFY_EXCEPTION; "
                    f"error={type(exc).__name__}; "
                    f"reason={reason}"
                ),
            )
            _rb.db.session.commit()

            return {
                'ok': False,
                'deleted': True,
                'ris_state_updated': False,
                'error': 'ORTHANC_DELETE_VERIFICATION_FAILED',
            }, 502

        if verify.status_code != 404:
            _rb.audit(
                'PACS_IMAGES_DELETE_FAILED_ADMIN',
                'order',
                order.id,
                (
                    f"accession={order.accession}; "
                    f"study={study_id}; "
                    f"stage=ORTHANC_VERIFY_PRESENT; "
                    f"http={verify.status_code}; "
                    f"reason={reason}"
                ),
            )
            _rb.db.session.commit()

            return {
                'ok': False,
                'deleted': True,
                'ris_state_updated': False,
                'error': 'ORTHANC_STUDY_STILL_PRESENT',
            }, 502

        try:
            order.pacs_image_count=0
            order.pacs_status='IMAGES_DELETED'
            order.pacs_last_seen_at=_rb.datetime.utcnow()
            order.pacs_last_change_at=_rb.datetime.utcnow()

            _rb.audit(
                'PACS_IMAGES_DELETED_ADMIN',
                'order',
                order.id,
                (
                    f"accession={order.accession}; "
                    f"patient_id={order.patient.patient_id if order.patient else ''}; "
                    f"study={study_id}; "
                    f"study_uid={study_uid}; "
                    f"image_count_before={image_count_before}; "
                    f"image_count_after=0; "
                    f"orthanc_verified_absent=yes; "
                    f"reason={reason}"
                ),
            )

            _rb.db.session.commit()

        except Exception as exc:
            _rb.db.session.rollback()

            try:
                _rb.audit(
                    'PACS_IMAGES_DELETE_FAILED_ADMIN',
                    'order',
                    order.id,
                    (
                        f"accession={order.accession}; "
                        f"study={study_id}; "
                        f"stage=RIS_STATE_UPDATE_AFTER_PACS_DELETE; "
                        f"error={type(exc).__name__}; "
                        f"reason={reason}"
                    ),
                )
                _rb.db.session.commit()
            except Exception:
                _rb.db.session.rollback()

            return {
                'ok': False,
                'deleted': True,
                'ris_state_updated': False,
                'error': 'RIS_STATE_UPDATE_FAILED_AFTER_PACS_DELETE',
            }, 500

        return {
            'ok': True,
            'deleted': True,
            'ris_state_updated': True,
            'order_id': order.id,
            'accession': order.accession,
            'pacs_study_id': study_id,
            'pacs_status': order.pacs_status,
            'pacs_image_count': order.pacs_image_count,
        }, 200
    return granular_delete_images_only_execute


def install_0587(_rb):
    def granular_delete_ris_case_only_preview_snapshot(order, dependency_rows, report_rows):
        """Read-only explicit policy preflight for Delete RIS Case Data Only."""
        from sqlalchemy import inspect as _ris_inspect, text as _ris_text

        rows=[]
        blockers=[]
        warnings=[]
        unknown_active=[]
        safe_delete_rows=0
        safe_nullify_rows=0

        inspector=_ris_inspect(_rb.db.engine)
        table_names=set(inspector.get_table_names())

        for dependency in dependency_rows:
            table=str(dependency.get('table') or '')
            column=str(dependency.get('column') or '')
            count=dependency.get('count')
            count_value=int(count or 0) if count is not None else None
            policy=_rb._RIS_CASE_ONLY_DEPENDENCY_POLICY.get((table,column))

            # Lease state is verified separately below, including malformed expiry
            # values. Do not classify these rows as unknown generic dependencies or
            # send them to the generic ORM action loop. The executor owns expired
            # lease cleanup; the raw FK scanner and final dependency check stay intact.
            if (table,column) == ('report_edit_lease','order_id') and count_value is not None:
                if 'report_edit_lease' not in table_names:
                    blockers.append('REPORT_LEASE_STATE_UNVERIFIED')
                continue

            if count_value is None:
                classification='REVIEW'
                action='BLOCK'
                reason='COMPOSITE_FK_REVIEW'
                blocking=True
            elif policy is None:
                classification='UNCLASSIFIED'
                action='BLOCK' if count_value else 'NONE'
                reason='UNKNOWN_DEPENDENCY' if count_value else 'NO_ROWS'
                blocking=bool(count_value)
            else:
                classification,action,reason=policy
                blocking=bool(count_value and action == 'BLOCK')

            if count_value:
                if action == 'DELETE_CASE_ROW':
                    safe_delete_rows += count_value
                elif action == 'NULLIFY_ORDER_LINK':
                    safe_nullify_rows += count_value

            if blocking:
                blockers.append(reason + ': ' + table + '.' + column)
                if policy is None:
                    unknown_active.append(table + '.' + column)

            rows.append({
                'table':table,
                'column':column,
                'count':count_value,
                'classification':classification,
                'action':action,
                'reason_code':reason,
                'blocking':blocking,
            })

        report_count=len(report_rows)
        if report_count:
            marker='DELETE_REPORTS_FIRST: report.order_id'
            if marker not in blockers:
                blockers.append(marker)

        active_lease_count=0
        expired_lease_count=0
        lease_verified=True
        try:
            if 'report_edit_lease' in table_names:
                lease_result=_rb.db.session.execute(
                    _ris_text(
                        'SELECT expires_at FROM report_edit_lease '
                        'WHERE order_id = :order_id'
                    ),
                    {'order_id':int(order.id)},
                ).all()
                from datetime import datetime as _ris_datetime, timezone as _ris_timezone
                now=_ris_datetime.utcnow()
                for lease in lease_result:
                    value=lease[0]
                    if isinstance(value,str):
                        raw=value.strip()
                        if raw.endswith('Z'):
                            raw=raw[:-1] + '+00:00'
                        try:
                            value=_ris_datetime.fromisoformat(raw)
                        except ValueError:
                            value=None
                    if value is None:
                        active_lease_count += 1
                        continue
                    if getattr(value,'tzinfo',None) is not None:
                        value=value.astimezone(_ris_timezone.utc).replace(tzinfo=None)
                    if value > now:
                        active_lease_count += 1
                    else:
                        expired_lease_count += 1
        except Exception as exc:
            lease_verified=False
            blockers.append('REPORT_LEASE_STATE_UNVERIFIED')
            warnings.append(type(exc).__name__)

        if active_lease_count:
            blockers.append('ACTIVE_REPORT_EDIT_LEASE')
        if expired_lease_count:
            warnings.append('EXPIRED_REPORT_EDIT_LEASE_PRESENT')

        can_prepare_execution=(
            not blockers
            and report_count == 0
            and not unknown_active
            and lease_verified
            and active_lease_count == 0
        )

        return {
            'readonly':True,
            'execution_implemented':False,
            'can_prepare_execution':can_prepare_execution,
            'report_count':report_count,
            'patient_preserved':True,
            'pacs_images_preserved':True,
            'audit_history_preserved':True,
            'safe_delete_row_count':safe_delete_rows,
            'safe_nullify_row_count':safe_nullify_rows,
            'unknown_active_dependencies':unknown_active,
            'lease':{
                'verified':lease_verified,
                'active_count':active_lease_count,
                'expired_count':expired_lease_count,
            },
            'rows':rows,
            'blockers':blockers,
            'warnings':warnings,
        }
    return granular_delete_ris_case_only_preview_snapshot


def install_0588(_rb):
    def _ris_case_only_dependency_rows(order):
        """Collect direct FK dependencies on order.id without mutating state."""
        from sqlalchemy import inspect as _ris_inspect, text as _ris_text

        inspector=_ris_inspect(_rb.db.session.connection())
        order_table=_rb.Order.__table__.name
        preparer=_rb.db.engine.dialect.identifier_preparer
        rows=[]

        for child_table in sorted(inspector.get_table_names()):
            for fk in inspector.get_foreign_keys(child_table):
                if fk.get('referred_table') != order_table:
                    continue
                local_columns=fk.get('constrained_columns') or []
                if len(local_columns) != 1:
                    rows.append({
                        'table':child_table,
                        'column':','.join(local_columns),
                        'count':None,
                        'classification':'COMPOSITE_FK_REVIEW',
                    })
                    continue
                local_column=local_columns[0]
                qt=preparer.quote(child_table)
                qc=preparer.quote(local_column)
                count=_rb.db.session.execute(
                    _ris_text('SELECT COUNT(*) FROM '+qt+' WHERE '+qc+' = :order_id'),
                    {'order_id':int(order.id)},
                ).scalar() or 0
                rows.append({
                    'table':child_table,
                    'column':local_column,
                    'count':int(count),
                    'classification':'EXECUTION_RESCAN',
                })
        return rows
    return _ris_case_only_dependency_rows


def install_0590(_rb):
    def granular_delete_ris_case_only_execution_preview_snapshot(order, dependency_rows=None, report_rows=None):
        """Execution-grade, still read-only preflight for RIS Case Data Only."""
        from sqlalchemy import inspect as _ris_inspect

        if dependency_rows is None:
            dependency_rows=_rb._ris_case_only_dependency_rows(order)
        if report_rows is None:
            reports=_rb.Report.query.filter_by(order_id=order.id).order_by(_rb.Report.id).all()
            report_rows=[{'id':r.id,'status':getattr(r,'status',None)} for r in reports]

        snap=_rb.granular_delete_ris_case_only_preview_snapshot(order,dependency_rows,report_rows)
        blockers=list(snap.get('blockers') or [])
        warnings=list(snap.get('warnings') or [])

        order_status=str(getattr(order,'status','') or '').strip().upper()
        if order_status not in ('CANCELLED','CANCELED'):
            blockers.append('ORDER_NOT_CANCELLED')

        inspector=_ris_inspect(_rb.db.session.connection())
        nullify_checks=[]
        for row in snap.get('rows') or []:
            if not row.get('count') or row.get('action') != 'NULLIFY_ORDER_LINK':
                continue
            table=str(row.get('table') or '')
            column=str(row.get('column') or '')
            columns={str(c.get('name')):c for c in inspector.get_columns(table)}
            nullable=bool(columns.get(column,{}).get('nullable'))
            nullify_checks.append({'table':table,'column':column,'nullable':nullable})
            if not nullable:
                blockers.append('NULLIFY_COLUMN_NOT_NULLABLE: '+table+'.'+column)

        second_order=_rb._ris_case_only_second_order_checks(order,snap.get('rows') or [])
        blockers.extend(second_order.get('blockers') or [])

        # Stable de-duplication for deterministic preview/audit/test output.
        blockers=list(dict.fromkeys(blockers))
        warnings=list(dict.fromkeys(warnings))
        snap['execution_implemented']=True
        snap['order_cancelled']=order_status in ('CANCELLED','CANCELED')
        snap['nullify_checks']=nullify_checks
        snap['second_order']=second_order
        snap['blockers']=blockers
        snap['warnings']=warnings
        snap['can_prepare_execution']=bool(
            not blockers
            and int(snap.get('report_count') or 0) == 0
            and not (snap.get('unknown_active_dependencies') or [])
            and bool(snap.get('lease',{}).get('verified'))
            and int(snap.get('lease',{}).get('active_count') or 0) == 0
        )
        return snap
    return granular_delete_ris_case_only_execution_preview_snapshot


def install_0591(_rb):
    def _ris_case_only_blocked_response(order, reason, code, blockers, status=409):
        try:
            _rb.audit(
                'RIS_CASE_DATA_DELETE_BLOCKED_ADMIN',
                'order',
                getattr(order,'id',''),
                (
                    f"accession={getattr(order,'accession','')}; "
                    f"code={code}; blockers={','.join(str(x) for x in (blockers or []))}; "
                    f"reason={reason}"
                ),
            )
            _rb.db.session.commit()
        except Exception:
            _rb.db.session.rollback()
        return {'ok':False,'deleted':False,'error':code,'blockers':list(blockers or [])},status
    return _ris_case_only_blocked_response


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


def install_0594(_rb):
    def granular_delete_full_case_orchestration_preview_snapshot(
        order,
        patient,
        dependency_rows,
        report_rows,
        reports_only_preview,
        ris_case_only_preview,
        pacs_snapshot,
    ):
        """Read-only staged plan for a future Full Case Deletion orchestrator.

    This function never executes a deletion. It composes the already-reviewed
    PACS Images Only, Reports Only, and RIS Case Data Only safety contracts and
    projects whether the three stages could run in the required order.
    """
        blockers=[]
        warnings=[]

        # This preview helper is also called directly by existing unit tests and
        # other read-only code paths that may have only an application context.
        # Session-backed actor lookup is valid only while a request context exists.
        from flask import has_request_context as _has_request_context
        user=_rb.current_user() if _has_request_context() else None

        super_admin=_rb._delete_reports_only_is_super_admin(user)
        if not super_admin:
            blockers.append('SUPER_ADMIN_REQUIRED')

        accession=str(getattr(order,'accession','') or '').strip()
        order_status=str(getattr(order,'status','') or '').strip().upper()
        if not accession:
            blockers.append('ORDER_ACCESSION_MISSING')
        if patient is None:
            blockers.append('PATIENT_MISSING')
        if order_status not in ('CANCELLED','CANCELED'):
            blockers.append('ORDER_NOT_CANCELLED')

        pacs_snapshot=dict(pacs_snapshot or {})
        pacs_linked=bool(pacs_snapshot.get('linked'))
        pacs_present=pacs_snapshot.get('present')
        pacs_status=str(pacs_snapshot.get('status') or '').strip().upper()

        pacs_stage_blockers=[]
        pacs_stage_warnings=[]
        pacs_preflight=None

        if not pacs_linked:
            pacs_stage_state='NOT_REQUIRED'
        elif pacs_present is True:
            # The existing PACS destructive-path preflight is request-context aware
            # because it validates the logged-in SUPER_ADMIN.  Legacy/unit callers of
            # the order preview may run with only an application context, so do not
            # invoke that preflight unless the already-resolved actor is SUPER_ADMIN.
            # This keeps the preview read-only and preserves the historical single
            # Orthanc probe contract.
            if not super_admin:
                pacs_stage_state='BLOCKED'
                pacs_stage_blockers.append('SUPER_ADMIN_REQUIRED')
            else:
                pacs_preflight=_rb.granular_delete_images_only_preflight(
                    order,
                    accession,
                    'READ_ONLY_ORCHESTRATION_PREVIEW',
                    cached_orthanc_response=pacs_snapshot.get('_orthanc_response'),
                )
                pacs_stage_blockers=list(pacs_preflight.get('blockers') or [])
                pacs_stage_state='READY' if pacs_preflight.get('allowed') else 'BLOCKED'
        elif pacs_present is False and pacs_status == 'IMAGES_DELETED':
            pacs_stage_state='COMPLETE'
        elif pacs_present is False:
            pacs_stage_state='BLOCKED'
            pacs_stage_blockers.append('PACS_STUDY_ABSENT_WITHOUT_DELETE_CONFIRMATION')
        else:
            pacs_stage_state='BLOCKED'
            pacs_stage_blockers.append('PACS_PRESENCE_UNVERIFIED')

        report_count=int((reports_only_preview or {}).get('report_count') or 0)
        if report_count == 0:
            reports_stage_state='COMPLETE'
            reports_stage_blockers=[]
            reports_stage_warnings=[]
        else:
            reports_stage_blockers=list((reports_only_preview or {}).get('blocker_codes') or [])
            reports_stage_warnings=list((reports_only_preview or {}).get('warnings') or [])
            reports_stage_state=(
                'READY'
                if (reports_only_preview or {}).get('can_delete_reports_only')
                else 'BLOCKED'
            )

        # Project the RIS stage after Reports Only succeeds. The live/current RIS
        # preflight remains untouched and visible separately. Only the report FK and
        # report rows are removed from this in-memory projection; no database state
        # is mutated.
        projected_dependencies=[
            dict(row)
            for row in (dependency_rows or [])
            if not (
                str(row.get('table') or '') == 'report'
                and str(row.get('column') or '') == 'order_id'
            )
        ]
        projected_ris=_rb.granular_delete_ris_case_only_execution_preview_snapshot(
            order,
            projected_dependencies,
            [],
        )
        ris_stage_blockers=list(projected_ris.get('blockers') or [])
        ris_stage_warnings=list(projected_ris.get('warnings') or [])

        if projected_ris.get('can_prepare_execution'):
            ris_stage_state='READY_AFTER_REPORTS' if report_count else 'READY'
        else:
            ris_stage_state='BLOCKED'

        blockers.extend('PACS: '+str(x) for x in pacs_stage_blockers)
        blockers.extend('REPORTS: '+str(x) for x in reports_stage_blockers)
        blockers.extend('RIS: '+str(x) for x in ris_stage_blockers)
        warnings.extend('PACS: '+str(x) for x in pacs_stage_warnings)
        warnings.extend('REPORTS: '+str(x) for x in reports_stage_warnings)
        warnings.extend('RIS: '+str(x) for x in ris_stage_warnings)

        blockers=list(dict.fromkeys(blockers))
        warnings=list(dict.fromkeys(warnings))

        pacs_ready=pacs_stage_state in ('READY','COMPLETE','NOT_REQUIRED')
        reports_ready=reports_stage_state in ('READY','COMPLETE')
        ris_ready=ris_stage_state in ('READY','READY_AFTER_REPORTS')
        can_execute_full_case=bool(
            not blockers
            and super_admin
            and order_status in ('CANCELLED','CANCELED')
            and patient is not None
            and bool(accession)
            and pacs_ready
            and reports_ready
            and ris_ready
        )

        return {
            'readonly':True,
            'execution_enabled':_rb._full_case_orchestration_execution_enabled(),
            'can_execute_full_case':can_execute_full_case,
            'order_id':int(order.id),
            'accession':accession,
            'patient_id':getattr(patient,'patient_id',None) if patient else None,
            'order_status':getattr(order,'status',None),
            'patient_preserved':True,
            'audit_append_only':True,
            'stop_on_stage_failure':True,
            'required_sequence':[
                'PACS_IMAGES_ONLY',
                'REPORTS_ONLY',
                'RIS_CASE_DATA_ONLY',
            ],
            'stages':[
                {
                    'sequence':1,
                    'code':'PACS_IMAGES_ONLY',
                    'state':pacs_stage_state,
                    'blockers':pacs_stage_blockers,
                    'warnings':pacs_stage_warnings,
                    'future_confirmation_required':pacs_stage_state == 'READY',
                },
                {
                    'sequence':2,
                    'code':'REPORTS_ONLY',
                    'state':reports_stage_state,
                    'blockers':reports_stage_blockers,
                    'warnings':reports_stage_warnings,
                    'future_confirmation_required':reports_stage_state == 'READY',
                },
                {
                    'sequence':3,
                    'code':'RIS_CASE_DATA_ONLY',
                    'state':ris_stage_state,
                    'blockers':ris_stage_blockers,
                    'warnings':ris_stage_warnings,
                    'future_confirmation_required':ris_stage_state in ('READY','READY_AFTER_REPORTS'),
                },
            ],
            'current_ris_stage':{
                'can_prepare_execution':bool((ris_case_only_preview or {}).get('can_prepare_execution')),
                'blockers':list((ris_case_only_preview or {}).get('blockers') or []),
            },
            'projected_ris_stage':projected_ris,
            'blockers':blockers,
            'warnings':warnings,
        }
    return granular_delete_full_case_orchestration_preview_snapshot


def install_0600(_rb):
    def _full_case_orchestration_execution_enabled():
        return str(
            _rb.os.environ.get(
                'RADBRIDGE_FULL_CASE_ORCHESTRATION_EXECUTION_ENABLED',
                '0',
            )
            or '0'
        ).strip().lower() in ('1','true','yes','on')
    return _full_case_orchestration_execution_enabled


def install_0601(_rb):
    def _full_case_orchestration_failure(
        order_id,
        accession,
        reason,
        stage,
        error,
        status,
        completed_stages=None,
        details=None,
    ):
        completed=list(completed_stages or [])
        stage_result=(details or {}).get('stage_result') if isinstance(details,dict) else None
        partial_destructive_changes=bool(completed) or bool(
            isinstance(stage_result,dict) and stage_result.get('deleted')
        )
        payload={
            'ok':False,
            'deleted':False,
            'full_case_deleted':False,
            'partial_destructive_changes':partial_destructive_changes,
            'order_id':int(order_id),
            'accession':accession,
            'failed_stage':stage,
            'error':error,
            'completed_stages':completed,
            'stop_on_stage_failure':True,
        }
        if details:
            payload['details']=details

        try:
            _rb.audit(
                'FULL_CASE_DELETE_FAILED_ADMIN',
                'order',
                order_id,
                (
                    f"accession={accession}; stage={stage}; error={error}; "
                    f"completed={','.join(completed)}; reason={reason}"
                ),
            )
            _rb.db.session.commit()
        except Exception:
            _rb.db.session.rollback()

        return payload,status
    return _full_case_orchestration_failure


def install_0602(_rb):
    def _full_case_orchestration_final_postcheck(order_id, patient_id):
        order_present=_rb.db.session.get(_rb.Order,int(order_id)) is not None
        patient_present=_rb.db.session.get(_rb.Patient,int(patient_id)) is not None
        report_count=_rb.Report.query.filter_by(order_id=int(order_id)).count()
        dependency_rows=[]
        if not order_present:
            # Direct order-FK dependencies must be gone/nullified before the Order
            # disappears. The validated RIS executor enforces this immediately
            # before deleting the Order; report_count remains independently checked.
            dependency_count=0
        else:
            dependency_rows=_rb._ris_case_only_dependency_rows(
                _rb.db.session.get(_rb.Order,int(order_id))
            )
            dependency_count=sum(
                int(row.get('count') or 0)
                for row in dependency_rows
                if row.get('count') is not None
            )
        ok=bool(
            not order_present
            and patient_present
            and report_count == 0
            and dependency_count == 0
        )
        return {
            'ok':ok,
            'order_removed':not order_present,
            'patient_preserved':patient_present,
            'report_count':int(report_count),
            'direct_dependency_count':int(dependency_count),
            'dependency_rows':dependency_rows,
        }
    return _full_case_orchestration_final_postcheck


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


def install_0607(_rb):
    def correction_execution_snapshot(
        correction_request,
    ):
        order=correction_request.order

        return {
            'correction_request_id':
                correction_request.id,
            'correction_request_status':
                correction_request.status,
            'request_type':
                correction_request.request_type,
            'requester_id':
                correction_request.requested_by,
            'reviewer_id':
                correction_request.assigned_to,
            'order_id':
                correction_request.order_id,
            'branch_id':
                correction_request.branch_id,
            'order_status':
                getattr(order,'status',None)
                if order else None,
            'exam_status':
                getattr(order,'exam_status',None)
                if order else None,
            'accession':
                getattr(order,'accession',None)
                if order else None,
            'pacs_status':
                getattr(order,'pacs_status',None)
                if order else None,
            'pacs_image_count':
                getattr(order,'pacs_image_count',None)
                if order else None,
            'pacs_study_id':
                getattr(order,'pacs_study_id',None)
                if order else None,
            'study_instance_uid':
                getattr(order,'study_instance_uid',None)
                if order else None,
        }
    return correction_execution_snapshot


def install_0608(_rb):
    def correction_execution_request_lock(
        correction_request_id,
    ):
        return (
            _rb.CorrectionRequest.query
            .filter_by(
                id=correction_request_id
            )
            .with_for_update()
            .first()
        )
    return correction_execution_request_lock


def install_0609(_rb):
    def correction_execution_row_lock(
        execution_id,
    ):
        return (
            _rb.CorrectionExecution.query
            .filter_by(id=execution_id)
            .with_for_update()
            .first()
        )
    return correction_execution_row_lock


def install_0610(_rb):
    def correction_execution_saved_snapshot(
        execution,
    ):
        try:
            value=_rb.json.loads(
                execution.request_snapshot_json
                or '{}'
            )
        except Exception:
            raise ValueError(
                'CORRECTION_EXECUTION_SNAPSHOT_INVALID'
            )

        if not isinstance(value,dict):
            raise ValueError(
                'CORRECTION_EXECUTION_SNAPSHOT_INVALID'
            )

        return value
    return correction_execution_saved_snapshot


def install_0611(_rb):
    def correction_execution_assert_snapshot_current(
        execution,
        correction_request,
    ):
        saved=_rb.correction_execution_saved_snapshot(
            execution
        )

        current=_rb.correction_execution_snapshot(
            correction_request
        )

        mismatches=[]

        for key in _rb.CORRECTION_EXECUTION_SNAPSHOT_KEYS:
            if saved.get(key) != current.get(key):
                mismatches.append(key)

        if mismatches:
            raise ValueError(
                'CORRECTION_EXECUTION_STALE_SNAPSHOT:'
                + ','.join(mismatches)
            )

        return current
    return correction_execution_assert_snapshot_current


def install_0612(_rb):
    def correction_execution_prepare(
        correction_request,
    ):
        if not correction_request:
            raise ValueError(
                'CORRECTION_REQUEST_REQUIRED'
            )

        if not getattr(
            correction_request,
            'id',
            None
        ):
            raise ValueError(
                'CORRECTION_REQUEST_NOT_PERSISTED'
            )

        locked_request=(
            _rb.correction_execution_request_lock(
                correction_request.id
            )
        )

        if not locked_request:
            raise ValueError(
                'CORRECTION_REQUEST_NOT_FOUND'
            )

        if locked_request.status!='APPROVED':
            raise ValueError(
                'CORRECTION_REQUEST_NOT_APPROVED'
            )

        existing=(
            _rb.CorrectionExecution.query
            .filter_by(
                correction_request_id=
                    locked_request.id
            )
            .first()
        )

        if existing:
            raise ValueError(
                'CORRECTION_EXECUTION_ALREADY_EXISTS'
            )

        snapshot=_rb.correction_execution_snapshot(
            locked_request
        )

        row=_rb.CorrectionExecution(
            correction_request_id=
                locked_request.id,
            order_id=
                locked_request.order_id,
            branch_id=
                locked_request.branch_id,
            execution_type=
                locked_request.request_type,
            status='READY_FOR_EXECUTION',
            state_version=1,
            request_snapshot_json=_rb.json.dumps(
                snapshot,
                ensure_ascii=False,
                sort_keys=True,
                default=str,
            ),
            preflight_snapshot_json='{}',
            result_snapshot_json='{}',
        )

        _rb.db.session.add(row)
        _rb.db.session.flush()

        return row
    return correction_execution_prepare


def install_0613(_rb):
    def correction_execution_assert_actor(
        execution,
        user,
    ):
        if not execution:
            raise ValueError(
                'CORRECTION_EXECUTION_REQUIRED'
            )

        if not _rb.correction_execution_user_has_perm(
            user
        ):
            raise PermissionError(
                'CORRECTION_EXECUTE_PERMISSION_REQUIRED'
            )

        req=_rb.correction_execution_request_lock(
            execution.correction_request_id
        )

        if not req:
            raise ValueError(
                'CORRECTION_REQUEST_NOT_FOUND'
            )

        if req.status!='APPROVED':
            raise ValueError(
                'CORRECTION_REQUEST_NO_LONGER_APPROVED'
            )

        if user.id==req.requested_by:
            raise PermissionError(
                'REQUESTER_CANNOT_EXECUTE'
            )

        if (
            req.assigned_to
            and user.id==req.assigned_to
        ):
            raise PermissionError(
                'REVIEWER_CANNOT_EXECUTE'
            )

        if (
            execution.claimed_by
            and execution.claimed_by!=user.id
        ):
            raise PermissionError(
                'CORRECTION_EXECUTION_CLAIMED_BY_ANOTHER_USER'
            )

        order=_rb.db.session.get(
            _rb.Order,
            execution.order_id
        )

        if (
            order
            and not _rb.correction_branch_allowed(
                order,
                user
            )
        ):
            raise PermissionError(
                'CORRECTION_EXECUTION_BRANCH_FORBIDDEN'
            )

        return req
    return correction_execution_assert_actor


def install_0614(_rb):
    def correction_execution_transition(
        execution,
        new_status,
        user=None,
        expected_version=None,
    ):
        if not execution:
            raise ValueError(
                'CORRECTION_EXECUTION_REQUIRED'
            )

        if not getattr(
            execution,
            'id',
            None
        ):
            raise ValueError(
                'CORRECTION_EXECUTION_NOT_PERSISTED'
            )

        locked=_rb.correction_execution_row_lock(
            execution.id
        )

        if not locked:
            raise ValueError(
                'CORRECTION_EXECUTION_NOT_FOUND'
            )

        if expected_version is not None:
            if (
                int(locked.state_version or 0)
                !=
                int(expected_version)
            ):
                raise ValueError(
                    'CORRECTION_EXECUTION_STALE_VERSION'
                )

        new_status=(
            new_status or ''
        ).strip().upper()

        if (
            new_status
            not in _rb.CORRECTION_EXECUTION_STATUSES
        ):
            raise ValueError(
                'INVALID_CORRECTION_EXECUTION_STATUS'
            )

        current=locked.status

        allowed=(
            _rb.CORRECTION_EXECUTION_TRANSITIONS
            .get(
                current,
                set()
            )
        )

        if new_status not in allowed:
            raise ValueError(
                'INVALID_CORRECTION_EXECUTION_TRANSITION'
            )

        req=None

        if user is not None:
            req=_rb.correction_execution_assert_actor(
                locked,
                user
            )

            _rb.correction_execution_assert_snapshot_current(
                locked,
                req
            )

        now=_rb.datetime.utcnow()

        locked.status=new_status

        locked.state_version=(
            int(
                locked.state_version
                or 0
            )
            + 1
        )

        locked.updated_at=now

        if new_status=='CLAIMED_FOR_EXECUTION':
            locked.claimed_by=(
                user.id
                if user else None
            )
            locked.claimed_at=now

        elif new_status=='READY_FOR_EXECUTION':
            locked.claimed_by=None
            locked.claimed_at=None

        elif new_status=='EXECUTING':
            locked.executed_by=(
                user.id
                if user else None
            )
            locked.started_at=now

        elif new_status=='VERIFYING':
            locked.executed_at=now

        elif new_status=='COMPLETED':
            locked.verified_at=now

        elif new_status in (
            'EXECUTION_FAILED',
            'VERIFICATION_FAILED',
        ):
            locked.failed_at=now

        _rb.db.session.flush()

        return locked
    return correction_execution_transition


def install_0615(_rb):
    def correction_execution_hold(
        execution,
        user,
        expected_version=None,
    ):
        return _rb.correction_execution_transition(
            execution,
            'ON_HOLD',
            user,
            expected_version=expected_version,
        )
    return correction_execution_hold


def install_0616(_rb):
    def correction_execution_release(
        execution,
        user,
        expected_version=None,
    ):
        return _rb.correction_execution_transition(
            execution,
            'READY_FOR_EXECUTION',
            user,
            expected_version=expected_version,
        )
    return correction_execution_release


def install_0617(_rb):
    def correction_can_request():
        return _rb.has_perm('correction.request') or _rb.has_perm('correction.review')
    return correction_can_request


def install_0618(_rb):
    def correction_can_review():
        return _rb.has_perm('correction.review')
    return correction_can_review


def install_0619(_rb):
    def correction_branch_allowed(order, user=None):
        user=user or _rb.current_user()
        if not user or not order:
            return False
        if user.role and user.role.code=='SUPER_ADMIN':
            return True
        # Global correction reviewers may operate across branches. Request-only
        # users without an explicit branch fail closed instead of gaining global
        # access accidentally.
        if not user.branch_id:
            return bool(_rb.has_perm('correction.review'))
        return int(order.branch_id or 0)==int(user.branch_id)
    return correction_branch_allowed


def install_0620(_rb):
    def correction_search_orders(term, user=None, limit=50):
        term=(term or '').strip()
        if not term:
            return []
        user=user or _rb.current_user()
        q=_rb.Order.query.join(_rb.Patient,_rb.Order.patient_id==_rb.Patient.id)
        if user and not (user.role and user.role.code=='SUPER_ADMIN'):
            if user.branch_id:
                q=q.filter(_rb.Order.branch_id==user.branch_id)
            elif not _rb.has_perm('correction.review'):
                return []
        like=f'%{term}%'
        filters=[
            _rb.Order.accession.ilike(like),
            _rb.Patient.patient_id.ilike(like),
            _rb.Patient.name.ilike(like),
            _rb.Patient.phone.ilike(like),
        ]
        if term.isdigit():
            filters.append(_rb.Order.id==int(term))
        return q.filter(_rb.db.or_(*filters)).order_by(_rb.Order.id.desc()).limit(limit).all()
    return correction_search_orders


def install_0625(_rb):
    def correction_execution_assert_request_actor(
        correction_request,
        user,
    ):
        if not correction_request:
            raise ValueError(
                'CORRECTION_REQUEST_REQUIRED'
            )

        if not _rb.correction_execution_user_has_perm(
            user
        ):
            raise PermissionError(
                'CORRECTION_EXECUTE_PERMISSION_REQUIRED'
            )

        if correction_request.status!='APPROVED':
            raise ValueError(
                'CORRECTION_REQUEST_NOT_APPROVED'
            )

        if user.id==correction_request.requested_by:
            raise PermissionError(
                'REQUESTER_CANNOT_EXECUTE'
            )

        if (
            correction_request.assigned_to
            and user.id==correction_request.assigned_to
        ):
            raise PermissionError(
                'REVIEWER_CANNOT_EXECUTE'
            )

        order=correction_request.order

        if (
            order
            and not _rb.correction_branch_allowed(
                order,
                user
            )
        ):
            raise PermissionError(
                'CORRECTION_EXECUTION_BRANCH_FORBIDDEN'
            )

        return correction_request
    return correction_execution_assert_request_actor


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


def install_0632(_rb):
    def correction_wrong_images_execute(
        execution_id,
        actor,
        expected_version,
        typed_accession,
        reason,
    ):
        execution=(
            _rb.CorrectionExecution.query
            .filter_by(id=execution_id)
            .with_for_update()
            .first()
        )

        if not execution:
            return {
                'ok':False,
                'error':'EXECUTION_NOT_FOUND',
            },404

        request_row=(
            _rb.CorrectionRequest.query
            .filter_by(
                id=execution.correction_request_id
            )
            .with_for_update()
            .first()
        )

        if not request_row:
            return {
                'ok':False,
                'error':'CORRECTION_REQUEST_NOT_FOUND',
            },404

        order=(
            _rb.Order.query
            .filter_by(id=execution.order_id)
            .with_for_update()
            .first()
        )

        if not order:
            return {
                'ok':False,
                'error':'ORDER_NOT_FOUND',
            },404

        if execution.execution_type!='WRONG_IMAGES':
            return {
                'ok':False,
                'error':'EXECUTION_TYPE_MISMATCH',
            },409

        if request_row.request_type!='WRONG_IMAGES':
            return {
                'ok':False,
                'error':'REQUEST_TYPE_MISMATCH',
            },409

        if request_row.status!='APPROVED':
            return {
                'ok':False,
                'error':'REQUEST_NOT_APPROVED',
            },409

        if execution.status!='CLAIMED_FOR_EXECUTION':
            return {
                'ok':False,
                'error':'EXECUTION_NOT_CLAIMED',
            },409

        if execution.claimed_by!=actor.id:
            return {
                'ok':False,
                'error':'EXECUTION_CLAIM_OWNER_MISMATCH',
            },409

        if request_row.requested_by==actor.id:
            return {
                'ok':False,
                'error':'REQUESTER_CANNOT_EXECUTE',
            },409

        if request_row.assigned_to==actor.id:
            return {
                'ok':False,
                'error':'REVIEWER_CANNOT_EXECUTE',
            },409

        try:
            expected_version=int(expected_version)
        except (TypeError,ValueError):
            return {
                'ok':False,
                'error':'INVALID_EXPECTED_VERSION',
            },400

        if execution.state_version!=expected_version:
            return {
                'ok':False,
                'error':'STALE_VERSION',
                'current_version':execution.state_version,
            },409

        try:
            _rb.correction_execution_assert_snapshot_current(
                execution,
                request_row,
            )
        except ValueError as exc:
            return {
                'ok':False,
                'error':str(exc),
            },409

        # Run and persist the full preflight before entering the execution path.
        preflight=_rb.granular_delete_images_only_preflight(
            order,
            typed_accession,
            reason,
        )

        preflight_snapshot={
            key:value
            for key,value in preflight.items()
            if key not in (
                'patient',
                'orthanc_payload',
            )
        }

        execution.preflight_snapshot_json=_rb.json.dumps(
            preflight_snapshot,
            ensure_ascii=False,
            sort_keys=True,
            default=str,
        )

        _rb.db.session.flush()

        if not preflight.get('allowed'):
            execution=_rb.correction_execution_transition(
                execution,
                'PREFLIGHT_BLOCKED',
                None,
                expected_version=execution.state_version,
            )

            execution.failure_code='PREFLIGHT_BLOCKED'
            execution.failure_message=';'.join(
                preflight.get('blockers')
                or ()
            )[:2000]

            _rb.audit(
                'CORRECTION_EXECUTION_PREFLIGHT_BLOCKED',
                'correction_execution',
                execution.id,
                (
                    f'order_id={order.id};'
                    f'accession={order.accession};'
                    f'actor={actor.id};'
                    f'blockers={execution.failure_message};'
                    f'state_version={execution.state_version}'
                ),
            )

            _rb.db.session.commit()

            return {
                'ok':False,
                'deleted':False,
                'ris_state_updated':False,
                'error':'PREFLIGHT_BLOCKED',
                'blockers':
                    preflight.get('blockers')
                    or [],
            },409

        # CLAIMED_FOR_EXECUTION -> PREFLIGHT_PASSED
        execution=_rb.correction_execution_transition(
                execution,
                'PREFLIGHT_PASSED',
                None,
                expected_version=execution.state_version,
            )

        _rb.audit(
            'CORRECTION_EXECUTION_PREFLIGHT_PASSED',
            'correction_execution',
            execution.id,
            (
                f'order_id={order.id};'
                f'accession={order.accession};'
                f'actor={actor.id};'
                f'state_version={execution.state_version}'
            ),
        )

        _rb.db.session.commit()

        # PREFLIGHT_PASSED -> EXECUTING immediately before the
        # primitive is allowed to cross the Orthanc DELETE boundary.
        execution=_rb.correction_execution_transition(
                execution,
                'EXECUTING',
                None,
                expected_version=execution.state_version,
            )

        execution.executed_by=actor.id

        _rb.audit(
            'CORRECTION_EXECUTION_STARTED',
            'correction_execution',
            execution.id,
            (
                f'order_id={order.id};'
                f'accession={order.accession};'
                f'actor={actor.id};'
                f'state_version={execution.state_version}'
            ),
        )

        _rb.db.session.commit()

        verifying_state={
            'entered':False,
        }

        def enter_verifying():
            current=(
                _rb.CorrectionExecution.query
                .filter_by(id=execution_id)
                .with_for_update()
                .first()
            )

            if not current:
                raise RuntimeError(
                    'EXECUTION_LOST_AFTER_DELETE'
                )

            current=_rb.correction_execution_transition(
                current,
                'VERIFYING',
                None,
                expected_version=current.state_version,
            )

            _rb.audit(
                'CORRECTION_EXECUTION_VERIFYING',
                'correction_execution',
                current.id,
                (
                    f'order_id={order.id};'
                    f'accession={order.accession};'
                    f'actor={actor.id};'
                    f'state_version={current.state_version}'
                ),
            )

            _rb.db.session.commit()

            verifying_state['entered']=True

        payload,status_code=_rb.granular_delete_images_only_execute(
            order,
            typed_accession,
            reason,
            preflight=preflight,
            after_delete=enter_verifying,
        )

        execution=(
            _rb.CorrectionExecution.query
            .filter_by(id=execution_id)
            .with_for_update()
            .first()
        )

        if not execution:
            return {
                'ok':False,
                'error':'EXECUTION_LOST_AFTER_DELETE',
            },500

        execution.result_snapshot_json=_rb.json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            default=str,
        )

        deleted=bool(
            payload.get('deleted')
        )

        ris_state_updated=bool(
            payload.get('ris_state_updated')
        )

        if (
            status_code==200
            and payload.get('ok') is True
            and deleted
            and ris_state_updated
        ):
            # VERIFYING -> COMPLETED.
            # user=None is intentional because successful RIS PACS-state
            # mutation changes the original request snapshot.
            execution=_rb.correction_execution_transition(
                execution,
                'COMPLETED',
                None,
                expected_version=execution.state_version,
            )

            execution.failure_code=None
            execution.failure_message=None

            request_row=(
                _rb.CorrectionRequest.query
                .filter_by(
                    id=execution.correction_request_id
                )
                .with_for_update()
                .first()
            )

            if request_row:
                request_row.status='COMPLETED'
                request_row.closed_at=_rb.datetime.utcnow()
                request_row.updated_at=_rb.datetime.utcnow()

            _rb.audit(
                'CORRECTION_EXECUTION_COMPLETED',
                'correction_execution',
                execution.id,
                (
                    f'order_id={order.id};'
                    f'accession={order.accession};'
                    f'actor={actor.id};'
                    f'state_version={execution.state_version}'
                ),
            )

            _rb.db.session.commit()

            return payload,200

        failure_error=(
            payload.get('error')
            or 'UNKNOWN_EXECUTION_FAILURE'
        )

        if not deleted:
            target_status='EXECUTION_FAILED'

        else:
            if not verifying_state['entered']:
                # DELETE may already have happened. Leave EXECUTING as an
                # uncertain hard-blocked state rather than pretending that
                # execution safely failed before the destructive boundary.
                _rb.db.session.rollback()

                return {
                    'ok':False,
                    'deleted':True,
                    'ris_state_updated':False,
                    'error':
                        'VERIFYING_STATE_NOT_ENTERED_AFTER_DELETE',
                },500

            target_status='VERIFICATION_FAILED'

        execution=_rb.correction_execution_transition(
                execution,
                target_status,
                None,
                expected_version=execution.state_version,
            )

        execution.failure_code=str(
            failure_error
        )[:80]

        execution.failure_message=str(
            failure_error
        )[:2000]

        _rb.audit(
            'CORRECTION_EXECUTION_FAILED',
            'correction_execution',
            execution.id,
            (
                f'order_id={order.id};'
                f'accession={order.accession};'
                f'actor={actor.id};'
                f'status={execution.status};'
                f'error={failure_error};'
                f'state_version={execution.state_version}'
            ),
        )

        _rb.db.session.commit()

        return payload,status_code
    return correction_wrong_images_execute


def install_0645(_rb):
    def migrate_existing_schema():
        # SQLAlchemy create_all creates new tables but does not alter old Order/Patient tables.
        inspector=_rb.inspect(_rb.db.engine)
        tables=set(inspector.get_table_names())
        if 'branch' in tables and 'reception_collection_enabled' not in {c['name'] for c in inspector.get_columns('branch')}:
            _rb.db.session.execute(_rb.text('ALTER TABLE branch ADD COLUMN reception_collection_enabled BOOLEAN DEFAULT FALSE NOT NULL'))
        if 'patient' in tables:
            cols={c['name'] for c in inspector.get_columns('patient')}
            additions={
              'national_id':'VARCHAR(30)',
              'address':'VARCHAR(255)',
              'created_at':'TIMESTAMP',
              'dob_estimated':'BOOLEAN DEFAULT FALSE NOT NULL'
            }
            for col,typ in additions.items():
                if col not in cols:
                    _rb.db.session.execute(_rb.text(f'ALTER TABLE patient ADD COLUMN {col} {typ}'))
        if 'device' in tables:
            cols={c['name'] for c in inspector.get_columns('device')}
            additions={
              'operational_status':"VARCHAR(30) DEFAULT 'ACTIVE'",
              'booking_enabled':'BOOLEAN DEFAULT TRUE',
              'workday_start':"VARCHAR(5) DEFAULT '08:00'",
              'workday_end':"VARCHAR(5) DEFAULT '22:00'"
            }
            for col,typ in additions.items():
                if col not in cols:
                    _rb.db.session.execute(_rb.text(f'ALTER TABLE device ADD COLUMN IF NOT EXISTS {col} {typ}'))

        if 'appointment' in tables:
            cols={c['name'] for c in inspector.get_columns('appointment')}
            additions={
              'confirmed_at':'TIMESTAMP',
              'duration_min':'INTEGER DEFAULT 20',
              'priority':"VARCHAR(20) DEFAULT 'NORMAL'",
              'waiting_list':'BOOLEAN DEFAULT FALSE'
            }
            for col,typ in additions.items():
                if col not in cols:
                    _rb.db.session.execute(_rb.text(f'ALTER TABLE appointment ADD COLUMN IF NOT EXISTS {col} {typ}'))

        if 'consumable' in tables:
            cols={c['name'] for c in inspector.get_columns('consumable')}
            additions={
              'name_en':"VARCHAR(160) DEFAULT ''",
              'name_ar':"VARCHAR(160) DEFAULT ''",
              'barcode':"VARCHAR(80) DEFAULT ''",
              'category':"VARCHAR(100) DEFAULT ''",
              'selling_price':'FLOAT DEFAULT 0',
              'expiry_tracking':'BOOLEAN DEFAULT FALSE'
            }
            for col,typ in additions.items():
                if col not in cols:
                    _rb.db.session.execute(_rb.text(f'ALTER TABLE consumable ADD COLUMN IF NOT EXISTS {col} {typ}'))

        if 'procedure' in tables:
            cols={c['name'] for c in inspector.get_columns('procedure')}
            additions={'name_ar':'VARCHAR(180)','category':'VARCHAR(80)'}
            for col,typ in additions.items():
                if col not in cols:
                    _rb.db.session.execute(_rb.text(f'ALTER TABLE procedure ADD COLUMN IF NOT EXISTS {col} {typ}'))
        if 'order' in tables:
            cols={c['name'] for c in inspector.get_columns('order')}
            additions={
              'procedure_id':'INTEGER','branch_id':'INTEGER','device_id':'INTEGER','contract_id':'INTEGER',
              'gross_price':'FLOAT DEFAULT 0','contract_price':'FLOAT DEFAULT 0','patient_share':'FLOAT DEFAULT 0',
              'company_share':'FLOAT DEFAULT 0','paid_amount':'FLOAT DEFAULT 0','approval_no':'VARCHAR(80)',
              'created_by':'INTEGER','created_at':'TIMESTAMP','referring_doctor_id':'INTEGER','report_delivered':'BOOLEAN DEFAULT FALSE','images_delivered':'BOOLEAN DEFAULT FALSE','report_delivered_at':'TIMESTAMP','images_delivered_at':'TIMESTAMP'
            }
            for col,typ in additions.items():
                if col not in cols:
                    _rb.db.session.execute(_rb.text(f'ALTER TABLE "order" ADD COLUMN IF NOT EXISTS {col} {typ}'))

        if 'appointment' in tables:
            cols={c['name'] for c in inspector.get_columns('appointment')}
            additions={'device_id':'INTEGER','checked_in_at':'TIMESTAMP','cancelled_at':'TIMESTAMP'}
            for col,typ in additions.items():
                if col not in cols:
                    _rb.db.session.execute(_rb.text(f'ALTER TABLE appointment ADD COLUMN IF NOT EXISTS {col} {typ}'))

        if 'report' in tables:
            cols={c['name'] for c in inspector.get_columns('report')}
            additions={'source_path':'VARCHAR(500)','source_type':"VARCHAR(20) DEFAULT 'DOCX'"}
            for col,typ in additions.items():
                if col not in cols:
                    _rb.db.session.execute(_rb.text(f'ALTER TABLE report ADD COLUMN IF NOT EXISTS {col} {typ}'))
        if 'storage_location' in tables:
            cols={c['name'] for c in inspector.get_columns('storage_location')}
            additions={
              'protocol':"VARCHAR(30) DEFAULT 'LOCAL'",'role':"VARCHAR(30) DEFAULT 'PRIMARY'",
              'branch_id':'INTEGER','company_code':"VARCHAR(60) DEFAULT ''",'vendor':"VARCHAR(80) DEFAULT ''",
              'endpoint':"VARCHAR(255) DEFAULT ''",'mount_source':"VARCHAR(500) DEFAULT ''",
              'filesystem':"VARCHAR(40) DEFAULT ''",'priority':'INTEGER DEFAULT 100','read_only':'BOOLEAN DEFAULT FALSE',
              'capacity_bytes':'BIGINT DEFAULT 0','free_bytes':'BIGINT DEFAULT 0',
              'health_status':"VARCHAR(30) DEFAULT 'UNKNOWN'",'last_health_at':'TIMESTAMP','notes':"TEXT DEFAULT ''"}
            for col,typ in additions.items():
                if col not in cols:
                    _rb.db.session.execute(_rb.text(f'ALTER TABLE storage_location ADD COLUMN IF NOT EXISTS {col} {typ}'))

        if 'report_version' in tables:
            cols={c['name'] for c in inspector.get_columns('report_version')}
            additions={'source_path':'VARCHAR(500)','source_type':"VARCHAR(20) DEFAULT 'DOCX'"}
            for col,typ in additions.items():
                if col not in cols:
                    _rb.db.session.execute(_rb.text(f'ALTER TABLE report_version ADD COLUMN IF NOT EXISTS {col} {typ}'))


        if 'report' in tables:
            cols={c['name'] for c in inspector.get_columns('report')}
            additions={
                'verified_by':'VARCHAR(160)',
                'verified_at':'TIMESTAMP',
                'second_verified_by':'VARCHAR(160)',
                'second_verified_at':'TIMESTAMP',
                'finalized_by':'VARCHAR(160)',
                'addendum_no':'INTEGER DEFAULT 0'
            }
            for col,typ in additions.items():
                if col not in cols:
                    _rb.db.session.execute(_rb.text(f'ALTER TABLE report ADD COLUMN IF NOT EXISTS {col} {typ}'))

        if 'order' in tables:
            cols={c['name'] for c in inspector.get_columns('order')}
            additions={
                'priority':"VARCHAR(20) DEFAULT 'ROUTINE'",
                'assigned_doctor_id':'INTEGER',
                'assigned_at':'TIMESTAMP'
            }
            for col,typ in additions.items():
                if col not in cols:
                    _rb.db.session.execute(_rb.text(f'ALTER TABLE "order" ADD COLUMN IF NOT EXISTS {col} {typ}'))

        if 'patient' in tables:
            cols={c['name'] for c in inspector.get_columns('patient')}
            if 'worklist_name' not in cols:
                _rb.db.session.execute(_rb.text("ALTER TABLE patient ADD COLUMN IF NOT EXISTS worklist_name VARCHAR(180)"))
            if 'email' not in cols:
                _rb.db.session.execute(_rb.text("ALTER TABLE patient ADD COLUMN IF NOT EXISTS email VARCHAR(180) DEFAULT ''"))

        if 'order' in tables:
            cols={c['name'] for c in inspector.get_columns('order')}
            additions={
                'exam_status':"VARCHAR(30) DEFAULT 'ORDERED'",
                'exam_started_at':'TIMESTAMP',
                'exam_completed_at':'TIMESTAMP',
                'pacs_image_count':'INTEGER DEFAULT 0',
                'pacs_status':"VARCHAR(30) DEFAULT 'WAITING'",
                'pacs_last_seen_at':'TIMESTAMP',
                'pacs_last_change_at':'TIMESTAMP',
                'pacs_study_id':"VARCHAR(120) DEFAULT ''"
            }
            for col,typ in additions.items():
                if col not in cols:
                    _rb.db.session.execute(_rb.text(f'ALTER TABLE "order" ADD COLUMN IF NOT EXISTS {col} {typ}'))

        if 'pacs_transfer_job' in tables:
            cols={c['name'] for c in inspector.get_columns('pacs_transfer_job')}
            additions={
                'started_at':'TIMESTAMP','cancelled_at':'TIMESTAMP',
                'progress_total':'INTEGER DEFAULT 0','progress_sent':'INTEGER DEFAULT 0'
            }
            for col,typ in additions.items():
                if col not in cols:
                    _rb.db.session.execute(_rb.text(f'ALTER TABLE pacs_transfer_job ADD COLUMN IF NOT EXISTS {col} {typ}'))

        if 'user' in tables:
            cols={c['name'] for c in inspector.get_columns('user')}
            additions={'must_change_password':'BOOLEAN DEFAULT FALSE','password_changed_at':'TIMESTAMP'}
            for col,typ in additions.items():
                if col not in cols:
                    _rb.db.session.execute(_rb.text(f'ALTER TABLE "user" ADD COLUMN IF NOT EXISTS {col} {typ}'))
        if 'nursing_consumable_entry' in tables:
            cols={c['name'] for c in inspector.get_columns('nursing_consumable_entry')}
            additions={'corrected_by':'INTEGER','corrected_at':'TIMESTAMP','correction_reason':"VARCHAR(500) DEFAULT ''"}
            for col,typ in additions.items():
                if col not in cols:
                    _rb.db.session.execute(_rb.text(f'ALTER TABLE nursing_consumable_entry ADD COLUMN IF NOT EXISTS {col} {typ}'))


        if 'storage_location' in tables:
            cols={c['name'] for c in inspector.get_columns('storage_location')}
            additions={
              'protocol':"VARCHAR(30) DEFAULT 'LOCAL'",'role':"VARCHAR(30) DEFAULT 'PRIMARY'",
              'branch_id':'INTEGER','company_code':"VARCHAR(60) DEFAULT ''",'vendor':"VARCHAR(80) DEFAULT ''",
              'endpoint':"VARCHAR(255) DEFAULT ''",'mount_source':"VARCHAR(500) DEFAULT ''",
              'filesystem':"VARCHAR(40) DEFAULT ''",'priority':'INTEGER DEFAULT 100','read_only':'BOOLEAN DEFAULT FALSE',
              'capacity_bytes':'BIGINT DEFAULT 0','free_bytes':'BIGINT DEFAULT 0',
              'health_status':"VARCHAR(30) DEFAULT 'UNKNOWN'",'last_health_at':'TIMESTAMP','notes':"TEXT DEFAULT ''"}
            for col,typ in additions.items():
                if col not in cols:
                    _rb.db.session.execute(_rb.text(f'ALTER TABLE storage_location ADD COLUMN IF NOT EXISTS {col} {typ}'))

        if 'report_version' in tables:
            cols={c['name'] for c in inspector.get_columns('report_version')}
            additions={'created_by':'INTEGER','created_role':"VARCHAR(60) DEFAULT ''",
              'change_summary':"VARCHAR(500) DEFAULT ''",'sha256':"VARCHAR(64) DEFAULT ''",'file_size':'INTEGER DEFAULT 0'}
            for col,typ in additions.items():
                if col not in cols:
                    _rb.db.session.execute(_rb.text(f'ALTER TABLE report_version ADD COLUMN IF NOT EXISTS {col} {typ}'))

        if 'ocr_provider_setting' in tables:
            cols={c['name'] for c in inspector.get_columns('ocr_provider_setting')}
            additions={
              'validation_status':"VARCHAR(40) DEFAULT 'NOT_CHECKED'",
              'validation_details':"TEXT DEFAULT '{}'",
              'validation_config_hash':"VARCHAR(64) DEFAULT ''",
              'validation_latency_ms':'INTEGER',
              'validated_by':'INTEGER',
              'validated_at':'TIMESTAMP'
            }
            for col,typ in additions.items():
                if col not in cols:
                    _rb.db.session.execute(_rb.text(f'ALTER TABLE ocr_provider_setting ADD COLUMN IF NOT EXISTS {col} {typ}'))

        if 'smart_intake_session' in tables:
            cols={c['name'] for c in inspector.get_columns('smart_intake_session')}
            additions={
              'matched_patient_score':'DOUBLE PRECISION DEFAULT 0',
              'match_resolution':"VARCHAR(40) DEFAULT 'NOT_CHECKED'",
              'review_notes':"TEXT DEFAULT ''",'reviewed_by':'INTEGER','reviewed_at':'TIMESTAMP',
              'commit_key':'VARCHAR(64)','commit_action':"VARCHAR(30) DEFAULT ''",
              'committed_by':'INTEGER','committed_at':'TIMESTAMP','completed_at':'TIMESTAMP'}
            for col,typ in additions.items():
                if col not in cols:
                    _rb.db.session.execute(_rb.text(f'ALTER TABLE smart_intake_session ADD COLUMN IF NOT EXISTS {col} {typ}'))

        if 'smart_intake_document' in tables:
            cols={c['name'] for c in inspector.get_columns('smart_intake_document')}
            additions={
              'content_sha256':"VARCHAR(64) DEFAULT ''",'ocr_provider_key':"VARCHAR(60) DEFAULT ''",
              'ocr_config_hash':"VARCHAR(64) DEFAULT ''",'ocr_error':"VARCHAR(500) DEFAULT ''",
              'review_notes':"TEXT DEFAULT ''",'patient_document_id':'INTEGER'}
            for col,typ in additions.items():
                if col not in cols:
                    _rb.db.session.execute(_rb.text(f'ALTER TABLE smart_intake_document ADD COLUMN IF NOT EXISTS {col} {typ}'))

        _rb.db.session.commit()
    return migrate_existing_schema


def install_0646(_rb):
    def seed_master_data():
        if _rb.Branch.query.count()==0:
            _rb.db.session.add(_rb.Branch(code='MAIN',name='Main Branch',active=True)); _rb.db.session.commit()
        for code,perms in _rb.ROLE_PERMS.items():
            r=_rb.Role.query.filter_by(code=code).first()
            if not r:
                _rb.db.session.add(_rb.Role(code=code,name=code.replace('_',' ').title(),permissions_json=_rb.json.dumps(perms)))
        _rb.db.session.commit()

        # RB_CORRECTION_PERMISSION_DEFAULTS_V1
        # Append only the new correction permissions to standard roles. Existing
        # custom permissions remain untouched and execution is never granted here.
        correction_defaults={
            'RECEPTION': {'correction.request'},
            'TECHNICIAN': {'correction.request'},
            'BRANCH_MANAGER': {'correction.request'},
            'CASE_COORDINATOR': {'correction.request','correction.review'},
        }
        for code,required in correction_defaults.items():
            role=_rb.Role.query.filter_by(code=code).first()
            if not role:
                continue
            current=set(role.permissions())
            missing=required-current
            if missing:
                role.permissions_json=_rb.json.dumps(sorted(current|required))
        _rb.db.session.commit()
        if _rb.User.query.count()==0:
            admin_role=_rb.Role.query.filter_by(code='SUPER_ADMIN').first()
            admin_password=(_rb.os.getenv('RIS_ADMIN_PASSWORD') or '').strip()
            if not admin_password:
                raise RuntimeError('RIS_ADMIN_PASSWORD is required when creating the initial administrator')
            _rb.db.session.add(_rb.User(username='admin',full_name='System Administrator',
                password_hash=_rb.generate_password_hash(admin_password),
                role_id=admin_role.id,branch_id=_rb.Branch.query.first().id,active=True))
            _rb.db.session.commit()
        if _rb.Contract.query.count()==0:
            _rb.db.session.add(_rb.Contract(code='CASH',name='Cash / Private',patient_share_percent=100,discount_percent=0,approval_required=False,active=True))
            _rb.db.session.commit()
        _rb.storage_defaults()

        # Comprehensive bilingual procedure catalog.
        # Upsert by code so existing customer prices are preserved.
        for code,name_en,name_ar,modality,body,price,duration,contrast,category in _rb.PROCEDURE_CATALOG:
            p=_rb.Procedure.query.filter_by(code=code).first()
            if not p:
                _rb.db.session.add(_rb.Procedure(code=code,name=name_en,name_ar=name_ar,category=category,modality=modality,
                    body_part=body,base_price=price,duration_min=duration,contrast=contrast,active=True))
            else:
                # Keep existing configured prices, but enrich names/catalog metadata.
                p.name=name_en
                p.name_ar=name_ar
                p.category=category
                if not p.body_part: p.body_part=body
                if not p.modality: p.modality=modality
                if not p.duration_min: p.duration_min=duration
        _rb.db.session.commit()

        # starter consumables and automatic mapping for contrast studies
        starters=[
          ('CANNULA20','IV Cannula 20G','unit',100,20,8),
          ('SYR20','Syringe 20 ml','unit',100,20,5),
          ('SALINE500','Normal Saline 500 ml','bag',50,10,25),
          ('CTCONTRAST100','Non-ionic CT Contrast 100 ml','vial',20,5,650),
          ('GAD10','Gadolinium 10 ml','vial',20,5,900),
        ]
        for code,name,unit,stock,reorder,cost in starters:
            if not _rb.Consumable.query.filter_by(code=code).first():
                _rb.db.session.add(_rb.Consumable(code=code,name=name,unit=unit,stock_qty=stock,reorder_level=reorder,unit_cost=cost,active=True))
        _rb.db.session.commit()
        cann=_rb.Consumable.query.filter_by(code='CANNULA20').first()
        syr=_rb.Consumable.query.filter_by(code='SYR20').first()
        sal=_rb.Consumable.query.filter_by(code='SALINE500').first()
        ct=_rb.Consumable.query.filter_by(code='CTCONTRAST100').first()
        gad=_rb.Consumable.query.filter_by(code='GAD10').first()
        for p in _rb.Procedure.query.filter_by(contrast=True).all():
            default=[(cann,1),(syr,1),(sal,1),(gad if p.modality=='MR' else ct,1)]
            for c,q in default:
                if c and not _rb.ProcedureConsumable.query.filter_by(procedure_id=p.id,consumable_id=c.id).first():
                    _rb.db.session.add(_rb.ProcedureConsumable(procedure_id=p.id,consumable_id=c.id,qty=q))
        _rb.db.session.commit()
    return seed_master_data


def install_0686(_rb):
    def _open_pool_visible_to_doctor(order,user):
        if not user or not user.active:
            return False

        profile=_rb.DoctorAssignmentProfile.query.filter_by(
            user_id=user.id
        ).first()

        if not profile:
            return False

        if not profile.auto_assign or not profile.available:
            return False

        modalities=[
            x.strip().upper()
            for x in (profile.modalities or '').split(',')
            if x.strip()
        ]

        if modalities and str(order.modality or '').upper() not in modalities:
            return False

        branches=[
            x.strip()
            for x in (profile.branches or '').split(',')
            if x.strip()
        ]

        if branches and str(order.branch_id or '') not in branches:
            return False

        active_cases=_rb.CaseAssignment.query.filter_by(
            doctor_user_id=user.id,
            active=True
        ).count()

        max_cases=int(profile.max_active_cases or 20)

        if active_cases>=max_cases:
            return False

        return True
    return _open_pool_visible_to_doctor


def install_0726(_rb):
    def _saved_view_page_or_404(page_key):
        key=(page_key or '').strip().upper()
        if key not in _rb.SAVED_VIEW_PAGES:
            _rb.abort(404)
        from staff_worklist_filters import page_access
        page_access(_rb._reporting_support_sys.modules[__name__],key)
        return key
    return _saved_view_page_or_404


def install_0727(_rb):
    def _saved_view_filtered_data(page_key, source):
        if not isinstance(source,dict) and not hasattr(source,'items'):return {}
        allowed=_rb.SAVED_VIEW_FILTER_KEYS.get(page_key,set())
        return {
            k:v for k,v in source.items()
            if k in allowed and str(v).strip() != ''
        }
    return _saved_view_filtered_data


def install_0728(_rb):
    def _saved_views_for(page_key):
        return (
            _rb.SavedSearchFilter.query
            .filter_by(
                user_id=_rb.current_user().id,
                page_key=page_key
            )
            .order_by(
                _rb.SavedSearchFilter.is_default.desc(),
                _rb.SavedSearchFilter.name
            )
            .all()
        )
    return _saved_views_for


def install_0756(_rb):
    def _ocr_config_from_input(source):
        try:
            timeout=int(source.get('timeout_seconds',60) or 60)
        except (TypeError,ValueError):
            timeout=-1
        return {
          'enabled':source.get('enabled') in (True,1,'1','true','True','yes','on'),
          'provider_key':(source.get('provider_key') or 'GENERIC_OCR_REST').strip().upper(),
          'base_url':(source.get('base_url') or '').strip(),
          'model_name':(source.get('model_name') or '').strip(),
          'timeout_seconds':timeout,
          'secret_env_name':(source.get('secret_env_name') or 'RIS_OCR_API_KEY').strip(),
        }
    return _ocr_config_from_input


def install_0757(_rb):
    def _ocr_saved_validation(row):
        if not row:
            return {'overall':'NOT_CONFIGURED','message':'Save OCR settings before provider validation.'}
        try:
            details=_rb.json.loads(row.validation_details or '{}')
            if not isinstance(details,dict): details={}
        except Exception:
            details={}
        current_hash=_rb.ocr_configuration_hash(row)
        if not row.validation_config_hash or row.validation_config_hash!=current_hash:
            return {
              'overall':'CONFIG_CHANGED',
              'message':'Configuration changed after the last validation.',
              'validated_at':row.validated_at.isoformat()+'Z' if row.validated_at else None,
            }
        details.setdefault('overall',row.validation_status or 'NOT_CHECKED')
        details.setdefault('latency_ms',row.validation_latency_ms)
        details.setdefault('validated_at',row.validated_at.isoformat()+'Z' if row.validated_at else None)
        return details
    return _ocr_saved_validation


def install_0758(_rb):
    def _store_ocr_validation(row,result):
        if not row or result.get('config_hash')!=_rb.ocr_configuration_hash(row):
            return False
        row.validation_status=(result.get('overall') or 'NOT_CHECKED')[:40]
        row.validation_details=_rb.json.dumps(result,ensure_ascii=False)[:12000]
        row.validation_config_hash=result.get('config_hash') or ''
        row.validation_latency_ms=result.get('latency_ms')
        row.validated_by=_rb.current_user().id if _rb.current_user() else None
        row.validated_at=_rb.datetime.utcnow()
        return True
    return _store_ocr_validation


def install_0772(_rb):
    @_rb.app.context_processor
    def inject_studio_shortcuts():
        return {
            'studio_shortcuts_for': _rb.studio_shortcuts_for,
            'studio_icon_map': _rb.STUDIO_ICON_MAP,
        }
    return inject_studio_shortcuts


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


def install_0858(_rb):
    def _normalize_case_uid(value):
        return str(value or '').strip()
    return _normalize_case_uid


def install_0895(_rb):
    def _rb_authoritative_docx_download(order, report):
        if (report.status or '').upper() == 'FINAL':
            corrected = _rb._rb_final_revision_document(order)
            if corrected:return corrected

        version = _rb._rb_latest_report_version(report)

        if not version:
            return None

        path = version.docx_path or version.source_path

        if not path or not _rb.os.path.isfile(path):
            return None

        status = (
            'FINAL'
            if (report.status or '').upper() == 'FINAL'
            else (version.status or report.status or 'REPORT').upper()
        )

        return {
            'path': path,
            'version_no': version.version_no,
            'status': status,
        }
    return _rb_authoritative_docx_download


def install_0896(_rb):
    def _rb_latest_authoritative_version(report):
        return (
            _rb.ReportVersion.query
            .filter(
                _rb.ReportVersion.report_id == report.id,
                _rb.ReportVersion.status.in_([
                    'VERIFIED',
                    'SECOND_VERIFIED',
                    'FINALIZED'
                ])
            )
            .order_by(_rb.ReportVersion.version_no.desc())
            .first()
        )
    return _rb_latest_authoritative_version


def install_0920(_rb):
    def _rb_sip_secret_map():

        path=_rb.os.getenv(
            'RADBRIDGE_SIP_SECRET_FILE',
            '/run/secrets/radbridge-sip-agents.env'
        )

        result={}

        try:
            with open(path,encoding='utf-8') as f:

                for raw in f:

                    line=raw.strip()

                    if (
                        not line
                        or line.startswith('#')
                        or '=' not in line
                    ):
                        continue

                    key,value=line.split('=',1)

                    result[
                        key.strip()
                    ]=value.strip()

        except Exception:
            return {}

        return result
    return _rb_sip_secret_map


def install_0924(_rb):
    def _rb_public_reference():

        from datetime import datetime

        return (
            "WEB-"
            + datetime.utcnow().strftime("%Y%m%d")
            + "-"
            + _rb._rb_secrets.token_hex(4).upper()
        )
    return _rb_public_reference


def install_0925(_rb):
    def _rb_normalize_public_text(value, limit=1000):

        value = str(
            value or ""
        ).strip()

        return value[:limit]
    return _rb_normalize_public_text


def install_0926(_rb):
    def _rb_human_requested(text):

        q = str(
            text or ""
        ).strip().lower()

        words = (
            "موظف",
            "الاستقبال",
            "استقبال",
            "حد يرد",
            "شخص",
            "انسان",
            "إنسان",
            "human",
            "agent",
            "reception",
            "call center",
        )

        return any(
            word in q
            for word in words
        )
    return _rb_human_requested


def install_0927(_rb):
    def _rb_public_bot_answer(text):

        q = str(
            text or ""
        ).strip().lower()

        if any(
            x in q
            for x in (
                "موعد",
                "مواعيد",
                "الفرع",
                "الفرع",
                "ساعات العمل",
            )
        ):
            return (
                True,
                "أقدر أساعدك في مواعيد الفروع. "
                "اكتب اسم الفرع أو المنطقة، "
                "ولو تحب التحدث مع موظف اكتب: موظف."
            )

        if any(
            x in q
            for x in (
                "سعر",
                "الأسعار",
                "الاسعار",
                "تكلفة",
                "كام",
            )
        ):
            return (
                True,
                "اكتب اسم الفحص المطلوب، "
                "وسنراجع السعر المتاح. "
                "ويمكنك طلب موظف في أي وقت."
            )

        if any(
            x in q
            for x in (
                "تقرير",
                "النتيجة",
                "نتيجة",
            )
        ):
            return (
                True,
                "للاستفسار عن التقرير، "
                "يفضل كتابة رقم الموبايل المسجل "
                "أو رقم الحجز في النموذج."
            )

        if any(
            x in q
            for x in (
                "حجز",
                "احجز",
                "تعديل الحجز",
                "الغاء",
                "إلغاء",
            )
        ):
            return (
                True,
                "أقدر أساعدك في طلبات الحجز. "
                "املأ الاسم ورقم الموبايل، "
                "وسيظهر الطلب لموظف الاستقبال."
            )

        if any(
            x in q
            for x in (
                "تحضير",
                "صيام",
                "تجهيز",
                "استعداد",
            )
        ):
            return (
                True,
                "اكتب اسم الفحص المطلوب، "
                "وسنراجع تعليمات التحضير المناسبة."
            )

        return (
            False,
            "لم أتمكن من تحديد طلبك بدقة. "
            "يمكنك توضيح السؤال أو اختيار التحدث مع موظف."
        )
    return _rb_public_bot_answer


def install_0928(_rb):
    def _rb_staff_role_allowed():

        try:
            u = _rb.current_user()

            code = (
                u.role.code
                if u and u.role
                else ""
            )

            # Canonical production roles plus legacy aliases kept for backwards compatibility.
            return code in {
                "SUPER_ADMIN",
                "RECEPTION",
                "CALL_CENTER",
                "CASE_COORDINATOR",
                "ADMIN",
                "COORDINATOR",
            }

        except Exception:
            return False
    return _rb_staff_role_allowed


def install_0940(_rb):
    def _rb_public_attachment_root():

        root = _rb.os.environ.get(
            "ATTACHMENT_DIR",
            "/app/attachments"
        )

        root = _rb._rb_os.path.join(
            root,
            "public-contact"
        )

        _rb._rb_os.makedirs(
            root,
            exist_ok=True
        )

        return root
    return _rb_public_attachment_root


def install_0941(_rb):
    def _rb_safe_upload_extension(filename):

        _, ext = _rb._rb_os.path.splitext(
            str(filename or "")
        )

        return ext.lower()
    return _rb_safe_upload_extension
