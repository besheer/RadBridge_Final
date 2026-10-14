"""Runtime-bound application.components.imaging; dependencies are supplied at composition.

Legacy behavior is preserved; new policies belong in the independent domain layer.
"""

def install_0014(_rb):
    def _orthanc_auth():
        return (_rb.PACS_ORTHANC_USER,_rb.PACS_ORTHANC_PASSWORD) if _rb.PACS_ORTHANC_USER else None
    return _orthanc_auth


def install_0015(_rb):
    def pacs_lookup_order(order):
        accession=str(order.accession or '').strip()
        if not accession:
            return {'count':0,'status':'WAITING','study_id':''}
        try:
            r=_rb.requests.post(
                _rb.PACS_ORTHANC_URL+'/tools/find',
                auth=_rb._orthanc_auth(),
                json={'Level':'Study','Query':{'AccessionNumber':accession},'Expand':True,'Limit':20},
                timeout=10
            )
            r.raise_for_status()
            studies=r.json() or []
        except Exception:
            order.pacs_status='PACS_OFFLINE'
            return {'count':int(order.pacs_image_count or 0),'status':'PACS_OFFLINE','study_id':order.pacs_study_id or ''}

        if not studies:
            order.pacs_image_count=0
            order.pacs_status='WAITING'
            order.pacs_last_seen_at=_rb.datetime.utcnow()
            return {'count':0,'status':'WAITING','study_id':''}

        blocked=_rb.DicomCorrection.query.filter(
            _rb.db.or_(_rb.DicomCorrection.status.in_(['PENDING','CREATED']),
                   _rb.db.and_(_rb.DicomCorrection.status=='NEEDS_REVIEW',_rb.DicomCorrection.new_study_id==''))).first()
        if blocked:
            return {'count':int(order.pacs_image_count or 0),'status':'REVIEW_REQUIRED','study_id':order.pacs_study_id or ''}
        excluded={row.source_study_id for row in _rb.DicomCorrection.query.all()}
        excluded.update(row.new_study_id for row in _rb.DicomCorrection.query.filter(_rb.DicomCorrection.status!='COMPLETED').all())
        studies=[st for st in studies if st.get('ID') not in excluded]
        count=0
        study_id=''
        for st in studies:
            study_id=study_id or st.get('ID','')
            stats=st.get('Statistics') or {}
            c=stats.get('CountInstances')
            if c is None:
                instances=st.get('Instances')
                if instances is not None:
                    c=len(instances or [])
                else:
                    c=0
                    for series_id in (st.get('Series') or []):
                        try:
                            sr=_rb.requests.get(
                                _rb.PACS_ORTHANC_URL+'/series/'+str(series_id),
                                auth=_rb._orthanc_auth(),
                                timeout=8,
                            )
                            sr.raise_for_status()
                            series_data=sr.json() or {}
                            c += len(series_data.get('Instances') or [])
                        except Exception:
                            continue
            count += int(c or 0)

        now=_rb.datetime.utcnow()
        previous=int(order.pacs_image_count or 0)
        if count != previous:
            order.pacs_last_change_at=now

        order.pacs_image_count=count
        order.pacs_last_seen_at=now
        order.pacs_study_id=study_id or order.pacs_study_id or ''

        if count<=0:
            status='WAITING'
        elif not __import__('workflow_engine').acquisition_completed(order.exam_status):
            status='RECEIVING'
        elif order.pacs_last_change_at and (now-order.pacs_last_change_at).total_seconds()>=_rb.PACS_IMAGES_STABLE_SECONDS:
            status='IMAGES_COMPLETE'
        else:
            status='RECEIVING'

        order.pacs_status=status
        return {'count':count,'status':status,'study_id':study_id}
    return pacs_lookup_order


def install_0033(_rb):
    def _orthanc_recent_studies(limit=100):
        try:
            r=_rb.requests.post(_rb.PACS_ORTHANC_URL+'/tools/find',auth=_rb._orthanc_auth(),
                json={'Level':'Study','Query':{},'Expand':True,'Limit':limit},timeout=15)
            r.raise_for_status();return r.json() or []
        except:return []
    return _orthanc_recent_studies


def install_0035(_rb):
    def strict_pacs_demographic_match(tags):
        """
    Safe PACS demographic gate.

    Automatic linking requires:
      - exact Accession
      - exact Patient ID
      - exact DOB

    Any mismatch requires manual review.
    Patient name is informational and is never sufficient for auto-link.
    """
        accession = str(tags.get('accession') or '').strip()
        pacs_pid = str(tags.get('patient_id') or '').strip()
        pacs_dob = str(tags.get('dob') or '').strip()[:8]

        if not accession:
            return None, 'ACCESSION_MISSING', 'REVIEW_REQUIRED'

        order = _rb.Order.query.filter_by(accession=accession).first()

        if not order:
            return None, 'ACCESSION_NOT_FOUND', 'REVIEW_REQUIRED'

        patient = _rb.Patient.query.get(order.patient_id)

        if not patient:
            return order, 'RIS_PATIENT_NOT_FOUND', 'REVIEW_REQUIRED'

        ris_pid = str(patient.patient_id or '').strip()
        ris_dob = str(patient.dob or '').strip()[:8]

        mismatches = []

        if not pacs_pid or pacs_pid != ris_pid:
            mismatches.append('PATIENT_ID')

        if not pacs_dob or pacs_dob != ris_dob:
            mismatches.append('DOB')

        if mismatches:
            if len(mismatches) > 1:
                reason = 'MULTIPLE_MISMATCH:' + ','.join(mismatches)
            else:
                reason = mismatches[0] + '_MISMATCH'

            return order, reason, 'REVIEW_REQUIRED'

        return order, 'DEMOGRAPHICS_EXACT', 'AUTO_SAFE'
    return strict_pacs_demographic_match


