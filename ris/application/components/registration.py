"""Runtime-bound application.components.registration; dependencies are supplied at composition.

Legacy behavior is preserved; new policies belong in the independent domain layer.
"""

def install_0021(_rb):
    def _order_revenue(o): return _rb._money(o.contract_price or o.gross_price or 0)
    return _order_revenue


def install_0032(_rb):
    def find_duplicate_patients(name='',dob='',phone='',national_id=''):
        found=[]
        if national_id:found += _rb.Patient.query.filter(_rb.Patient.national_id==national_id).limit(10).all()
        if phone and dob:found += _rb.Patient.query.filter(_rb.Patient.phone==phone,_rb.Patient.dob==dob).limit(10).all()
        return list({p.id:p for p in found}.values())
    return find_duplicate_patients


def install_0037(_rb):
    def suggest_order_for_study(tags):
        if tags['accession']:
            o=_rb.Order.query.filter_by(accession=tags['accession']).first()
            if o:return o,'ACCESSION_EXACT','HIGH'
        if tags['patient_id']:
            patient=_rb.Patient.query.filter_by(patient_id=tags['patient_id']).first()
            if patient:
                q=_rb.Order.query.filter_by(patient_id=patient.id)
                modality=tags['modality'].split('\\')[0].strip().upper()
                if modality:q=q.filter(_rb.Order.modality==modality)
                cand=q.order_by(_rb.Order.scheduled.desc()).limit(10).all()
                if len(cand)==1:return cand[0],'PATIENT_ID_UNIQUE','HIGH'
                if cand:return cand[0],'PATIENT_ID_SUGGESTED','MEDIUM'
        return None,'UNMATCHED','LOW'
    return suggest_order_for_study


def install_0066(_rb):
    def order_balance(order):
        due=_rb.effective_patient_due(order)
        paid=float(order.paid_amount or 0)
        return round(due-paid,2)
    return order_balance


def install_0067(_rb):
    def procedure_display_name(p):
        if not p: return ''
        return (p.name_ar or p.name) if _rb.lang()=='ar' else p.name
    return procedure_display_name


def install_0104(_rb):
    def patient_worklist_display_name(patient):
        return _rb.normalized_worklist_name(
            getattr(patient,'name',''),
            getattr(patient,'worklist_name',''),
        )
    return patient_worklist_display_name


def install_0114(_rb):
    def next_patient_id():
        prefix = "P"

        # Serialize every application path that allocates a P-number, including
        # manual registration, booking, PACS intake, and OCR intake.
        if _rb.db.engine.dialect.name=='postgresql':
            _rb.db.session.execute(_rb.text("SELECT pg_advisory_xact_lock(hashtext('PATIENT_ID_SEQUENCE'))"))

        rows = _rb.Patient.query.filter(
            _rb.Patient.patient_id.like(prefix + "%")
        ).all()

        max_no = 0

        for row in rows:
            pid = str(row.patient_id or "")

            if not pid.startswith(prefix):
                continue

            try:
                n = int(pid[len(prefix):])
                max_no = max(max_no, n)
            except Exception:
                continue

        return f"{prefix}{max_no + 1:08d}"
    return next_patient_id


def install_0115(_rb):
    def _rb_registration_v2_name_parts(form):
        return [
            (form.get('new_first_name') or '').strip(),
            (form.get('new_middle_name') or '').strip(),
            (form.get('new_third_name') or '').strip(),
            (form.get('new_fourth_name') or '').strip(),
        ]
    return _rb_registration_v2_name_parts


def install_0116(_rb):
    def _rb_registration_v2_patient_name(form):
        return ' '.join(x for x in _rb._rb_registration_v2_name_parts(form) if x).strip()
    return _rb_registration_v2_patient_name


def install_0117(_rb):
    def _rb_registration_v2_worklist_name(form):
        return _rb.normalized_worklist_name(_rb._rb_registration_v2_patient_name(form),
            form.get('new_worklist_name') or form.get('worklist_name') or '')
    return _rb_registration_v2_worklist_name


def install_0118(_rb):
    def _rb_registration_v2_dob(form):
        return _rb.resolve_patient_dob(form, prefix='new_').dob
    return _rb_registration_v2_dob


def install_0119(_rb):
    def _rb_registration_v2_create_patient(form,audit_action='PATIENT_CREATE_FROM_CALENDAR'):
        parts=_rb._rb_registration_v2_name_parts(form)
        if not parts[0]: raise ValueError('First name is required.')
        if not any(parts[1:]): raise ValueError('Enter at least one additional patient name.')
        name=_rb._rb_registration_v2_patient_name(form)
        dob_resolution=_rb.resolve_patient_dob(form, prefix='new_')
        dob=dob_resolution.dob
        phone=(form.get('new_phone') or '').strip()
        national=(form.get('new_national_id') or '').strip()
        from registration_policy import validate_patient_fields
        validate_patient_fields(dict(name=name,phone=phone,national_id=national,dob=dob,sex=form.get('new_sex',''),
            email=form.get('new_email',''),address=form.get('new_address',''),nationality=form.get('new_nationality','')))
        duplicates=_rb.find_duplicate_patients(name,dob,phone,national)
        if duplicates:
            d=duplicates[0]
            raise ValueError(f'Possible duplicate patient: {d.patient_id} — {d.name}. Use the existing patient or review the duplicate.')
        patient=_rb.Patient(
            patient_id='TMP'+_rb.secrets.token_hex(8),name=name,dob=dob,
            dob_estimated=dob_resolution.estimated,
            sex=(form.get('new_sex') or '').strip(),phone=phone,national_id=national,
            address=(form.get('new_address') or '').strip(),
            email=(form.get('new_email') or '').strip(),
            worklist_name=_rb._rb_registration_v2_worklist_name(form))
        _rb.db.session.add(patient);_rb.db.session.flush()
        _rb.db.session.add(_rb.PatientDemographicsExtra(patient_id=patient.id,nationality=(form.get('new_nationality') or '').strip()))
        try: patient.patient_id=_rb.generate_patient_id(patient)
        except Exception: patient.patient_id=_rb.next_patient_id()
        _rb.audit(audit_action,'patient',patient.id,f'{patient.patient_id} {patient.name}')
        return patient
    return _rb_registration_v2_create_patient


def install_0122(_rb):
    def generate_patient_id(patient):
        return f'P{patient.id:08d}'
    return generate_patient_id


def install_0234(_rb):
    def appointment_overlap(device_id,start_at,duration_min,exclude_id=None):
        if not device_id:return None
        duration=max(5,int(duration_min or 20))
        end_at=start_at+_rb.timedelta(minutes=duration)
        q=_rb.Appointment.query.filter(
            _rb.Appointment.device_id==device_id,
            _rb.Appointment.status.notin_(['CANCELLED','NO_SHOW']),
            _rb.Appointment.scheduled < end_at
        )
        if exclude_id:q=q.filter(_rb.Appointment.id!=exclude_id)
        for a in q.all():
            a_end=a.scheduled+_rb.timedelta(minutes=max(5,int(a.duration_min or (a.procedure.duration_min if a.procedure else 20) or 20)))
            if a_end>start_at:
                return a
        return None
    return appointment_overlap


def install_0236(_rb):
    def device_booking_reason(device, start_at=None, end_at=None):
        # Compatible with both:
        # device_booking_reason(device)
        # device_booking_reason(device, start_at, end_at)
        #
        # Current DeviceBlock schema has no "active" column.
        blocks = _rb.DeviceBlock.query.filter_by(device_id=device.id).all()

        if not blocks:
            return ''

        # General device-status check.
        # Used by schedule_v2 when no specific slot is supplied.
        if start_at is None or end_at is None:
            now = _rb.datetime.now()
            for block in blocks:
                if block.start_at <= now < block.end_at:
                    return block.reason or 'Device unavailable'
            return ''

        # Specific booking-slot check.
        for block in blocks:
            if block.start_at < end_at and block.end_at > start_at:
                return block.reason or 'Device unavailable'

        return ''
    return device_booking_reason


def install_0237(_rb):
    def device_available_for_booking(device,start_at,duration_min,exclude_appointment_id=None):
        duration=max(5,int(duration_min or 20));end_at=start_at+_rb.timedelta(minutes=duration)
        if not device:return False,'Device is required',None
        if not bool(getattr(device,'active',True)):return False,'Device is inactive',None
        if not bool(getattr(device,'booking_enabled',True)):return False,'Booking is disabled for this device',None
        operational=(getattr(device,'operational_status','ACTIVE') or 'ACTIVE').upper()
        if operational!='ACTIVE':return False,_rb.DEVICE_BOOKING_STATUSES.get(operational,operational.replace('_',' ').title()),None
        start_min=start_at.hour*60+start_at.minute;end_min=end_at.hour*60+end_at.minute
        ws=_rb._hhmm_to_minutes(getattr(device,'workday_start','08:00'),'08:00');we=_rb._hhmm_to_minutes(getattr(device,'workday_end','22:00'),'22:00')
        if start_min<ws or end_min>we:return False,f'Outside device working hours {device.workday_start or "08:00"}-{device.workday_end or "22:00"}',None
        reason=_rb.device_booking_reason(device,start_at,end_at)
        if reason:return False,reason,None
        conflict=_rb.appointment_overlap(device.id,start_at,duration,exclude_id=exclude_appointment_id)
        if conflict:
            ce=conflict.scheduled+_rb.timedelta(minutes=max(5,int(conflict.duration_min or 20)))
            return False,f'Already booked for {conflict.patient.name} until {ce.strftime("%H:%M")}',conflict
        return True,'',None
    return device_available_for_booking