def install_0036(_rb):
    def pacs_demographic_gate(order):
        """
    Central safety gate for PACS/AI/reporting.

    Allowed:
      1. PACS study has an AUTO_SAFE strict demographic match.
      2. PACS study was manually reconciled by an authorized user.

    Blocked:
      - REVIEW_REQUIRED
      - missing/unreconciled PACS study
      - demographic mismatch without authorized reconciliation
    """

        if not order:
            return False, 'ORDER_NOT_FOUND'

        # Exam metadata is an independent safety boundary; demographic overrides
        # and minimum-count overrides cannot authorize a conflicting acquisition.
        from exam_type_policy import cached_exam_gate
        type_ok,type_reason=cached_exam_gate(order,_rb.CaseReadiness.query.filter_by(order_id=order.id).first())
        if not type_ok:
            return False,type_reason

        # A study waiting for demographic review always blocks downstream actions.
        review = _rb.PacsStudyInbox.query.filter(
            _rb.PacsStudyInbox.state == 'REVIEW_REQUIRED',
            _rb.PacsStudyInbox.accession == order.accession
        ).order_by(_rb.PacsStudyInbox.id.desc()).first()

        if review:
            return False, 'PACS_DEMOGRAPHIC_REVIEW_REQUIRED'

        match = _rb.PacsStudyMatch.query.filter_by(
            order_id=order.id
        ).order_by(_rb.PacsStudyMatch.id.desc()).first()

        if not match:
            return False, 'PACS_DEMOGRAPHIC_MATCH_NOT_VERIFIED'

        confidence = str(match.confidence or '').upper()
        method = str(match.match_method or '').upper()

        if confidence == 'AUTO_SAFE' and method == 'DEMOGRAPHICS_EXACT':
            return True, 'AUTO_SAFE'

        if method in ('MANUAL_CONFIRMED','OVERRIDE_APPROVED') and confidence in ('CONFIRMED','OVERRIDE_APPROVED'):
            return True, method

        return False, 'PACS_DEMOGRAPHIC_MATCH_NOT_VERIFIED'
    return pacs_demographic_gate


def install_0038(_rb):
    def _orthanc_study_detail(study_id):
        try:
            r=_rb.requests.get(f'{_rb.PACS_ORTHANC_URL}/studies/{study_id}',auth=_rb._orthanc_auth(),timeout=15)
            r.raise_for_status()
            return r.json() or {}
        except Exception:
            return {}
    return _orthanc_study_detail


def install_0040(_rb):
    def _orthanc_series_detail(series_id):
        try:
            r=_rb.requests.get(f'{_rb.PACS_ORTHANC_URL}/series/{series_id}',auth=_rb._orthanc_auth(),timeout=10)
            r.raise_for_status();return r.json() or {}
        except Exception:return {}
    return _orthanc_series_detail


def install_0041(_rb):
    def _orthanc_instance_remote_aet(instance_id):
        """Return the sending AE recorded by Orthanc for one received instance."""
        try:
            r=_rb.requests.get(
                f'{_rb.PACS_ORTHANC_URL}/instances/{instance_id}/metadata',
                auth=_rb._orthanc_auth(),params={'expand':'true'},timeout=10
            )
            r.raise_for_status();metadata=r.json() or {}
            return str(
                metadata.get('RemoteAET') or metadata.get('RemoteAet') or ''
            ).strip().upper()
        except Exception:
            return ''
    return _orthanc_instance_remote_aet


def install_0042(_rb):
    def _parse_dicom_date(value):
        value=str(value or '').strip()
        try:return _rb.datetime.strptime(value[:8],'%Y%m%d')
        except Exception:return _rb.datetime.utcnow()
    return _parse_dicom_date


def install_0043(_rb):
    def provisional_patient_from_pacs(tags):
        p=_rb.Patient(
          patient_id=_rb.next_patient_id(),
          name=(tags.get('patient_name') or f"PACS Imported {tags.get('patient_id') or ''}").replace('^',' ').strip(),
          dob=str(tags.get('dob') or '')[:8],
          sex='',
          phone='',
          worklist_name='PACS AUTO INTAKE'
        )
        _rb.db.session.add(p);_rb.db.session.flush()
        return p
    return provisional_patient_from_pacs


def install_0044(_rb):
    def create_order_from_pacs(tags):
        branch=_rb.Branch.query.filter_by(active=True).order_by(_rb.Branch.id).first()
        if not branch:
            branch=_rb.Branch(code='MAIN',name='Main Branch',active=True);_rb.db.session.add(branch);_rb.db.session.flush()
        modality=(str(tags.get('modality') or 'OT').split('\\')[0].strip().upper() or 'OT')[:8]
        accession=str(tags.get('accession') or '').strip()
        if not accession or _rb.Order.query.filter_by(accession=accession).first():
            accession=_rb.new_accession()
        patient=_rb.provisional_patient_from_pacs(tags)
        description=(tags.get('study_description') or f'{modality} PACS Imported Study').strip()[:120]
        o=_rb.Order(
          accession=accession,patient_id=patient.id,modality=modality,procedure=description,
          station_ae=(tags.get('source_ae') or '')[:40],scheduled=_rb._parse_dicom_date(tags.get('study_date')),
          status='IMAGES_RECEIVED',branch_id=branch.id,created_at=_rb.datetime.utcnow(),
          exam_status='EXAM_COMPLETED',exam_completed_at=_rb.datetime.utcnow(),
          pacs_image_count=int(tags.get('instances') or 0),pacs_status='RECEIVED',
          pacs_last_seen_at=_rb.datetime.utcnow(),pacs_last_change_at=_rb.datetime.utcnow(),
          pacs_study_id=tags.get('study_id') or '',study_instance_uid=tags.get('study_instance_uid') or ''
        )
        _rb.db.session.add(o);_rb.db.session.flush()
        return o
    return create_order_from_pacs


def install_0045(_rb):
    def pacs_auto_intake_once(limit=200):
        from pacs_resolution_service import atomic_primary_link
        result={'seen':0,'linked':0,'created':0,'review_required':0,'errors':0}
        for st in _rb._orthanc_recent_studies(limit):
            tags=_rb._study_tags_extended(st);sid=tags.get('study_id')
            _rb.discover_dicom_node_from_tags(tags)
            if not sid: continue
            result['seen']+=1
            try:
                inbox=_rb.PacsStudyInbox.query.filter_by(orthanc_study_id=sid).first()
                if not inbox:
                    inbox=_rb.PacsStudyInbox(
                      orthanc_study_id=sid,study_instance_uid=(tags.get('study_instance_uid') or None),
                      pacs_patient_id=tags.get('patient_id',''),pacs_patient_name=tags.get('patient_name',''),
                      accession=tags.get('accession',''),modality=tags.get('modality',''),
                      study_description=tags.get('study_description',''),source_ae=tags.get('source_ae',''),
                      image_count=int(tags.get('instances') or 0),state='NEW')
                    _rb.db.session.add(inbox);_rb.db.session.flush()
                else:
                    inbox.last_seen_at=_rb.datetime.utcnow()
                    inbox.image_count=int(tags.get('instances') or inbox.image_count or 0)

                if _rb.DicomCorrection.query.filter(
                    _rb.db.or_(_rb.DicomCorrection.source_study_id==sid,
                           _rb.db.and_(_rb.DicomCorrection.new_study_id==sid,_rb.DicomCorrection.status!='COMPLETED'))
                ).first() or _rb.DicomCorrection.query.filter(_rb.db.or_(_rb.DicomCorrection.status.in_(['PENDING','CREATED']),_rb.db.and_(_rb.DicomCorrection.status=='NEEDS_REVIEW',_rb.DicomCorrection.new_study_id==''))).first():
                    _rb.db.session.rollback()
                    continue

                # Known external sources never enter the internal auto-match path.
                # The master/center switches control capture, while disabled known
                # sources remain blocked and visible in PACS inbox diagnostics.
                external_center=_rb.ExternalReportingCenter.query.filter(
                    _rb.db.func.upper(_rb.ExternalReportingCenter.ae_title)==str(inbox.source_ae or '').strip().upper()
                ).first()
                if external_center:
                    setting=_rb.external_reporting_setting()
                    if setting.enabled and external_center.active and external_center.receiving_enabled:
                        if not _rb.ExternalIntakeCase.query.filter_by(inbox_id=inbox.id).first():
                            _rb.db.session.add(_rb.ExternalIntakeCase(center_id=external_center.id,inbox_id=inbox.id,status='RECEIVED'))
                        inbox.state='EXTERNAL_INTAKE'
                        result['review_required']+=1
                    else:
                        inbox.state='EXTERNAL_BLOCKED'
                    _rb.db.session.commit()
                    continue

                match=_rb.PacsStudyMatch.query.filter_by(orthanc_study_id=sid).first()
                if match:
                    if not match.is_current:
                        inbox.state='SUPERSEDED'
                        result['linked']+=1
                        _rb.db.session.commit()
                        continue
                    order=match.order
                    if order:
                        atomic_primary_link(
                            db=_rb.db,Order=_rb.Order,Report=_rb.Report,
                            PacsStudyInbox=_rb.PacsStudyInbox,PacsStudyMatch=_rb.PacsStudyMatch,
                            PacsResolutionEvent=_rb.PacsResolutionEvent,order_id=order.id,
                            orthanc_study_id=sid,
                            study_instance_uid=tags.get('study_instance_uid') or '',
                            image_count=inbox.image_count,match_method=match.match_method,
                            confidence=match.confidence,actor_user_id=None,
                            reason='Existing current PACS match refresh',
                            pacs_patient_id=tags.get('patient_id',''),
                            pacs_patient_name=tags.get('patient_name',''),
                            pacs_accession=tags.get('accession',''))
                        _rb.evaluate_case_readiness(order)
                    result['linked']+=1
                    _rb.db.session.commit()
                    continue

                order,reason,decision=_rb.strict_pacs_demographic_match(tags)
                if order and decision=='AUTO_SAFE':
                    atomic_primary_link(
                        db=_rb.db,Order=_rb.Order,Report=_rb.Report,
                        PacsStudyInbox=_rb.PacsStudyInbox,PacsStudyMatch=_rb.PacsStudyMatch,
                        PacsResolutionEvent=_rb.PacsResolutionEvent,order_id=order.id,
                        orthanc_study_id=sid,
                        study_instance_uid=tags.get('study_instance_uid') or '',
                        image_count=inbox.image_count,match_method='DEMOGRAPHICS_EXACT',
                        confidence='AUTO_SAFE',actor_user_id=None,
                        reason='Strict match: Accession + Patient ID + DOB',
                        pacs_patient_id=tags.get('patient_id',''),
                        pacs_patient_name=tags.get('patient_name',''),
                        pacs_accession=tags.get('accession',''))
                    _rb.evaluate_case_readiness(order)
                    _rb.enqueue_auto_routes_for_inbox(inbox)
                    result['linked']+=1
                else:
                    inbox.order_id=None;inbox.state='REVIEW_REQUIRED';inbox.match_method=reason
                    inbox.error_text=(f'{reason}; suggested_order_id={order.id if order else ""}')[:2000]
                    result['review_required']+=1
                _rb.db.session.commit()
            except Exception as exc:
                _rb.db.session.rollback();result['errors']+=1
                _rb.app.logger.exception('PACS intake failed study=%s: %s',sid,exc)
        return result
    return pacs_auto_intake_once