def install_0238(_rb):
    def booking_v2_slots(selected,device,slot_minutes=15):
        start_min=_rb._hhmm_to_minutes(getattr(device,'workday_start','08:00'),'08:00')
        end_min=_rb._hhmm_to_minutes(getattr(device,'workday_end','22:00'),'22:00')
        slots=[]
        for minute in range(start_min,end_min,slot_minutes):
            dt=_rb.datetime.combine(selected,_rb.datetime.min.time())+_rb.timedelta(minutes=minute)
            slots.append(dt)
        return slots
    return booking_v2_slots


def install_0239(_rb):
    def booking_v2_slot_state(device,slot,duration_min=15):
        ok,reason,conflict=_rb.device_available_for_booking(device,slot,duration_min)
        if ok:
            return {'available':True,'reason':'','conflict':None}
        return {'available':False,'reason':reason,'conflict':conflict}
    return booking_v2_slot_state


def install_0240(_rb):
    def procedure_available_in_branch(procedure_id,branch_id):
        row=_rb.ProcedureBranch.query.filter_by(procedure_id=procedure_id,branch_id=branch_id).first()
        if row is None:
            return True
        return bool(row.active)
    return procedure_available_in_branch


def install_0241(_rb):
    def allowed_procedures_for_branch(branch_id,modality=''):
        q=_rb.Procedure.query.filter_by(active=True)
        if modality:
            q=q.filter(_rb.Procedure.modality==modality)
        rows=q.order_by(_rb.Procedure.modality,_rb.Procedure.name).all()
        return [p for p in rows if _rb.procedure_available_in_branch(p.id,branch_id)]
    return allowed_procedures_for_branch


def install_0242(_rb):
    def booking_restriction_reason(branch,procedure,device,start_at,duration_min,exclude_appointment_id=None):
        if not branch or not branch.active:
            return 'Branch is inactive'
        if not procedure or not procedure.active:
            return 'Procedure is inactive'
        if not _rb.procedure_available_in_branch(procedure.id,branch.id):
            return 'This examination is not available in the selected branch'
        if not device:
            return 'Device is required'
        if device.branch_id!=branch.id:
            return 'Selected device belongs to another branch'
        if (device.modality or '').upper()!=(procedure.modality or '').upper():
            return 'Selected device is not compatible with this examination'

        duration=max(5,int(duration_min or procedure.duration_min or 20))
        control_reason=_rb.booking_control_reason(branch,procedure,device,start_at,start_at+_rb.timedelta(minutes=duration))
        if control_reason:
            return f'Booking blocked: {control_reason}'
        ok,reason,conflict=_rb.device_available_for_booking(
            device,start_at,duration,exclude_appointment_id=exclude_appointment_id
        )
        if not ok:
            return reason or 'Device is unavailable'
        return ''
    return booking_restriction_reason


def install_0243(_rb):
    def ensure_default_procedure_branch_mappings():
        added=0
        branches=_rb.Branch.query.filter_by(active=True).all()
        procedures=_rb.Procedure.query.filter_by(active=True).all()
        for b in branches:
            for p in procedures:
                if not _rb.ProcedureBranch.query.filter_by(branch_id=b.id,procedure_id=p.id).first():
                    _rb.db.session.add(_rb.ProcedureBranch(branch_id=b.id,procedure_id=p.id,active=True))
                    added+=1
        if added:
            _rb.db.session.commit()
        return added
    return ensure_default_procedure_branch_mappings


def install_0250(_rb):
    def booking_control_reason(branch,procedure,device,start_at,end_at):
        rows=_rb.BookingBlock.query.filter_by(active=True).filter(
            _rb.BookingBlock.start_at < end_at,
            _rb.BookingBlock.end_at > start_at
        ).all()
        for b in rows:
            # Staff availability belongs to assignment/worklist scheduling.
            # It must never block creation of the patient's appointment.
            if (b.block_type or '').upper() in ('DOCTOR','TECHNICIAN'):
                continue
            if b.branch_id and b.branch_id!=branch.id:continue
            if b.device_id and b.device_id!=device.id:continue
            if b.procedure_id and b.procedure_id!=procedure.id:continue
            return b.reason_text or b.reason_code
        return ''
    return booking_control_reason


def install_0251(_rb):
    def validate_booking_block_scope(
        *,block_type,branch_id=None,device_id=None,procedure_id=None,
        user_id=None,start_at=None,end_at=None
    ):
        block_type=str(block_type or 'OTHER').strip().upper()
        allowed={'DEVICE','PROCEDURE','BRANCH','DOCTOR','TECHNICIAN','OTHER'}
        if block_type not in allowed:
            return 'Invalid booking block type.'
        if not start_at or not end_at:
            return 'Start and end date/time are required.'
        if end_at<=start_at:
            return 'End date/time must be after start date/time.'
        required={
            'DEVICE':(device_id,'Select a device for a device block.'),
            'PROCEDURE':(procedure_id,'Select a procedure for a procedure block.'),
            'BRANCH':(branch_id,'Select a branch for a branch block.'),
            'DOCTOR':(user_id,'Select a doctor for a doctor availability block.'),
            'TECHNICIAN':(user_id,'Select a technician for a technician availability block.'),
        }
        value_and_message=required.get(block_type)
        if value_and_message and not value_and_message[0]:
            return value_and_message[1]
        if block_type=='OTHER' and not any(
            (branch_id,device_id,procedure_id,user_id)
        ):
            return 'Select at least one scope for an Other block.'
        return ''
    return validate_booking_block_scope


def install_0252(_rb):
    def acquire_booking_slot_lock(device_id,start_at):
        """Serialize booking checks for one device/day on PostgreSQL.

    The lock lives only for the current transaction. The second concurrent
    request waits, then repeats the overlap check after the first commits.
    SQLite test runs intentionally use a no-op because they are single-process
    contract tests and do not support PostgreSQL advisory locks.
    """
        if not device_id or not start_at:
            return
        bind=_rb.db.session.get_bind()
        if bind.dialect.name!='postgresql':
            return
        lock_name=f'radbridge-booking:{int(device_id)}:{start_at:%Y-%m-%d}'
        _rb.db.session.execute(
            _rb.text('SELECT pg_advisory_xact_lock(hashtextextended(:name,0))'),
            {'name':lock_name},
        )
    return acquire_booking_slot_lock


def install_0264(_rb):
    def smart_booking_cards(day,branch_id=None):
        q=_rb.Device.query.filter_by(active=True)
        if branch_id:q=q.filter_by(branch_id=branch_id)
        start=_rb.datetime.combine(day,_rb.datetime.min.time());end=start+_rb.timedelta(days=1);out=[]
        for d in q.order_by(_rb.Device.modality,_rb.Device.name).all():
            appts=_rb.Appointment.query.filter(_rb.Appointment.device_id==d.id,_rb.Appointment.scheduled>=start,_rb.Appointment.scheduled<end).order_by(_rb.Appointment.scheduled).all()
            blocks=_rb.BookingBlock.query.filter(_rb.BookingBlock.active.is_(True),_rb.BookingBlock.start_at<end,_rb.BookingBlock.end_at>start).filter(_rb.or_(_rb.BookingBlock.device_id==d.id,_rb.and_(_rb.BookingBlock.device_id.is_(None),_rb.BookingBlock.branch_id==d.branch_id))).order_by(_rb.BookingBlock.start_at).all()
            out.append({'device':d,'appointments':appts,'blocks':blocks})
        return out
    return smart_booking_cards


def install_0266(_rb):
    def patient_by_phone(number):
        n=_rb.normalize_phone(number)
        if not n: return None
        for p in _rb.Patient.query.filter(_rb.Patient.phone.isnot(None)).all():
            if _rb.normalize_phone(p.phone)==n:
                return p
        return None
    return patient_by_phone


def install_0273(_rb):
    def _collect_patient_file_paths():
        paths=[]
        try:
            for a in _rb.Attachment.query.all():
                for attr in ('stored_path','path','file_path'):
                    p=getattr(a,attr,None)
                    if p and _rb.os.path.isfile(p): paths.append(('attachment',p))
        except Exception:
            pass
        try:
            for r in _rb.Report.query.all():
                for attr in ('docx_path','pdf_path','source_path','file_path'):
                    p=getattr(r,attr,None)
                    if p and _rb.os.path.isfile(p): paths.append(('report',p))
        except Exception:
            pass
        # stable unique order
        seen=set();out=[]
        for kind,p in paths:
            ap=_rb.os.path.abspath(p)
            if ap not in seen:
                seen.add(ap);out.append((kind,ap))
        return out
    return _collect_patient_file_paths