def install_0046(_rb):
    def discover_dicom_node_from_tags(tags):
        ae=(tags.get('source_ae') or '').strip().upper()
        if not ae:
            return None
        host=(tags.get('source_ip') or '').strip()
        row=_rb.DiscoveredDicomNode.query.filter_by(ae_title=ae,host=host).first()
        if not row:
            # If source IP is not available from Orthanc study metadata, keep one AE-only discovery record.
            if not host:
                row=_rb.DiscoveredDicomNode.query.filter_by(ae_title=ae,host='').first()
            if not row:
                row=_rb.DiscoveredDicomNode(
                    ae_title=ae,host=host,node_type='MODALITY',
                    modality=(tags.get('modality') or '')[:30],
                    source_description=(tags.get('study_description') or '')[:255],
                    status='PENDING',studies_seen=0)
                _rb.db.session.add(row);_rb.db.session.flush()
        if row.status=='DISMISSED':
            return row
        row.last_seen_at=_rb.datetime.utcnow()
        row.studies_seen=int(row.studies_seen or 0)+1
        if tags.get('modality'):
            row.modality=str(tags.get('modality'))[:30]
        if tags.get('study_description'):
            row.source_description=str(tags.get('study_description'))[:255]
        return row
    return discover_dicom_node_from_tags


def install_0048(_rb):
    def sync_destination_to_orthanc(dest):
        # Outbound destinations never grant incoming C-FIND/C-STORE permissions.
        payload={'AET':dest.ae_title,'Host':dest.host,'Port':int(dest.port),
                 'AllowEcho':True,'AllowFind':False,'AllowFindWorklist':False,'AllowStore':False,
                 'AllowMove':False,'AllowGet':False}
        r=_rb.requests.put(f'{_rb.PACS_ORTHANC_URL}/modalities/{dest.key}',auth=_rb._orthanc_auth(),json=payload,timeout=15)
        r.raise_for_status()
        return True
    return sync_destination_to_orthanc


def install_0051(_rb):
    def test_dicom_destination(dest):
        _rb.sync_destination_to_orthanc(dest)
        r=_rb.requests.post(f'{_rb.PACS_ORTHANC_URL}/modalities/{dest.key}/echo',auth=_rb._orthanc_auth(),timeout=30)
        r.raise_for_status()
        return True
    return test_dicom_destination


def install_0052(_rb):
    def process_pacs_transfer_jobs(limit=20):
        jobs=_rb.PacsTransferJob.query.filter(_rb.PacsTransferJob.status.in_(['PENDING','FAILED']),_rb.PacsTransferJob.attempts<5).order_by(_rb.PacsTransferJob.id).limit(limit).all()
        done=0
        for job in jobs:
            if job.status=='CANCELLED':continue
            job.attempts+=1;job.status='SENDING';job.started_at=_rb.datetime.utcnow();job.last_error=''
            if not job.progress_total and job.order:
                job.progress_total=int(job.order.pacs_image_count or 0)
            _rb.db.session.commit()
            try:
                _rb.test_dicom_destination(job.destination)
                payload={'Resources':[job.orthanc_study_id],'Synchronous':True}
                r=_rb.requests.post(f'{_rb.PACS_ORTHANC_URL}/modalities/{job.destination.key}/store',
                  auth=_rb._orthanc_auth(),json=payload,timeout=600)
                r.raise_for_status()
                job.status='SUCCESS';job.completed_at=_rb.datetime.utcnow();job.verified_at=_rb.datetime.utcnow();job.last_error=''
                job.progress_sent=int(job.progress_total or (job.order.pacs_image_count if job.order else 0) or 0);done+=1
            except Exception as exc:
                job.status='FAILED';job.last_error=str(exc)[:2000]
            _rb.db.session.commit()
        return done
    return process_pacs_transfer_jobs