def install_0274(_rb):
    def create_all_patient_backup():
        stamp=_rb.datetime.utcnow().strftime('%Y%m%d-%H%M%S')
        path=_rb.os.path.join(_rb.admin_backup_dir(),f'all-patients-{stamp}.zip')
        patient_fields=['id','patient_id','name','dob','sex','phone','national_id','address','email','created_at']
        order_fields=['id','accession','patient_id','modality','procedure','scheduled','status','branch_id','contract_id','gross_price','contract_price','patient_share','company_share','paid_amount','created_at']
        with _rb.zipfile.ZipFile(path,'w',_rb.zipfile.ZIP_DEFLATED,allowZip64=True) as z:
            out=_rb.io.StringIO();w=_rb.csv.writer(out);w.writerow(patient_fields)
            for p in _rb.Patient.query.order_by(_rb.Patient.id).yield_per(500):
                w.writerow([getattr(p,f,None) for f in patient_fields])
            z.writestr('patients.csv',out.getvalue())

            out=_rb.io.StringIO();w=_rb.csv.writer(out);w.writerow(order_fields)
            for o in _rb.Order.query.order_by(_rb.Order.id).yield_per(500):
                w.writerow([getattr(o,f,None) for f in order_fields])
            z.writestr('orders.csv',out.getvalue())

            manifest={
                'created_at':_rb.datetime.utcnow().isoformat()+'Z',
                'patients':_rb.Patient.query.count(),
                'orders':_rb.Order.query.count(),
                'attachments':_rb.Attachment.query.count() if 'Attachment' in _rb.namespace() else 0,
                'reports':_rb.Report.query.count() if 'Report' in _rb.namespace() else 0,
                'version':_rb.APP_VERSION
            }
            z.writestr('manifest.json',_rb.json.dumps(manifest,ensure_ascii=False,indent=2))

            for kind,p in _rb._collect_patient_file_paths():
                try:
                    z.write(p,f'{kind}s/{_rb.safe_export_name(_rb.os.path.basename(p))}')
                except Exception:
                    pass

        digest=_rb.hashlib.sha256()
        with open(path,'rb') as f:
            for chunk in iter(lambda:f.read(1024*1024),b''):
                digest.update(chunk)
        with open(path+'.sha256','w',encoding='utf-8') as f:
            f.write(digest.hexdigest()+'  '+_rb.os.path.basename(path)+'\n')
        return path,digest.hexdigest()
    return create_all_patient_backup


def install_0275(_rb):
    def quarantine_patient_files():
        stamp=_rb.datetime.utcnow().strftime('%Y%m%d-%H%M%S')
        root=_rb.os.path.join(_rb.os.getenv('RIS_QUARANTINE_DIR') or '/app/quarantine',f'patient-reset-{stamp}')
        _rb.os.makedirs(root,exist_ok=True)
        moved=0
        for kind,p in _rb._collect_patient_file_paths():
            try:
                rel=_rb.safe_export_name(_rb.os.path.basename(p))
                target=_rb.os.path.join(root,kind+'s',rel)
                _rb.os.makedirs(_rb.os.path.dirname(target),exist_ok=True)
                # avoid collision
                if _rb.os.path.exists(target):
                    stem,ext=_rb.os.path.splitext(target);target=stem+'-'+_rb.hashlib.sha1(p.encode()).hexdigest()[:8]+ext
                _rb.shutil.move(p,target);moved+=1
            except Exception:
                pass
        return root,moved
    return quarantine_patient_files


def install_0276(_rb):
    def operational_patient_table_order():
        # Discover tables that depend (directly or transitively) on patient/order/appointment.
        meta=_rb.db.metadata
        roots={'patient','order','appointment'}
        deps={}
        for name,table in meta.tables.items():
            parents=set()
            for fk in table.foreign_keys:
                parents.add(fk.column.table.name)
            deps[name]=parents

        affected=set(roots)
        changed=True
        while changed:
            changed=False
            for child,parents in deps.items():
                if child=='audit_log':
                    continue
                if child not in affected and parents & affected:
                    affected.add(child);changed=True

        # Explicitly never delete configuration/security/audit master data.
        protected={'audit_log','user','role','permission','branch','procedure','device','contract',
                   'referring_doctor','warehouse','inventory_item','warehouse_stock_policy',
                   'procedure_consumable_default','studio_shortcut','printer_profile','registration_default'}
        affected-=protected

        depth={}
        def calc(name,stack=None):
            if name in depth:return depth[name]
            stack=stack or set()
            if name in stack:return 0
            stack=stack|{name}
            ps=[p for p in deps.get(name,set()) if p in affected]
            depth[name]=0 if not ps else max(calc(p,stack)+1 for p in ps)
            return depth[name]
        for name in affected:calc(name)
        return sorted(affected,key=lambda n:depth.get(n,0),reverse=True)
    return operational_patient_table_order


def install_0277(_rb):
    def delete_all_patient_operational_data():
        tables=_rb.operational_patient_table_order()
        counts={}
        # Files are quarantined first, never permanently purged by this operation.
        quarantine,moved=_rb.quarantine_patient_files()
        for name in tables:
            table=_rb.db.metadata.tables.get(name)
            if table is None:continue
            try:
                result=_rb.db.session.execute(table.delete())
                counts[name]=getattr(result,'rowcount',None)
            except Exception:
                _rb.db.session.rollback()
                raise
        _rb.db.session.commit()
        return {'tables':tables,'counts':counts,'quarantine':quarantine,'files_moved':moved}
    return delete_all_patient_operational_data


def install_0281(_rb):
    def patient_export_manifest(patient):
        orders=_rb.Order.query.filter_by(patient_id=patient.id).order_by(_rb.Order.id).all()
        return {
            'generated_at':_rb.datetime.utcnow().isoformat()+'Z',
            'patient':{
                'id':patient.id,'patient_id':getattr(patient,'patient_id',None),'name':getattr(patient,'name',None),
                'phone':getattr(patient,'phone',None)
            },
            'orders':[{
                'id':o.id,'accession':o.accession,'procedure':o.procedure,'status':o.status,
                'created_at':o.created_at.isoformat() if getattr(o,'created_at',None) else None
            } for o in orders]
        }
    return patient_export_manifest


def install_0299(_rb):
    def base_patient_due(order):
        return float(order.patient_share or order.contract_price or order.gross_price or 0)
    return base_patient_due


def install_0300(_rb):
    def effective_patient_due(order):
        return round(max(0.0,_rb.base_patient_due(order)-_rb.total_order_discount(order)),2)
    return effective_patient_due


def install_0315(_rb):
    def registration_defaults_for(user=None):
        user=user or _rb.current_user()
        row=None
        if user:
            row=_rb.RegistrationDefault.query.filter_by(user_id=user.id,active=True).order_by(_rb.RegistrationDefault.id.desc()).first()
        if not row:
            row=_rb.RegistrationDefault.query.filter_by(is_global=True,active=True).order_by(_rb.RegistrationDefault.id.desc()).first()
        return row
    return registration_defaults_for


def install_0316(_rb):
    def registration_form_context(form_data=None,selected_patient=None,duplicate_patients=None):
        selected_patient_obj = _rb.Patient.query.get(selected_patient) if selected_patient else None
        form_data=dict(form_data or {})

        # RB_SELECTED_PATIENT_FORM_PREFILL_V1
        # Existing form values always win. Patient data only fills missing fields.
        if selected_patient_obj:
            patient_prefill = {
                'patient': str(selected_patient_obj.id),
                'name': str(selected_patient_obj.name or ''),
                'national_id': str(selected_patient_obj.national_id or ''),
                'phone': str(selected_patient_obj.phone or ''),
                'dob': str(selected_patient_obj.dob or ''),
                'sex': str(selected_patient_obj.sex or ''),
                'address': str(selected_patient_obj.address or ''),
                'patient_mode': 'existing',
            }

            for key,value in patient_prefill.items():
                if key not in form_data or str(form_data.get(key) or '').strip()=='':
                    form_data[key]=value

        defaults=_rb.registration_defaults_for()
        return dict(
            patients=_rb.Patient.query.order_by(_rb.Patient.name).all(),
            branches=_rb.Branch.query.filter_by(active=True).order_by(_rb.Branch.name).all(),
            procedures=_rb.Procedure.query.filter_by(active=True).order_by(_rb.Procedure.modality,_rb.Procedure.name).all(),
            contracts=_rb.Contract.query.filter_by(active=True).order_by(_rb.Contract.name).all(),
            referrers=_rb.ReferringDoctor.query.filter_by(active=True).order_by(_rb.ReferringDoctor.name).all(),
            selected_patient=selected_patient,
            selected_patient_obj=selected_patient_obj,
            duplicate_patients=duplicate_patients or [],
            form_data=form_data,
            field_rules=_rb.registration_rule_map(),
            registration_style=_rb.registration_style_for(),
            registration_defaults=defaults
        )
    return registration_form_context