def install_0074(_rb):
    def _public_pacs_base():
        base=(_rb.ORTHANC_PUBLIC_URL or 'http://pacs.radbridges.com').rstrip('/')
        # Prevent accidental double UI suffixes from environment values.
        base=_rb.re.sub(r'/(ui|ui/app)/?$', '', base)
        return base.rstrip('/')
    return _public_pacs_base


def install_0075(_rb):
    def ohif_study_uid(order):
        if not order:
            return None

        if order.pacs_study_id:
            try:
                r=_rb.requests.get(
                    f'{_rb.OHIF_INTERNAL_URL}/orthanc-api/studies/{order.pacs_study_id}',
                    timeout=5
                )

                r.raise_for_status()
                data=r.json() or {}

                tags=data.get('MainDicomTags') or {}

                uid=(
                    tags.get('StudyInstanceUID')
                    or data.get('StudyInstanceUID')
                )

                if uid:
                    return str(uid).strip()

            except Exception:
                _rb.app.logger.exception(
                    'Orthanc study lookup failed for order %s study %s',
                    getattr(order,'id',None),
                    getattr(order,'pacs_study_id','')
                )

        # Fallback to QIDO by Accession where AccessionNumber exists.
        if order.accession:
            try:
                r=_rb.requests.get(
                    f'{_rb.OHIF_INTERNAL_URL}/dicom-web/studies',
                    params={'AccessionNumber':order.accession},
                    timeout=5
                )

                r.raise_for_status()
                studies=r.json() or []

                if studies:
                    tag=studies[0].get('0020000D') or {}
                    values=tag.get('Value') or []

                    if values:
                        return str(values[0]).strip() or None

            except Exception:
                _rb.app.logger.exception(
                    'DICOMweb UID lookup failed for order %s accession %s',
                    getattr(order,'id',None),
                    getattr(order,'accession','')
                )

        return None
    return ohif_study_uid


def install_0076(_rb):
    def _ohif_identity_serializer():
        from itsdangerous import URLSafeTimedSerializer

        secret = (
            _rb.os.getenv("OHIF_DOCTOR_IDENTITY_SECRET", "").strip()
            or _rb.app.config.get("SECRET_KEY")
        )

        if not secret:
            raise RuntimeError("OHIF doctor identity secret is not configured")

        return URLSafeTimedSerializer(
            secret_key=secret,
            salt="radbridge-ohif-doctor-identity-v1"
        )
    return _ohif_identity_serializer


def install_0077(_rb):
    def create_ohif_doctor_identity(user, order):
        if not user or not user.active:
            raise ValueError("ACTIVE_USER_REQUIRED")

        role = (
            user.role.code
            if getattr(user, "role", None)
            else ""
        )

        payload = {
            "purpose": "OHIF_REPORTING",
            "user_id": int(user.id),
            "username": str(user.username or ""),
            "full_name": str(user.full_name or user.username or ""),
            "role": str(role or "").upper(),
            "order_id": int(order.id),
        }

        return _rb._ohif_identity_serializer().dumps(payload)
    return create_ohif_doctor_identity


def install_0078(_rb):
    def verify_ohif_doctor_identity(token, order_id=None):
        from itsdangerous import BadSignature, SignatureExpired

        token = str(token or "").strip()

        if not token:
            return None, "DOCTOR_IDENTITY_REQUIRED"

        try:
            payload = _rb._ohif_identity_serializer().loads(
                token,
                max_age=_rb.OHIF_DOCTOR_IDENTITY_MAX_AGE
            )
        except SignatureExpired:
            return None, "DOCTOR_IDENTITY_EXPIRED"
        except BadSignature:
            return None, "DOCTOR_IDENTITY_INVALID"
        except Exception:
            _rb.app.logger.exception("Doctor identity verification failed")
            return None, "DOCTOR_IDENTITY_INVALID"

        if payload.get("purpose") != "OHIF_REPORTING":
            return None, "DOCTOR_IDENTITY_INVALID"

        try:
            user_id = int(payload.get("user_id"))
            token_order_id = int(payload.get("order_id"))
        except Exception:
            return None, "DOCTOR_IDENTITY_INVALID"

        if order_id is not None and token_order_id != int(order_id):
            return None, "DOCTOR_IDENTITY_ORDER_MISMATCH"

        user = _rb.User.query.get(user_id)

        if not user or not user.active:
            return None, "DOCTOR_IDENTITY_USER_INACTIVE"

        current_role = (
            user.role.code.upper()
            if user.role and user.role.code
            else ""
        )

        token_role = str(payload.get("role") or "").upper()

        if current_role != token_role:
            return None, "DOCTOR_IDENTITY_ROLE_CHANGED"

        linked_order=_rb.db.session.get(_rb.Order,token_order_id)
        if not _rb.doctor_case_access_allowed(user,linked_order):
            return None, "DOCTOR_ASSIGNMENT_REQUIRED"

        return {
            "user": user,
            "payload": payload,
            "role": current_role,
        }, None
    return verify_ohif_doctor_identity


def install_0082(_rb):
    def ohif_audit_user(order_id):
        """Resolve the signed RadBridge OHIF identity for audit attribution."""
        identity, error = _rb.get_ohif_doctor_identity(order_id=order_id)
        if error or not identity:
            return None
        return identity.get('user')
    return ohif_audit_user