def install_0319(_rb):
    def registration_style_for(user=None):
        user=user or _rb.current_user()
        if not user:
            return 'MODERN'
        p=_rb.UserRegistrationPreference.query.filter_by(user_id=user.id).first()
        return (p.style_key if p and p.style_key in ('MODERN','CLASSIC','COMPACT') else 'MODERN')
    return registration_style_for


def install_0320(_rb):
    def registration_template_for(user=None):
        style=_rb.registration_style_for(user)
        return {
          'MODERN':'order_form.html',
          'CLASSIC':'order_form_classic.html',
          'COMPACT':'order_form_compact.html'
        }.get(style,'order_form.html')
    return registration_template_for


def install_0321(_rb):
    def registration_rule_map():
        return {x.field_key:x for x in _rb.FieldRule.query.all()}
    return registration_rule_map


def install_0322(_rb):
    def validate_registration_value(rule,value):
        if not rule:
            return True,''
        v=str(value or '').strip()
        label=rule.label_ar if _rb.current_ui_language()=='ar' else rule.label_en
        if rule.required and not v:
            return False,f'{label}: required'
        if not v:
            return True,''
        if rule.exact_length and len(v)!=int(rule.exact_length):
            return False,f'{label}: must be exactly {rule.exact_length} characters'
        if rule.min_length is not None and len(v)<int(rule.min_length):
            return False,f'{label}: minimum length is {rule.min_length}'
        if rule.max_length is not None and len(v)>int(rule.max_length):
            return False,f'{label}: maximum length is {rule.max_length}'
        if rule.data_type=='NUMBERS' and not v.isdigit():
            return False,f'{label}: numbers only'
        if rule.data_type=='LETTERS':
            check=v.replace(' ','')
            if not check.isalpha():
                return False,f'{label}: letters only'
        if rule.data_type=='ALPHANUM':
            check=v.replace(' ','')
            if not check.isalnum():
                return False,f'{label}: letters and numbers only'
        if rule.regex_pattern:
            try:
                if not _rb.re.fullmatch(rule.regex_pattern,v):
                    return False,f'{label}: invalid format'
            except _rb.re.error:
                pass
        return True,''
    return validate_registration_value


def install_0323(_rb):
    def patient_extra(patient):
        return _rb.PatientDemographicsExtra.query.filter_by(patient_id=patient.id).first()
    return patient_extra


def install_0342(_rb):
    def patient_default_recipient(patient,channel):
        if channel=='EMAIL':
            return getattr(patient,'email','') or ''
        return patient.phone or ''
    return patient_default_recipient


def install_0370(_rb):
    def _order_history_present(order):
        try:
            return _rb.ClinicalNote.query.filter_by(order_id=order.id).count()>0
        except Exception:
            return False
    return _order_history_present


def install_0371(_rb):
    def _order_attachment_count(order):
        try:
            return _rb.PatientDocument.query.filter_by(patient_id=order.patient_id).count()
        except Exception:
            return 0
    return _order_attachment_count


def install_0384(_rb):
    def order_action_context(order):
        receipt=_rb.Receipt.query.filter_by(order_id=order.id).order_by(_rb.Receipt.id.desc()).first()
        report=_rb.Report.query.filter_by(order_id=order.id).order_by(_rb.Report.id.desc()).first()
        return {'receipt':receipt,'report':report}
    return order_action_context


def install_0388(_rb):
    def order_visual_state(order):
        report=_rb.Report.query.filter_by(order_id=order.id).order_by(_rb.Report.id.desc()).first()
        readiness=__import__('reception_readiness').view(order,_rb.CaseReadiness.query.filter_by(order_id=order.id).first())
        assignment=_rb.CaseAssignment.query.filter_by(order_id=order.id,active=True).first()
        attachments=_rb.Attachment.query.filter_by(order_id=order.id).count()

        if getattr(order,'report_delivered',False):
            stage='DELIVERED'
        elif report and report.status=='FINAL':
            stage='FINAL'
        elif report and report.status in ('DRAFT','PRELIMINARY'):
            stage='REPORTING'
        elif assignment:
            stage='ASSIGNED'
        elif readiness and readiness.status=='READY':
            stage='READY_REPORT'
        elif getattr(order,'pacs_status','') in ('PARTIAL','WAITING') and getattr(order,'exam_status','') in ('COMPLETED','DONE'):
            stage='IMAGES_PENDING'
        elif getattr(order,'exam_status','') in ('IN_PROGRESS','STARTED'):
            stage='IN_EXAM'
        else:
            stage='REGISTERED'

        flags=[]
        if getattr(order,'priority','ROUTINE') in ('URGENT','STAT'):
            flags.append(('urgent','URGENT'))
        if readiness:
            missing=[]
            for field,label in [
                ('missing_history','Missing History'),
                ('missing_documents','Missing Documents'),
                ('images_incomplete','Images Incomplete'),
            ]:
                if getattr(readiness,field,False): missing.append(label)
            # Compatible with older readiness schema: use reason/details text if boolean columns do not exist.
            txt=' '.join(str(getattr(readiness,x,'') or '') for x in ('reason','details','notes','blocking_reasons'))
            low=txt.lower()
            if 'history' in low and 'Missing History' not in missing: missing.append('Missing History')
            if ('document' in low or 'attachment' in low) and 'Missing Documents' not in missing: missing.append('Missing Documents')
            if ('image' in low and ('incomplete' in low or 'missing' in low)) and 'Images Incomplete' not in missing: missing.append('Images Incomplete')
            flags.extend(('warning',x) for x in missing)
        if attachments==0:
            flags.append(('info','No Attachments'))
        return {'stage':stage,'flags':flags,'readiness':readiness,'assignment':assignment,'report':report,'attachments':attachments}
    return order_visual_state


def install_0391(_rb):
    def smart_intake_dir(intake_id):
        p=_rb.os.path.join(_rb.ATTACHMENT_DIR,'smart-intake',str(intake_id))
        _rb.os.makedirs(p,exist_ok=True)
        return p
    return smart_intake_dir


def install_0393(_rb):
    def _suggest_procedure_from_text(text):
        txt=_rb.re.sub(r'\s+',' ',str(text or '').lower()).strip()
        procs=_rb.Procedure.query.filter_by(active=True).all()
        ranked=[]
        for p in procs:
            names=[_rb.re.sub(r'\s+',' ',str(value or '').lower()).strip()
              for value in (p.name,p.name_ar) if str(value or '').strip()]
            code=str(p.code or '').lower().strip()
            body=_rb.re.sub(r'\s+',' ',str(p.body_part or '').lower()).strip()
            mod=str(p.modality or '').lower().strip()
            score=0
            phrase_hits=[name for name in names if len(name)>=4 and name in txt]
            if phrase_hits: score=max(score,100+min(len(max(phrase_hits,key=len)),30))
            if code and _rb.re.search(r'(?<!\w)'+_rb.re.escape(code)+r'(?!\w)',txt): score=max(score,95)
            meaningful={token for name in names for token in _rb.re.split(r'\W+',name)
              if len(token)>=4 and token not in {'scan','contrast','without','with'} and token!=mod}
            token_hits=sum(1 for token in meaningful if token in txt)
            modality_hit=bool(mod and _rb.re.search(r'(?<!\w)'+_rb.re.escape(mod)+r'(?!\w)',txt))
            body_hit=bool(body and len(body)>=3 and body in txt)
            if modality_hit and body_hit: score=max(score,75)
            if token_hits>=2: score=max(score,70+min(token_hits,5)*5)
            if score>=70: ranked.append((score,p))
        ranked.sort(key=lambda item:(-item[0],item[1].id))
        if not ranked: return None
        if len(ranked)>1 and ranked[1][0]>=ranked[0][0]-5: return None
        return ranked[0][1]
    return _suggest_procedure_from_text


def install_0394(_rb):
    def _suggest_contract_from_text(text):
        txt=_rb.re.sub(r'\s+',' ',str(text or '').lower()).strip()
        ranked=[]
        for c in _rb.Contract.query.filter_by(active=True).all():
            name=_rb.re.sub(r'\s+',' ',str(c.name or '').lower()).strip()
            code=str(c.code or '').lower().strip()
            score=0
            if name and len(name)>=3 and name in txt: score=100+min(len(name),30)
            if code and len(code)>=3 and _rb.re.search(r'(?<!\w)'+_rb.re.escape(code)+r'(?!\w)',txt): score=max(score,95)
            if score: ranked.append((score,c))
        ranked.sort(key=lambda item:(-item[0],item[1].id))
        if not ranked: return None
        if len(ranked)>1 and ranked[1][0]>=ranked[0][0]-3: return None
        return ranked[0][1]
    return _suggest_contract_from_text


def install_0395(_rb):
    def _intake_source_field(fields,field_key):
        aliases={
          'name':('name','patient_name','full_name'),
          'national_id':('national_id','national_id_number','id_number'),
          'phone':('phone','mobile','mobile_number'),
          'dob':('dob','date_of_birth','birth_date'),
          'sex':('sex','gender'),
          'address':('address','patient_address'),
        }
        return next((fields.get(key) for key in aliases.get(field_key,(field_key,))
          if fields.get(key) not in (None,'')),None)
    return _intake_source_field