def install_0083(_rb):
    def ohif_url_for_order(order):
        uid=_rb.ohif_study_uid(order)

        if not uid:
            return None

        from urllib.parse import quote

        url = (
            f'{_rb.OHIF_PUBLIC_URL}/radbridge'
            f'?StudyInstanceUIDs={quote(uid,safe="")}'
            f'&radbridgeOrderId={order.id}'
        )

        user = _rb.current_user()

        if user and user.active:
            role = (
                user.role.code.upper()
                if user.role and user.role.code
                else ''
            )

            if role in (
                'RADIOLOGIST',
                'CONSULTANT',
                'RADIOLOGY_CONSULTANT',
                'SUPER_ADMIN'
            ):
                secret = (
                    _rb.os.getenv('OHIF_DOCTOR_IDENTITY_SECRET', '').strip()
                    or _rb.app.config.get('SECRET_KEY')
                )

                if secret:
                    token = _rb.create_ohif_doctor_identity(
                        user,
                        order
                    )

                    url += '&radbridgeIdentity=' + quote(token, safe='')

        return url
    return ohif_url_for_order


def install_0105(_rb):
    def dicom_worklist_patient_name(patient):
        """Use the reviewed Latin name or a suggestion, preserving RIS demographics."""
        import unicodedata
        source=str(getattr(patient,'worklist_name','') or getattr(patient,'name','') or '')
        for ch in source:
            if not (ch.isascii() or ch in _rb.ARABIC_NAME_MAP or ch.isspace() or ch=='ـ'
                    or unicodedata.category(ch) in ('Mn','Cf')):
                raise ValueError('Enter a reviewed English Worklist name before sending to the device.')
        name=_rb.patient_worklist_display_name(patient)
        if not name or not _rb.re.search(r'[A-Z]',name):
            raise ValueError('Enter a reviewed English Worklist name before sending to the device.')
        parts=name.split()
        # PN permits five components; retain any further words inside the last one.
        if len(parts)>5:parts=parts[:4]+[' '.join(parts[4:])]
        result='^'.join(parts)
        if len(result)>64:
            raise ValueError('English Worklist name exceeds the DICOM limit of 64 characters. Review it without truncating the patient identity.')
        return result
    return dicom_worklist_patient_name


def install_0106(_rb):
    def dicom_person_name(value):
        value=_rb.re.sub(r'\s+',' ',str(value or '').strip().upper())
        return '^'.join([x for x in value.split(' ') if x])
    return dicom_person_name


def install_0123(_rb):
    def orthanc_ok():
        try: return _rb.requests.get(f'{_rb.ORTHANC}/system',auth=_rb.AUTH,timeout=3).ok
        except Exception: return False
    return orthanc_ok


def install_0126(_rb):
    def send_mwl(order):
        from insurance_policy import assert_approval_ready
        assert_approval_ready(order,runtime=_rb)
        p=order.patient
        patient_name=_rb.dicom_worklist_patient_name(p)
        tags={
            'SpecificCharacterSet':'ISO_IR 192',
            'PatientName':patient_name,
            'PatientID':p.patient_id or '',
            'PatientBirthDate':p.dob or '',
            'PatientSex':p.sex or '',
            'AccessionNumber':order.accession or '',
            'RequestedProcedureDescription':order.procedure or '',
            'RequestedProcedureID':order.accession or '',
            'ScheduledProcedureStepSequence':[{
                'ScheduledStationAETitle':order.station_ae or '',
                'Modality':order.modality or '',
                'ScheduledProcedureStepStartDate':order.scheduled.strftime('%Y%m%d'),
                'ScheduledProcedureStepStartTime':order.scheduled.strftime('%H%M%S'),
                'ScheduledProcedureStepDescription':order.procedure or '',
                'ScheduledProcedureStepID':order.accession or ''
            }]
        }
        r=_rb.requests.post(f'{_rb.ORTHANC}/worklists/create',json={'Tags':tags},auth=_rb.AUTH,timeout=15)
        if not r.ok:
            raise RuntimeError(f'Orthanc MWL HTTP {r.status_code}: {r.text[:1000]}')
        try: return r.json()
        except Exception: return {'ok':True,'text':r.text}
    return send_mwl


def install_0183(_rb):
    def technician_acquisition_notes(rule):
        if not rule:
            return ''
        row=_rb.StudioTemplate.query.filter_by(template_type='TECH_ACQUISITION',name=str(rule.id)).first()
        return row.notes if row else ''
    return technician_acquisition_notes


def install_0330(_rb):
    def safe_dicom_metadata(path):
        try:
            import pydicom
            ds=pydicom.dcmread(path,stop_before_pixels=True,force=True)
            return {
              'patient_name':str(getattr(ds,'PatientName','') or ''),
              'patient_id':str(getattr(ds,'PatientID','') or ''),
              'dob':str(getattr(ds,'PatientBirthDate','') or ''),
              'study_date':str(getattr(ds,'StudyDate','') or ''),
              'modality':str(getattr(ds,'Modality','') or ''),
              'study_description':str(getattr(ds,'StudyDescription','') or ''),
              'study_instance_uid':str(getattr(ds,'StudyInstanceUID','') or '')
            }
        except Exception:
            return {}
    return safe_dicom_metadata


def install_0345(_rb):
    def imaging_ai_provider_for_modality(modality):
        modality=(modality or '').upper()
        rows=_rb.ImagingAIProvider.query.filter_by(enabled=True).order_by(_rb.ImagingAIProvider.id).all()
        for row in rows:
            allowed=[x.strip().upper() for x in (row.modalities or '').split(',') if x.strip()]
            if not allowed or modality in allowed:
                return row
        return None
    return imaging_ai_provider_for_modality


def install_0346(_rb):
    def pacs_study_lookup(order):
        """Return only the study explicitly linked to the RIS order."""
        study_id=str(order.pacs_study_id or '').strip()
        expected_uid=str(order.study_instance_uid or '').strip()
        if not study_id:
            return None,'Order has no authoritative PACS study link'
        try:
            base=(_rb.app.config.get('ORTHANC_URL') or _rb.os.environ.get('ORTHANC_URL') or '').rstrip('/')
            if not base:
                return None,'PACS URL is not configured'
            import requests
            user=_rb.os.environ.get('ORTHANC_USER','');pwd=_rb.os.environ.get('ORTHANC_PASSWORD','')
            auth=(user,pwd) if user else None
            response=requests.get(base+'/studies/'+study_id,auth=auth,timeout=30)
            response.raise_for_status();st=response.json()
            tags=st.get('MainDicomTags') or {};pt=st.get('PatientMainDicomTags') or {}
            actual_uid=str(tags.get('StudyInstanceUID') or '').strip()
            if expected_uid and actual_uid != expected_uid:
                return None,'Authoritative PACS StudyInstanceUID mismatch'
            return {
              'orthanc_study_id':st.get('ID',study_id),'study_instance_uid':actual_uid,
              'accession':tags.get('AccessionNumber',''),'study_date':tags.get('StudyDate',''),
              'study_description':tags.get('StudyDescription',''),
              'modality':tags.get('ModalitiesInStudy') or tags.get('Modality',''),
              'patient_name':pt.get('PatientName',''),'patient_id':pt.get('PatientID',''),
              'patient_birth_date':pt.get('PatientBirthDate',''),'patient_sex':pt.get('PatientSex',''),
            },''
        except Exception as exc:
            return None,'PACS lookup failed: %s' % str(exc)
    return pacs_study_lookup


def install_0350(_rb):
    def build_imaging_ai_request(order,pacs_meta,analysis):
        return {
          'request_type':'RADIOLOGY_IMAGE_ANALYSIS',
          'study':{
            'orthanc_study_id':pacs_meta.get('orthanc_study_id'),
            'study_instance_uid':pacs_meta.get('study_instance_uid'),
            'accession':order.accession,
            'modality':order.modality,
            'procedure':order.procedure
          },
          'patient_context':{
            'age_or_dob':str(order.patient.dob or ''),
            'sex':order.patient.sex or '',
          },
          'constraints':{
            'draft_only':True,
            'no_final_diagnosis':True,
            'return_structured_findings':True,
            'include_uncertainty':True
          }
        }
    return build_imaging_ai_request


def install_0351(_rb):
    def call_imaging_ai(order,pacs_meta,analysis):
        provider=_rb.imaging_ai_provider_for_modality(order.modality)
        if not provider:
            return None,'No Imaging AI provider enabled for modality'
        token=_rb.os.environ.get(provider.secret_env_name or 'RIS_IMAGING_AI_TOKEN','')
        headers={'Content-Type':'application/json'}
        if token: headers['Authorization']='Bearer '+token
        payload=_rb.build_imaging_ai_request(order,pacs_meta,analysis)
        try:
            import requests
            r=requests.post(provider.base_url.rstrip('/')+'/analyze-study',
                json={'model':provider.model_name,'input':payload},
                headers=headers,timeout=max(30,int(provider.timeout_seconds or 180)))
            r.raise_for_status()
            data=r.json()
            return {
              'structured_findings':data.get('structured_findings') or {},
              'summary':str(data.get('summary') or ''),
              'uncertainty':str(data.get('uncertainty') or ''),
              'raw':data
            },''
        except Exception as e:
            return None,str(e)[:1000]
    return call_imaging_ai


def install_0352(_rb):
    def latest_verified_imaging_analysis(order):
        return _rb.ImagingAIAnalysis.query.filter_by(order_id=order.id,demographic_status='VERIFIED',status='AI_FINDINGS_READY').order_by(_rb.ImagingAIAnalysis.completed_at.desc()).first()
    return latest_verified_imaging_analysis


def install_0372(_rb):
    def pacs_image_count(order):
        count,meta,error,_series=_rb.pacs_readiness_evidence(order)
        return count,meta,error
    return pacs_image_count


def install_0509(_rb):
    def _rb_pacs_health():
        try:
            response = _rb.requests.get(
                _rb.PACS_ORTHANC_URL + '/system',
                auth=_rb._orthanc_auth(),
                timeout=3,
            )

            return {
                'status':
                    'ONLINE'
                    if response.ok
                    else 'DEGRADED',
                'http_status':
                    int(response.status_code),
            }

        except Exception as exc:
            return {
                'status': 'OFFLINE',
                'http_status': None,
                'detail': type(exc).__name__,
            }
    return _rb_pacs_health


def install_0836(_rb):
    def _managed_dicom_modality(node_id):
        key=_rb.modality_key(node_id)
        response=_rb.requests.get(f'{_rb.PACS_ORTHANC_URL}/modalities/{key}',
                              auth=_rb._orthanc_auth(),timeout=10)
        if response.status_code==404:return None
        response.raise_for_status()
        return response.json()
    return _managed_dicom_modality