def install_0396(_rb):
    def _intake_normalized_field(field_key,value):
        return _rb.normalize_intake_identity({field_key:value}).get(field_key,'')
    return _intake_normalized_field


def install_0399(_rb):
    def _intake_file_sha256(path):
        h=_rb.hashlib.sha256()
        with open(path,'rb') as handle:
            for chunk in iter(lambda:handle.read(1024*1024),b''):
                h.update(chunk)
        return h.hexdigest()
    return _intake_file_sha256


def install_0400(_rb):
    def _intake_final_identity(intake,summary=None):
        if summary is None:
            try: summary=_rb.json.loads(intake.extracted_json or '{}')
            except Exception: summary={}
        identity=dict(summary.get('identity') or {})
        rows=_rb.SmartIntakeFieldReview.query.filter_by(intake_id=intake.id).all()
        for row in rows:
            value=row.final_value if row.review_status in ('ACCEPTED','CORRECTED') else row.normalized_value
            if value: identity[row.field_key]=value
        return _rb.normalize_intake_identity(identity)
    return _intake_final_identity


def install_0401(_rb):
    def _intake_candidate_patients(identity):
        clean=_rb.normalize_intake_identity(identity)
        clauses=[]
        if clean.get('national_id'):
            if _rb.db.engine.dialect.name=='postgresql':
                clauses.append(_rb.func.regexp_replace(_rb.Patient.national_id,'[^0-9]','','g')==clean['national_id'])
            else:
                clauses.append(_rb.Patient.national_id==clean['national_id'])
        if clean.get('phone'):
            phone=clean['phone']
            variants={phone,'+20'+phone[1:] if phone.startswith('0') else phone,
              '20'+phone[1:] if phone.startswith('0') else phone,
              '0020'+phone[1:] if phone.startswith('0') else phone}
            if _rb.db.engine.dialect.name=='postgresql':
                clauses.append(_rb.func.regexp_replace(_rb.Patient.phone,'[^0-9]','','g').in_([_rb.intake_digits(x) for x in variants]))
            else:
                clauses.append(_rb.Patient.phone.in_(list(variants)))
        if clean.get('name'):
            clauses.append(_rb.Patient.name.ilike(clean['name']))
            first=clean['name'].split(' ')[0]
            if len(first)>=3: clauses.append(_rb.Patient.name.ilike(f'%{first}%'))
        if not clauses: return []
        return _rb.Patient.query.filter(_rb.or_(*clauses)).order_by(_rb.Patient.id.desc()).limit(100).all()
    return _intake_candidate_patients


def install_0402(_rb):
    def _intake_match_context(identity):
        patients=_rb._intake_candidate_patients(identity)
        return _rb.score_intake_patient_candidates(identity,patients)
    return _intake_match_context


def install_0403(_rb):
    def _sync_intake_field_reviews(intake,summary,approved_source_docs):
        identity=_rb.normalize_intake_identity(summary.get('identity') or {})
        validation=_rb.validate_intake_identity(identity)
        for field_key in _rb.OCR_INTAKE_CORE_FIELDS:
            source_doc=None;raw_value='';confidence=0
            for doc,fields in approved_source_docs:
                found=_rb._intake_source_field(fields,field_key)
                if found not in (None,''):
                    source_doc=doc;raw_value=str(found);confidence=float(doc.confidence or 0);break
            row=_rb.SmartIntakeFieldReview.query.filter_by(intake_id=intake.id,field_key=field_key).first()
            if not row:
                row=_rb.SmartIntakeFieldReview(intake_id=intake.id,field_key=field_key)
                _rb.db.session.add(row)
            row.source_document_id=source_doc.id if source_doc else None
            row.source_type=source_doc.document_type if source_doc else ''
            row.extracted_value=raw_value
            row.normalized_value=identity.get(field_key,'')
            if row.review_status not in ('ACCEPTED','CORRECTED'):
                row.final_value=identity.get(field_key,'')
                row.review_status='PENDING'
            field_validation=validation['fields'].get(field_key,{})
            row.validation_status=(field_validation.get('status') or 'warning').upper()
            row.validation_message=(field_validation.get('message') or '')[:500]
            row.confidence=confidence
        return validation
    return _sync_intake_field_reviews


def install_0404(_rb):
    def rebuild_intake_summary(intake,commit=True):
        docs=_rb.SmartIntakeDocument.query.filter_by(intake_id=intake.id).order_by(_rb.SmartIntakeDocument.id).all()
        try: previous=_rb.json.loads(intake.extracted_json or '{}')
        except Exception: previous={}
        if not isinstance(previous,dict): previous={}
        visit_review=previous.get('visit_review') if isinstance(previous.get('visit_review'),dict) else {}
        summary={'identity':{},'identity_sources':{},'identity_conflicts':{},
          'insurance':{},'prescription':{},'approval':{},'documents':[],
          'visit_review':visit_review}
        approved_sources=[];prescription_text=[];insurance_text=[]
        for doc in docs:
            try: fields=_rb.json.loads(doc.extracted_json or '{}')
            except Exception: fields={}
            if not isinstance(fields,dict): fields={}
            summary['documents'].append({
              'id':doc.id,'type':doc.document_type,'status':doc.status,
              'confidence':float(doc.confidence or 0),'included':doc.status=='APPROVED'})
            if doc.status!='APPROVED':
                continue
            if doc.document_type in _rb.INTAKE_IDENTITY_SOURCE_PRIORITY:
                approved_sources.append((doc,fields))
            searchable=(doc.ocr_text or '')+'\n'+_rb.json.dumps(fields,ensure_ascii=False)
            if doc.document_type=='INSURANCE_CARD':
                summary['insurance'].update(fields);insurance_text.append(searchable)
            elif doc.document_type=='PRESCRIPTION':
                summary['prescription'].update(fields);prescription_text.append(searchable)
            elif doc.document_type=='APPROVAL':
                summary['approval'].update(fields);insurance_text.append(searchable)

        approved_sources.sort(key=lambda item:(
          -_rb.INTAKE_IDENTITY_SOURCE_PRIORITY.get(item[0].document_type,0),item[0].id))
        for field_key in _rb.OCR_INTAKE_CORE_FIELDS:
            candidates=[]
            for doc,fields in approved_sources:
                raw=_rb._intake_source_field(fields,field_key)
                if raw in (None,''): continue
                normalized=_rb._intake_normalized_field(field_key,raw)
                if not normalized: continue
                candidates.append({'document_id':doc.id,'document_type':doc.document_type,
                  'document_name':doc.original_name,'value':str(raw),'normalized':normalized,
                  'confidence':float(doc.confidence or 0)})
            if not candidates: continue
            selected=candidates[0]
            summary['identity'][field_key]=selected['value']
            summary['identity_sources'][field_key]=selected
            distinct={item['normalized'] for item in candidates}
            if len(distinct)>1:
                summary['identity_conflicts'][field_key]=candidates

        auto_proc=_rb._suggest_procedure_from_text('\n'.join(prescription_text))
        auto_contract=_rb._suggest_contract_from_text('\n'.join(insurance_text))
        if visit_review.get('reviewed'):
            intake.suggested_procedure_id=(int(visit_review.get('procedure_id')) if str(visit_review.get('procedure_id') or '').isdigit() else None)
            intake.suggested_contract_id=(int(visit_review.get('contract_id')) if str(visit_review.get('contract_id') or '').isdigit() else None)
        else:
            intake.suggested_procedure_id=auto_proc.id if auto_proc else None
            intake.suggested_contract_id=auto_contract.id if auto_contract else None
            summary['visit_review'].update({
              'procedure_id':intake.suggested_procedure_id,
              'contract_id':intake.suggested_contract_id,
              'procedure_source':'PRESCRIPTION' if auto_proc else '',
              'contract_source':'INSURANCE_CARD_OR_APPROVAL' if auto_contract else '',
              'reviewed':False,
            })
        intake.extracted_json=_rb.json.dumps(summary,ensure_ascii=False)
        _rb._sync_intake_field_reviews(intake,summary,approved_sources)
        identity=_rb._intake_final_identity(intake,summary)
        validation=_rb.validate_intake_identity(identity)
        for field_key,item in validation.get('fields',{}).items():
            row=_rb.SmartIntakeFieldReview.query.filter_by(intake_id=intake.id,field_key=field_key).first()
            if row:
                row.validation_status=(item.get('status') or 'warning').upper()
                row.validation_message=(item.get('message') or '')[:500]
        match=_rb._intake_match_context(identity)
        top=match.get('top')
        intake.match_resolution=match.get('resolution') or 'NO_MATCH'
        intake.matched_patient_score=float(top.get('score') if top else 0)
        intake.matched_patient_id=(top.get('patient_id') if top and match['resolution']=='EXACT_MATCH' and not top.get('hard_conflict') else None)

        if match['resolution'] in ('CONFLICT','AMBIGUOUS'):
            intake.status='MATCH_REVIEW'
        elif validation.get('ok'):
            intake.status='READY_TO_COMMIT'
        elif docs:
            intake.status='IDENTITY_REVIEW'
        else:
            intake.status='DRAFT'
        if commit: _rb.db.session.commit()
        return summary,validation,match
    return rebuild_intake_summary