def install_0837(_rb):
    def _write_managed_dicom_modality(node_id,payload):
        key=_rb.modality_key(node_id)
        url=f'{_rb.PACS_ORTHANC_URL}/modalities/{key}'
        if payload is None:
            _rb.delete_modality(url,_rb._orthanc_auth(),_rb.requests)
            response=None
        else:
            response=_rb.requests.put(url,auth=_rb._orthanc_auth(),json=payload,timeout=10)
        if response is not None:response.raise_for_status()
        actual=_rb._managed_dicom_modality(node_id)
        if payload is None and actual is not None:
            raise RuntimeError('Orthanc did not remove the modality')
        if payload is not None and (actual is None or
                any(actual.get(k)!=v for k,v in payload.items())):
            raise RuntimeError('Orthanc did not retain the requested modality policy')
    return _write_managed_dicom_modality


def install_0843(_rb):
    def capture_external_pacs_studies():
        """Mirror eligible PACS inbox rows into the isolated external intake.

    This function never creates an Order, offer or assignment. An exact,
    enabled source AE mapping is mandatory; unknown sources remain untouched.
    """
        setting=_rb.external_reporting_setting()
        if not setting.enabled:
            return 0
        created=0
        centers={
            row.ae_title.strip().upper():row
            for row in _rb.ExternalReportingCenter.query.filter_by(active=True,receiving_enabled=True).all()
        }
        # RB_EXTERNAL_INTAKE_REMOTE_AET_DISCOVERY_V1
        # Scan Orthanc here instead of requiring the internal auto-intake job to
        # populate PacsStudyInbox first. Only exact known external AEs are mirrored;
        # unknown sources remain untouched and no Patient/Order is ever created.
        for study in _rb._orthanc_recent_studies(500):
            tags=_rb._study_tags_extended(study)
            study_id=str(tags.get('study_id') or '').strip()
            source_ae=str(tags.get('source_ae') or '').strip().upper()
            center=centers.get(source_ae)
            if not study_id or not center:
                continue
            inbox=_rb.PacsStudyInbox.query.filter_by(orthanc_study_id=study_id).first()
            if not inbox:
                inbox=_rb.PacsStudyInbox(
                    orthanc_study_id=study_id,
                    study_instance_uid=(tags.get('study_instance_uid') or None),
                    pacs_patient_id=tags.get('patient_id',''),
                    pacs_patient_name=tags.get('patient_name',''),
                    accession=tags.get('accession',''),
                    modality=tags.get('modality',''),
                    study_description=tags.get('study_description',''),
                    source_ae=source_ae,
                    image_count=int(tags.get('instances') or 0),
                    state='EXTERNAL_INTAKE'
                )
                _rb.db.session.add(inbox);_rb.db.session.flush()
            else:
                inbox.source_ae=source_ae
                inbox.last_seen_at=_rb.datetime.utcnow()
                inbox.image_count=int(tags.get('instances') or inbox.image_count or 0)
            if inbox.order_id is not None:
                continue
            intake=_rb.ExternalIntakeCase.query.filter_by(inbox_id=inbox.id).first()
            if not intake:
                intake=_rb.ExternalIntakeCase(
                    center_id=center.id,inbox_id=inbox.id,status='RECEIVED'
                )
                _rb.db.session.add(intake);_rb.db.session.flush()
                created+=1
            _rb.external_intake_autofill(intake,tags)
            inbox.state='EXTERNAL_INTAKE'

        # Preserve capture of eligible inbox rows created by older discovery jobs.
        for inbox in _rb.PacsStudyInbox.query.filter(_rb.PacsStudyInbox.order_id.is_(None)).all():
            center=centers.get(str(inbox.source_ae or '').strip().upper())
            if not center or _rb.ExternalIntakeCase.query.filter_by(inbox_id=inbox.id).first():
                continue
            intake=_rb.ExternalIntakeCase(center_id=center.id,inbox_id=inbox.id,status='RECEIVED')
            _rb.db.session.add(intake);_rb.db.session.flush()
            _rb.external_intake_autofill(intake)
            created+=1
        return created
    return capture_external_pacs_studies


def install_0844(_rb):
    def external_intake_dicom_demographics(row):
        """Read the authoritative patient/study identity from linked Orthanc data."""
        study_id=str(row.inbox.orthanc_study_id or '').strip()
        if not study_id:
            return {},'ORTHANC_STUDY_ID_MISSING'
        try:
            response=_rb.requests.get(
                f'{_rb.PACS_ORTHANC_URL}/studies/{study_id}',
                auth=_rb._orthanc_auth(),timeout=15
            )
            response.raise_for_status()
            study=response.json() or {}
            patient=study.get('PatientMainDicomTags') or {}
            tags=study.get('MainDicomTags') or {}
            return {
                'patient_id':str(patient.get('PatientID') or '').strip(),
                'patient_name':str(patient.get('PatientName') or '').strip(),
                'dob':_rb.normalize_date(patient.get('PatientBirthDate')),
                'sex':str(patient.get('PatientSex') or '').strip().upper()[:1],
                'accession':str(tags.get('AccessionNumber') or row.inbox.accession or '').strip(),
            },''
        except Exception as exc:
            return {},'ORTHANC_DEMOGRAPHICS_FAILED: '+str(exc)[:300]
    return external_intake_dicom_demographics