def install_0410(_rb):
    def _rb_v5462_patient(form):
        mode=(form.get('patient_mode') or 'new').strip().lower()
        if mode=='existing':
            pid=form.get('patient_id',type=int) or form.get('patient',type=int)
            if not pid:
                raise ValueError('Choose an existing patient.')
            patient=_rb.Patient.query.get_or_404(pid)
            from registration_policy import validate_patient
            validate_patient(patient)
            return patient
        return _rb._rb_registration_v2_create_patient(
            form,
            audit_action='PATIENT_CREATE_FROM_FULL_REGISTRATION'
        )
    return _rb_v5462_patient


def install_0413(_rb):
    def _rb_v5462_insurance(order,contract,form):
        if not contract or not contract.approval_required: return
        method=(form.get('approval_method') or 'AUTO').upper()
        if method not in ('AUTO','MANUAL','ALREADY_APPROVED'): method='AUTO'
        approval_no=(form.get('approval_no') or '').strip()
        if method=='ALREADY_APPROVED' and not approval_no:
            raise ValueError('Approval number is required for an already-approved case.')
        status='APPROVED' if method=='ALREADY_APPROVED' else ('PENDING' if method=='AUTO' else 'REQUIRED')
        row=_rb.InsuranceApprovalRequest(
            order_id=order.id,method=method,status=status,
            approval_no=approval_no,payer_name=contract.name,
            member_no=(form.get('member_no') or '').strip(),
            requested_at=_rb.datetime.utcnow(),
            decided_at=(_rb.datetime.utcnow() if status=='APPROVED' else None),
            created_by=_rb.current_user().id
        )
        _rb.db.session.add(row); _rb.db.session.flush()
        _rb.db.session.add(_rb.InsuranceApprovalEvent(
            approval_request_id=row.id,event_type='CREATED_FROM_FULL_REGISTRATION',
            old_status='',new_status=status,message=f'method={method}',
            user_id=_rb.current_user().id
        ))
        order.approval_no=approval_no
    return _rb_v5462_insurance


def install_0589(_rb):
    def _ris_case_only_second_order_checks(order, policy_rows):
        """Fail closed when rows selected for deletion have incoming FK dependents."""
        from sqlalchemy import inspect as _ris_inspect, text as _ris_text

        inspector=_ris_inspect(_rb.db.session.connection())
        tables=sorted(inspector.get_table_names())
        preparer=_rb.db.engine.dialect.identifier_preparer
        blockers=[]
        details=[]

        for policy_row in policy_rows:
            if not policy_row.get('count') or policy_row.get('action') != 'DELETE_CASE_ROW':
                continue
            target_table=str(policy_row.get('table') or '')
            order_column=str(policy_row.get('column') or '')
            pk_columns=inspector.get_pk_constraint(target_table).get('constrained_columns') or []
            if len(pk_columns) != 1:
                blockers.append('SECOND_ORDER_PK_REVIEW: '+target_table)
                continue
            target_pk=pk_columns[0]

            for child_table in tables:
                for fk in inspector.get_foreign_keys(child_table):
                    if fk.get('referred_table') != target_table:
                        continue
                    child_columns=fk.get('constrained_columns') or []
                    referred_columns=fk.get('referred_columns') or []
                    label=child_table+'.'+','.join(child_columns)+' -> '+target_table+'.'+','.join(referred_columns)
                    if len(child_columns) != 1 or len(referred_columns) != 1 or referred_columns[0] != target_pk:
                        blockers.append('SECOND_ORDER_COMPOSITE_FK_REVIEW: '+label)
                        details.append({'relation':label,'count':None,'blocking':True})
                        continue
                    qc_table=preparer.quote(child_table)
                    qc_col=preparer.quote(child_columns[0])
                    qt_table=preparer.quote(target_table)
                    qt_pk=preparer.quote(target_pk)
                    qt_order=preparer.quote(order_column)
                    count=_rb.db.session.execute(
                        _ris_text(
                            'SELECT COUNT(*) FROM '+qc_table+
                            ' WHERE '+qc_col+' IN ('+
                            'SELECT '+qt_pk+' FROM '+qt_table+
                            ' WHERE '+qt_order+' = :order_id)'
                        ),
                        {'order_id':int(order.id)},
                    ).scalar() or 0
                    count=int(count)
                    details.append({'relation':label,'count':count,'blocking':bool(count)})
                    if count:
                        blockers.append('SECOND_ORDER_DEPENDENCY_PRESENT: '+label)
        return {'blockers':blockers,'rows':details}
    return _ris_case_only_second_order_checks


def install_0593(_rb):
    def granular_delete_order_preview_snapshot(order):
        """
    Read-only preview of data associated with one RIS order.
    This helper MUST NOT mutate RIS, PACS, report files, or audit rows.
    """
        from sqlalchemy import inspect, text

        inspector = inspect(_rb.db.engine)
        order_table = _rb.Order.__table__.name

        patient = (
            _rb.db.session.get(_rb.Patient, order.patient_id)
            if getattr(order, 'patient_id', None)
            else None
        )

        dependency_rows = []
        dependency_total = 0
        active_dependency_tables = 0

        for child_table in sorted(inspector.get_table_names()):
            for fk in inspector.get_foreign_keys(child_table):
                if fk.get('referred_table') != order_table:
                    continue

                local_columns = fk.get('constrained_columns') or []

                if len(local_columns) != 1:
                    dependency_rows.append({
                        'table': child_table,
                        'column': ','.join(local_columns),
                        'count': None,
                        'classification': 'COMPOSITE_FK_REVIEW',
                    })
                    continue

                local_column = local_columns[0]

                preparer = _rb.db.engine.dialect.identifier_preparer
                quoted_table = preparer.quote(child_table)
                quoted_column = preparer.quote(local_column)

                count = _rb.db.session.execute(
                    text(
                        'SELECT COUNT(*) FROM '
                        + quoted_table
                        + ' WHERE '
                        + quoted_column
                        + ' = :order_id'
                    ),
                    {'order_id': order.id},
                ).scalar() or 0

                lower = child_table.lower()

                if 'audit' in lower:
                    classification = 'AUDIT_KEEP'
                elif 'report' in lower:
                    classification = 'REPORT_DOMAIN'
                elif any(
                    token in lower
                    for token in ('attach', 'document', 'file')
                ):
                    classification = 'FILE_DOMAIN'
                elif any(
                    token in lower
                    for token in ('pacs', 'study', 'image', 'dicom')
                ):
                    classification = 'PACS_DOMAIN'
                elif any(
                    token in lower
                    for token in (
                        'workflow',
                        'assignment',
                        'lease',
                        'queue',
                    )
                ):
                    classification = 'WORKFLOW_DOMAIN'
                elif any(
                    token in lower
                    for token in (
                        'note',
                        'consum',
                        'nursing',
                        'technician',
                    )
                ):
                    classification = 'CASE_DOMAIN'
                else:
                    classification = 'OTHER_DEPENDENCY'

                dependency_total += int(count)

                if count:
                    active_dependency_tables += 1

                dependency_rows.append({
                    'table': child_table,
                    'column': local_column,
                    'count': int(count),
                    'classification': classification,
                })

        report_rows = []

        if 'order_id' in _rb.Report.__table__.columns:
            reports = (
                _rb.Report.query
                .filter_by(order_id=order.id)
                .order_by(_rb.Report.id.desc())
                .all()
            )

            for report in reports:
                report_rows.append({
                    'id': report.id,
                    'status': getattr(report, 'status', None),
                    'finalized_at': getattr(
                        report,
                        'finalized_at',
                        None,
                    ),
                })

        final_report_present = any(
            str(row.get('status') or '').strip().upper() == 'FINAL'
            for row in report_rows
        )

        reports_only_preview = _rb.granular_delete_reports_only_preview_snapshot(
            order,
            patient,
            reports if 'order_id' in _rb.Report.__table__.columns else [],
        )

        ris_case_only_preview = _rb.granular_delete_ris_case_only_execution_preview_snapshot(
            order,
            dependency_rows,
            report_rows,
        )

        pacs_study_id = (
            getattr(order, 'pacs_study_id', None)
            or ''
        )

        pacs_image_count = (
            getattr(order, 'pacs_image_count', None)
            or 0
        )

        # Read-only Orthanc presence check.
        #
        # linked:
        #     RIS retains a PACS study identifier.
        #
        # present:
        #     True  -> Orthanc confirms the study exists.
        #     False -> no study is linked, or Orthanc confirms HTTP 404.
        #     None  -> presence cannot be established safely.
        #
        # Unknown/error deliberately fails closed for destructive actions.
        pacs_present = False
        pacs_presence_response = None

        if pacs_study_id:
            try:
                pacs_presence_response = _rb.requests.get(
                    f'{_rb.PACS_ORTHANC_URL}/studies/{pacs_study_id}',
                    auth=_rb._orthanc_auth(),
                    timeout=10,
                )

                if pacs_presence_response.status_code == 200:
                    pacs_present = True
                elif pacs_presence_response.status_code == 404:
                    pacs_present = False
                else:
                    pacs_present = None
            except Exception:
                pacs_present = None

        full_case_orchestration = _rb.granular_delete_full_case_orchestration_preview_snapshot(
            order,
            patient,
            dependency_rows,
            report_rows,
            reports_only_preview,
            ris_case_only_preview,
            {
                'study_id': pacs_study_id,
                'status': getattr(order, 'pacs_status', None),
                'image_count': int(pacs_image_count),
                'linked': bool(pacs_study_id),
                'present': pacs_present,
                '_orthanc_response': pacs_presence_response,
            },
        )

        blockers = []

        if active_dependency_tables:
            blockers.append(
                'RIS case deletion remains blocked pending '
                'dependency classification.'
            )

        if final_report_present:
            blockers.append(
                'Final report exists; report deletion requires '
                'elevated destructive-action approval.'
            )

        return {
            'kind': 'ORDER',
            'patient': {
                'id': getattr(patient, 'id', None),
                'patient_id': getattr(
                    patient,
                    'patient_id',
                    None,
                ),
                'name': getattr(patient, 'name', None),
            },
            'order': {
                'id': order.id,
                'accession': getattr(
                    order,
                    'accession',
                    None,
                ),
                'status': getattr(order, 'status', None),
                'exam_status': getattr(
                    order,
                    'exam_status',
                    None,
                ),
                'modality': getattr(
                    order,
                    'modality',
                    None,
                ),
                'procedure': getattr(
                    order,
                    'procedure',
                    None,
                ),
            },
            'pacs': {
                'study_id': pacs_study_id,
                'status': getattr(
                    order,
                    'pacs_status',
                    None,
                ),
                'image_count': int(pacs_image_count),
                'linked': bool(pacs_study_id),
                'present': pacs_present,
            },
            'reports': {
                'count': len(report_rows),
                'rows': report_rows,
                'final_present': final_report_present,
            },
            'reports_only': reports_only_preview,
            'ris_dependencies': {
                'table_count': len(dependency_rows),
                'active_table_count': active_dependency_tables,
                'row_count': dependency_total,
                'rows': dependency_rows,
            },
            'ris_case_only': ris_case_only_preview,
            'full_case_orchestration': full_case_orchestration,
            'safety': {
                'images_only_preview_available': True,
                'reports_only_preview_available': True,
                'reports_only_ready': reports_only_preview['can_delete_reports_only'],
                'ris_case_only_allowed': False,
                'ris_case_only_preflight_ready': ris_case_only_preview['can_prepare_execution'],
                'full_case_orchestration_preview_ready': full_case_orchestration['can_execute_full_case'],
                'full_case_purge_allowed': False,
                'blockers': blockers,
            },
            'readonly': True,
        }
    return granular_delete_order_preview_snapshot


def install_0595(_rb):
    def granular_delete_patient_preview_snapshot(patient):
        """
    Read-only preview of all RIS orders linked to one patient.
    """
        orders = (
            _rb.Order.query
            .filter_by(patient_id=patient.id)
            .order_by(_rb.Order.id.desc())
            .all()
        )

        order_rows = []

        total_reports = 0
        linked_pacs_cases = 0
        active_cases = 0

        for order in orders:
            report_count = 0

            if 'order_id' in _rb.Report.__table__.columns:
                report_count = (
                    _rb.Report.query
                    .filter_by(order_id=order.id)
                    .count()
                )

            total_reports += report_count

            if getattr(order, 'pacs_study_id', None):
                linked_pacs_cases += 1

            order_status = str(
                getattr(order, 'status', '') or ''
            ).strip().upper()

            if order_status not in (
                'CANCELLED',
                'CANCELED',
                'DELETED',
            ):
                active_cases += 1

            order_rows.append({
                'id': order.id,
                'accession': getattr(
                    order,
                    'accession',
                    None,
                ),
                'status': getattr(order, 'status', None),
                'exam_status': getattr(
                    order,
                    'exam_status',
                    None,
                ),
                'pacs_study_id': getattr(
                    order,
                    'pacs_study_id',
                    None,
                ),
                'pacs_image_count': (
                    getattr(
                        order,
                        'pacs_image_count',
                        None,
                    )
                    or 0
                ),
                'report_count': report_count,
            })

        appointment_count = 0

        if hasattr(_rb.Appointment, 'patient_id'):
            appointment_count = (
                _rb.Appointment.query
                .filter_by(patient_id=patient.id)
                .count()
            )

        blockers = []

        if active_cases:
            blockers.append(
                'Patient has active/non-cancelled cases.'
            )

        if orders:
            blockers.append(
                'Full patient purge remains disabled until '
                'all child dependencies are explicitly classified.'
            )

        return {
            'kind': 'PATIENT',
            'patient': {
                'id': patient.id,
                'patient_id': getattr(
                    patient,
                    'patient_id',
                    None,
                ),
                'name': getattr(patient, 'name', None),
            },
            'summary': {
                'order_count': len(orders),
                'appointment_count': appointment_count,
                'report_count': total_reports,
                'pacs_linked_case_count': linked_pacs_cases,
                'active_case_count': active_cases,
            },
            'orders': order_rows,
            'safety': {
                'full_patient_purge_allowed': False,
                'blockers': blockers,
            },
            'readonly': True,
        }
    return granular_delete_patient_preview_snapshot


def install_0687(_rb):
    def order_is_open_pool(order):
        if order.assigned_doctor_id:
            return False

        strategy=_rb.assignment_strategy_for_order(order)

        if strategy and str(strategy.assignment_mode or '').upper()=='OPEN_POOL':
            return True

        last_event=_rb.AssignmentEscalationEvent.query.filter_by(
            order_id=order.id
        ).order_by(
            _rb.AssignmentEscalationEvent.id.desc()
        ).first()

        if last_event and last_event.event_type=='OPEN_POOL':
            return True

        return False
    return order_is_open_pool


def install_0747(_rb):
    def _apply_smart_intake_ocr_result(doc, result):
        """Apply OCR output and attach a non-authoritative document-type suggestion."""
        fields = dict(result.get('fields') or {})

        classification = _rb.classify_document_text(result.get('text') or '')

        fields['_document_classification'] = {
            'suggested_type': classification.get('suggested_type') or classification.get('type') or 'OTHER',
            'safe_type': classification.get('type') or 'OTHER',
            'confidence': float(classification.get('confidence') or 0),
            'status': classification.get('status') or 'UNCLASSIFIED',
            'hits': classification.get('hits') or [],
            'declared_type': doc.document_type,
        }

        doc.ocr_text = result.get('text') or ''
        doc.extracted_json = _rb.json.dumps(fields, ensure_ascii=False)
        doc.confidence = float(result.get('confidence') or 0)
        doc.status = 'REVIEW_REQUIRED'
        doc.ocr_error = ''

        cfg = _rb.enabled_ocr_provider()
        doc.ocr_provider_key = cfg.provider_key if cfg else ''
        doc.ocr_config_hash = _rb.ocr_configuration_hash(cfg) if cfg else ''

        # ========================================================
        # RB_SMART_INTAKE_OCR_FIELD_SYNC_V1
        #
        # Persist OCR suggestions into SmartIntakeFieldReview so
        # the identity-review / registration UI can consume them.
        #
        # OCR suggestions remain PENDING here. final_value and
        # ACCEPTED/CORRECTED status are set only by the explicit
        # review/save workflow.
        # ========================================================

        core_fields = {
            key: str(fields.get(key) or '').strip()
            for key in _rb.OCR_INTAKE_CORE_FIELDS
        }

        normalized = _rb.normalize_intake_identity(
            core_fields
        )

        validation = _rb.validate_intake_identity(
            normalized
        )

        validation_fields = (
            validation.get('fields')
            or {}
        )

        for field_key in _rb.OCR_INTAKE_CORE_FIELDS:

            extracted = str(
                core_fields.get(field_key)
                or ''
            )

            normalized_value = str(
                normalized.get(field_key)
                or ''
            )

            # Keep rows already reviewed by a user untouched.
            row = (
                _rb.SmartIntakeFieldReview.query
                .filter_by(
                    intake_id=doc.intake_id,
                    field_key=field_key
                )
                .first()
            )

            if not row:
                row = _rb.SmartIntakeFieldReview(
                    intake_id=doc.intake_id,
                    field_key=field_key
                )
                _rb.db.session.add(row)

            if row.review_status in (
                'ACCEPTED',
                'CORRECTED'
            ):
                continue

            if extracted or normalized_value:

                item = (
                    validation_fields.get(
                        field_key
                    )
                    or {}
                )

                row.source_document_id = doc.id
                row.source_type = (
                    doc.document_type
                    or ''
                )

                row.extracted_value = extracted
                row.normalized_value = normalized_value

                row.confidence = float(
                    result.get('confidence')
                    or 0
                )

                row.validation_status = str(
                    item.get('status')
                    or 'warning'
                ).upper()

                row.validation_message = str(
                    item.get('message')
                    or ''
                )[:500]

                row.review_status = 'PENDING'

        return classification
    return _apply_smart_intake_ocr_result


def install_0751(_rb):
    def _save_intake_review_fields(intake,submitted,validation):
        clean=validation['normalized'];now=_rb.datetime.utcnow();uid=_rb.current_user().id
        for field_key in _rb.OCR_INTAKE_CORE_FIELDS:
            row=_rb.SmartIntakeFieldReview.query.filter_by(intake_id=intake.id,field_key=field_key).first()
            if not row:
                row=_rb.SmartIntakeFieldReview(intake_id=intake.id,field_key=field_key);_rb.db.session.add(row)
            final=str(clean.get(field_key) or '')
            row.final_value=final
            row.review_status='CORRECTED' if final!=str(row.normalized_value or '') else 'ACCEPTED'
            item=validation['fields'].get(field_key,{})
            row.validation_status=(item.get('status') or 'warning').upper()
            row.validation_message=(item.get('message') or '')[:500]
            row.reviewed_by=uid;row.reviewed_at=now
        intake.review_notes=(submitted.get('review_notes') or '').strip()[:2000]
        intake.reviewed_by=uid;intake.reviewed_at=now
    return _save_intake_review_fields


def install_0752(_rb):
    def _save_intake_visit_review(intake,form):
        procedure_id=form.get('procedure_id',type=int)
        contract_id=form.get('contract_id',type=int)
        procedure=_rb.Procedure.query.filter_by(id=procedure_id,active=True).first() if procedure_id else None
        contract=_rb.Contract.query.filter_by(id=contract_id,active=True).first() if contract_id else None
        approval_no=(form.get('approval_no') or '').strip()[:120]
        if not (contract and contract.approval_required): approval_no=''
        try: summary=_rb.json.loads(intake.extracted_json or '{}')
        except Exception: summary={}
        if not isinstance(summary,dict): summary={}
        summary['visit_review']={
          'procedure_id':procedure.id if procedure else None,
          'procedure_name':procedure.name if procedure else '',
          'contract_id':contract.id if contract else None,
          'contract_name':contract.name if contract else '',
          'approval_required':bool(contract and contract.approval_required),
          'approval_no':approval_no,
          'reviewed':True,
          'reviewed_by':_rb.current_user().id,
          'reviewed_at':_rb.datetime.utcnow().isoformat()+'Z',
        }
        intake.suggested_procedure_id=procedure.id if procedure else None
        intake.suggested_contract_id=contract.id if contract else None
        intake.extracted_json=_rb.json.dumps(summary,ensure_ascii=False)
        return summary['visit_review']
    return _save_intake_visit_review


def install_0753(_rb):
    def _attach_intake_documents(intake,patient):
        docs=_rb.SmartIntakeDocument.query.filter_by(intake_id=intake.id,status='APPROVED').all()
        for doc in docs:
            if doc.patient_document_id: continue
            attached=_rb.PatientDocument(
              patient_id=patient.id,document_type=doc.document_type,category='SMART_INTAKE',
              file_path=doc.file_path,original_name=doc.original_name,
              extracted_text=doc.ocr_text,extraction_status='COMPLETED',review_status='APPROVED',
              reviewer_id=doc.reviewed_by,review_notes=doc.review_notes,
              uploaded_by=intake.created_by,reviewed_at=doc.reviewed_at)
            _rb.db.session.add(attached);_rb.db.session.flush();doc.patient_document_id=attached.id
    return _attach_intake_documents


def install_0840(_rb):
    def _external_intake_generated_accession(row):
        """Return a stable local reference without pretending it came from DICOM."""
        center_code=(_rb.re.sub(r'[^A-Z0-9_-]','',str(row.center.code or '').upper()) or 'CENTER')[:20]
        return f'EXT-{center_code}-{row.id}'[:40]
    return _external_intake_generated_accession


def install_0841(_rb):
    def _external_intake_local_patient_id(row):
        """Create a unique RIS identity while preserving the external ID separately."""
        center_code=(_rb.re.sub(r'[^A-Z0-9_-]','',str(row.center.code or '').upper()) or 'CENTER')[:12]
        external_id=(
            str(row.expected_patient_id or '').strip()
            or str(row.dicom_patient_id or '').strip()
            or str(row.inbox.pacs_patient_id or '').strip()
            or 'UNKNOWN'
        )
        external_id=_rb.re.sub(r'[^A-Z0-9_-]','-',external_id.upper()).strip('-') or 'UNKNOWN'
        suffix=f'-{row.id}'
        prefix=f'EXT-{center_code}-'
        available=max(1,40-len(prefix)-len(suffix))
        return (prefix+external_id[:available]+suffix)[:40]
    return _external_intake_local_patient_id


def install_0842(_rb):
    def external_intake_autofill(row,tags=None):
        """Prefill empty referral fields but never mark them independently verified."""
        # RB_EXTERNAL_INTAKE_AUTOFILL_V1
        tags=tags or {}
        inbox=row.inbox
        proposed={
            'expected_patient_id':str(tags.get('patient_id') or inbox.pacs_patient_id or '').strip(),
            'expected_patient_name':str(tags.get('patient_name') or inbox.pacs_patient_name or '').replace('^',' ').strip(),
            'expected_dob':_rb.normalize_date(tags.get('dob')),
            'expected_sex':str(tags.get('sex') or '').strip().upper()[:1],
            'expected_accession':str(tags.get('accession') or inbox.accession or '').strip(),
        }
        if not proposed['expected_accession']:
            proposed['expected_accession']=_rb._external_intake_generated_accession(row)
        for field,value in proposed.items():
            if not str(getattr(row,field) or '').strip() and value:
                setattr(row,field,value)
        return proposed
    return external_intake_autofill


def install_0845(_rb):
    def external_intake_demographic_verification(row,persist=False,actor_user_id=None):
        """Fail-closed comparison of referral identity against live DICOM identity."""
        dicom,error=_rb.external_intake_dicom_demographics(row)
        expected={
            'patient_id':str(row.expected_patient_id or '').strip(),
            'patient_name':str(row.expected_patient_name or '').strip(),
            'dob':_rb.normalize_date(row.expected_dob),
            'sex':str(row.expected_sex or '').strip().upper()[:1],
            'accession':str(row.expected_accession or '').strip(),
        }
        normalizers={
            'patient_id':lambda value:str(value or '').strip().upper(),
            'patient_name':lambda value:_rb.normalize_person_name(value),
            'dob':lambda value:_rb.normalize_date(value),
            'sex':lambda value:str(value or '').strip().upper()[:1],
            'accession':lambda value:str(value or '').strip().upper(),
        }
        labels={
            'patient_id':'Patient ID','patient_name':'Patient Name','dob':'DOB',
            'sex':'Sex','accession':'Accession'
        }
        critical={'patient_id','dob','accession'}
        checks=[]
        matches=0
        comparable=0
        hard_mismatch=False
        review_required=bool(error)
        for key in ('patient_id','patient_name','dob','sex','accession'):
            left=normalizers[key](expected.get(key))
            right=normalizers[key](dicom.get(key))
            if not left or not right:
                state='MISSING'
                review_required=True
            elif left==right:
                state='MATCH'
                matches+=1
                comparable+=1
            else:
                state='MISMATCH'
                comparable+=1
                if key in critical:
                    hard_mismatch=True
                else:
                    review_required=True
            checks.append({
                'field':labels[key],'expected':expected.get(key) or '',
                'dicom':dicom.get(key) or '','status':state,'critical':key in critical
            })
        if hard_mismatch:
            status='BLOCKED'
        elif review_required:
            status='REVIEW_REQUIRED'
        else:
            status='MATCHED'
        score=round((matches/comparable)*100,2) if comparable else 0.0
        facts={
            'expected':expected,'dicom':dicom,'checks':checks,'source_error':error
        }
        facts_sha256=_rb.hashlib.sha256(
            _rb.json.dumps(facts,sort_keys=True,ensure_ascii=False).encode('utf-8')
        ).hexdigest()
        result={
            'status':status,'score':score,'checks':checks,'facts_sha256':facts_sha256,
            'source_error':error,'expected':expected,'dicom':dicom
        }
        if persist:
            row.dicom_patient_id=dicom.get('patient_id') or ''
            row.dicom_patient_name=dicom.get('patient_name') or ''
            row.dicom_dob=dicom.get('dob') or ''
            row.dicom_sex=dicom.get('sex') or ''
            row.dicom_accession=dicom.get('accession') or ''
            row.demographic_status=status
            row.demographic_score=score
            row.demographic_checks_json=_rb.json.dumps(checks,ensure_ascii=False)
            row.demographic_facts_sha256=facts_sha256
            row.demographic_verified_by=actor_user_id
            row.demographic_verified_at=_rb.datetime.utcnow()
            if row.demographic_override_facts_sha256!=facts_sha256:
                row.demographic_override_approved=False
                row.demographic_override_reason=''
                row.demographic_override_by=None
                row.demographic_override_at=None
                row.demographic_override_facts_sha256=''
        return result
    return external_intake_demographic_verification
