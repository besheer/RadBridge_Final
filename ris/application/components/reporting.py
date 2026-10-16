"""Runtime-bound application.components.reporting; dependencies are supplied at composition.

Legacy behavior is preserved; new policies belong in the independent domain layer.
"""

def install_0071(_rb):
    def report_filename(order, version_no=1, status='DRAFT', ext='docx'):
        patient_token=_rb._safe_token(order.patient.patient_id if order and order.patient else 'PATIENT')
        accession_token=_rb._safe_token(order.accession if order else 'ACC')
        status_token=_rb._safe_token(status).upper()
        return f'{patient_token}_{accession_token}_v{int(version_no):03d}_{status_token}.{ext.lstrip(".")}'
    return report_filename


def install_0072(_rb):
    def latest_final_report(order_id):
        report=_rb.Report.query.filter_by(order_id=order_id).first()
        if not report or report.status!='FINAL':
            return None
        return report
    return latest_final_report


def install_0086(_rb):
    def _safe_report_token(value):
        value=str(value or '').strip()
        value=_rb.re.sub(r'[^A-Za-z0-9_-]+','_',value)
        return value.strip('_') or 'NA'
    return _safe_report_token


def install_0087(_rb):
    def _next_report_version(report):
        last=_rb.ReportVersion.query.filter_by(report_id=report.id).order_by(_rb.ReportVersion.version_no.desc()).first()
        return (last.version_no + 1) if last else 1
    return _next_report_version


def install_0088(_rb):
    def build_report_filename(order, version_no, status, ext):
        return (
            f'{_rb._safe_report_token(order.patient.patient_id)}_'
            f'{_rb._safe_report_token(order.accession)}_'
            f'v{int(version_no):03d}_{str(status).upper()}.{str(ext).lstrip(".")}'
        )
    return build_report_filename


def install_0090(_rb):
    def allowed_report_transitions(report):
        s=(report.status or 'DRAFT').upper()
        if s == 'FINAL':
            # FINAL clinical lifecycle is immutable.
            # Addendum is disabled until the dedicated
            # amendment workflow is implemented.
            return []
        if s in ('READY_FORMATTING','FORMATTING'):
            return ['FORMATTING','READY_APPROVAL','DRAFT']
        if s=='READY_APPROVAL':
            return ['DRAFT','VERIFIED','SECOND_VERIFIED','FINAL']
        return ['DRAFT','PARTIAL','READY_FORMATTING','VERIFIED','SECOND_VERIFIED','FINAL']
    return allowed_report_transitions


def install_0091(_rb):
    def report_transition_allowed(report,target):
        return target in _rb.allowed_report_transitions(report)
    return report_transition_allowed


def install_0092(_rb):
    def extract_report_text(path, ext):
        ext=(ext or '').lower()
        try:
            if ext=='.docx':
                with _rb.zipfile.ZipFile(path) as z:
                    parts=[]
                    for name in z.namelist():
                        if name in ('word/document.xml','word/header1.xml','word/header2.xml','word/header3.xml'):
                            xml=z.read(name).decode('utf-8','ignore')
                            parts.append(_rb.re.sub(r'<[^>]+>',' ',xml))
                    return _rb.re.sub(r'\s+',' ',' '.join(parts)).strip()

            if ext=='.odt':
                with _rb.zipfile.ZipFile(path) as z:
                    xml=z.read('content.xml').decode('utf-8','ignore')
                    return _rb.re.sub(r'\s+',' ',_rb.re.sub(r'<[^>]+>',' ',xml)).strip()

            if ext=='.pdf':
                reader=_rb.PdfReader(path)
                text=' '.join((page.extract_text() or '') for page in reader.pages)
                return _rb.re.sub(r'\s+',' ',text).strip()

            # Legacy .doc is binary and cannot be reliably parsed here.
            return ''
        except Exception:
            return ''
    return extract_report_text


def install_0095(_rb):
    def validate_report_patient_file(order, path, ext):
        text=_rb.extract_report_text(path,ext)
        expected_pid=str(order.patient.patient_id or '').strip()
        expected_acc=str(order.accession or '').strip()
        expected_name=str(order.patient.name or '').strip()
        expected_worklist=str(getattr(order.patient,'worklist_name','') or '').strip()

        found_pid=_rb.detect_labeled_value(text,[r'Patient\s*ID',r'Patient\s*No',r'MRN',r'PID'])
        found_acc=_rb.detect_labeled_value(text,[r'Accession(?:\s*No|\s*Number)?',r'Accession'])

        found_name=''
        if text:
            for pattern in [
                r'Patient\s*Name\s*[:#\-]?\s*([A-Za-z\u0600-\u06FF][A-Za-z\u0600-\u06FF ._-]{2,80}?)(?=\s+(?:Patient\s*ID|MRN|PID|Accession|DOB|Sex|Modality|Study)\b|$)',
                r'Name\s*[:#\-]?\s*([A-Za-z\u0600-\u06FF][A-Za-z\u0600-\u06FF ._-]{2,80}?)(?=\s+(?:Patient\s*ID|MRN|PID|Accession|DOB|Sex|Modality|Study)\b|$)'
            ]:
                mm=_rb.re.search(pattern,text,flags=_rb.re.I)
                if mm:
                    found_name=mm.group(1).strip()
                    break

        npid=_rb._normalize_compare(expected_pid)
        nacc=_rb._normalize_compare(expected_acc)
        ntext=_rb._normalize_compare(text)
        pid_match=bool(npid and npid in ntext)
        acc_match=bool(nacc and nacc in ntext)

        explicit_pid_mismatch=bool(found_pid and _rb._normalize_compare(found_pid)!=npid)
        explicit_acc_mismatch=bool(found_acc and _rb._normalize_compare(found_acc)!=nacc)

        expected_names={
            _rb.normalized_person_name(expected_name),
            _rb.normalized_person_name(expected_worklist),
            _rb.normalized_person_name(_rb.arabic_to_latin_name(expected_name)),
        }
        expected_names={x for x in expected_names if x}
        found_name_norm=_rb.normalized_person_name(found_name)
        name_match=(not found_name_norm) or (found_name_norm in expected_names)
        explicit_name_mismatch=bool(found_name_norm and not name_match)

        common={
            'expected_patient_name':expected_name,
            'found_patient_name':found_name,
            'expected_patient_id':expected_pid,
            'found_patient_id':found_pid,
            'expected_accession':expected_acc,
            'found_accession':found_acc,
            'name_match':name_match,
        }

        if explicit_pid_mismatch or explicit_acc_mismatch:
            common.update(result='BLOCKED',reason='Patient ID or Accession does not match the open case.')
            return common

        if explicit_name_mismatch and pid_match and acc_match:
            common.update(result='WARNING',reason='Patient ID and Accession match, but Patient Name differs. Review spelling/transliteration.')
            return common

        if pid_match and acc_match and name_match:
            common.update(result='MATCH',reason='Patient Name, Patient ID and Accession are consistent with the open case.')
            return common

        common.update(result='WARNING',reason='Not enough readable identifiers to confirm Patient Name, Patient ID and Accession.')
        return common
    return validate_report_patient_file


def install_0127(_rb):
    def get_report(order):
        if not order.report:
            r=_rb.Report(order=order); _rb.db.session.add(r); _rb.db.session.commit()
        return order.report
    return get_report


def install_0128(_rb):
    def report_history(report):
        return _rb.ReportVersion.query.filter_by(report_id=report.id).order_by(_rb.ReportVersion.version_no.desc()).all()
    return report_history


def install_0219(_rb):
    def _reporting_serializer():
        return _rb.URLSafeTimedSerializer(_rb.app.secret_key, salt='radbridge-reporting-case-v5442')
    return _reporting_serializer


def install_0220(_rb):
    def reporting_case_token(accession):
        """Create a short-lived, accession-scoped token for the desktop reporting agent."""
        user = _rb.current_user()
        if not user or not user.active or not _rb.has_perm('reports.view'):
            return ''
        return _rb._reporting_serializer().dumps({
            'accession': str(accession or ''),
            'user_id': user.id,
            'can_edit': bool(_rb.has_perm('reports.edit')),
        })
    return reporting_case_token


def install_0221(_rb):
    def _valid_reporting_case_token(token, accession, write=False):
        if not token:
            return False
        try:
            data = _rb._reporting_serializer().loads(
                token,
                max_age=max(60, _rb.REPORTING_CASE_TOKEN_TTL_SECONDS)
            )
        except (_rb.BadSignature, _rb.SignatureExpired, ValueError, TypeError):
            return False
        if str(data.get('accession') or '') != str(accession or ''):
            return False
        if write and not bool(data.get('can_edit')):
            return False
        return True
    return _valid_reporting_case_token


def install_0227(_rb):
    def word_addin_taskpane_js():
        return _rb.app.send_static_file(
            'word-addin/taskpane.js'
        )
    return word_addin_taskpane_js


def install_0246(_rb):
    def user_reporting_preferences(profile):
        settings=_rb.user_profile_settings(profile)
        reporting=settings.get('reporting') or {}
        if not isinstance(reporting,dict):
            reporting={}

        editor=str(
            reporting.get('preferred_editor') or 'ONLYOFFICE'
        ).upper()

        layout=str(
            reporting.get('preferred_layout') or '50_50'
        ).upper()

        allowed_editors={
            'ONLYOFFICE',
            'BROWSER',
            'WORD',
            'LIBREOFFICE',
            'ASK'
        }

        allowed_layouts={
            '50_50',
            '70_30',
            '30_70',
            'FULL_EDITOR',
            'FULL_VIEWER',
            'DUAL_MONITOR',
            'CASCADE',
            'NEW_WINDOW'
        }

        if editor not in allowed_editors:
            editor='ONLYOFFICE'

        if layout not in allowed_layouts:
            layout='50_50'

        display=str(reporting.get('preferred_display') or 'CURRENT').upper()
        if display not in {'CURRENT','OTHER'}:
            display='CURRENT'
        return {
            'preferred_editor':editor,
            'preferred_layout':layout,
            'preferred_display':display
        }
    return user_reporting_preferences


def install_0247(_rb):
    def set_user_reporting_preferences(
        profile,
        preferred_editor,
        preferred_layout,
        preferred_display=None
    ):
        settings=_rb.user_profile_settings(profile)

        reporting=settings.get('reporting')

        if not isinstance(reporting,dict):
            reporting={}

        editor=str(
            preferred_editor or 'ONLYOFFICE'
        ).upper()

        layout=str(
            preferred_layout or '50_50'
        ).upper()

        allowed_editors={
            'ONLYOFFICE',
            'BROWSER',
            'WORD',
            'LIBREOFFICE',
            'ASK'
        }

        allowed_layouts={
            '50_50',
            '70_30',
            '30_70',
            'FULL_EDITOR',
            'FULL_VIEWER',
            'DUAL_MONITOR',
            'CASCADE',
            'NEW_WINDOW'
        }

        if editor not in allowed_editors:
            editor='ONLYOFFICE'

        if layout not in allowed_layouts:
            layout='50_50'

        display=str(preferred_display if preferred_display is not None else reporting.get('preferred_display') or 'CURRENT').upper()
        if display not in {'CURRENT','OTHER'}:
            display='CURRENT'
        reporting['preferred_display']=display
        reporting['preferred_editor']=editor
        reporting['preferred_layout']=layout

        settings['reporting']=reporting

        profile.settings_json=_rb.json.dumps(
            settings,
            separators=(',',':')
        )

        return {
            'preferred_editor':editor,
            'preferred_layout':layout,
            'preferred_display':display
        }
    return set_user_reporting_preferences


def install_0386(_rb):
    def assignment_report_rows(limit=1000):
        orders=_rb.Order.query.order_by(_rb.Order.id.desc()).limit(limit).all()
        out=[]
        for o in orders:
            ca=(
                _rb.CaseAssignment.query
                .filter_by(order_id=o.id,active=True)
                .order_by(_rb.CaseAssignment.assigned_at.desc(),_rb.CaseAssignment.id.desc())
                .first()
            )
            offers=_rb.AssignmentOffer.query.filter_by(order_id=o.id).order_by(_rb.AssignmentOffer.attempt_no).all()
            rd=__import__('reception_readiness').view(o,_rb.CaseReadiness.query.filter_by(order_id=o.id).first())
            tat=_rb.case_delay_snapshot(o)
            rp=_rb.Report.query.filter_by(order_id=o.id).order_by(_rb.Report.id.desc()).first()
            return_state=_rb.case_return_snapshot(o.id)
            last_offer_status=offers[-1].status if offers else ''

            # An open doctor return is active operational work even when an
            # earlier report version is FINAL. It must remain visible to the
            # branch/technician until READY_FOR_REREVIEW or RESOLVED.
            if return_state['open']:
                process_state='RETURNED'
                process_owner=return_state['owner'] or tat['owner']
            elif rp and str(rp.status or '').upper()=='FINAL':
                process_state='FINALIZED'
                process_owner='COMPLETE'
            elif rd and rd.status=='BLOCKED':
                process_state='BLOCKED'
                process_owner=tat['owner']
            elif last_offer_status=='PENDING':
                process_state='PENDING_OFFER'
                process_owner='ASSIGNMENT'
            elif ca:
                process_state='ASSIGNED'
                process_owner='DOCTOR'
            elif rd and rd.status=='READY':
                process_state='READY_UNASSIGNED'
                process_owner='ASSIGNMENT'
            else:
                process_state='WAITING_READINESS'
                process_owner=tat['owner']

            out.append({
              'order':o,'assignment':ca,'offers':offers,'readiness':rd,
              'tat':tat,'report':rp,'offer_attempts':len(offers),
              'last_offer_status':last_offer_status,
              'process_state':process_state,
              'process_owner':process_owner,
              'return_open':return_state['open'],
              'return_event':return_state['return_event'],
              'return_reason':return_state['reason']
            })
        return out
    return assignment_report_rows


def install_0529(_rb):
    def create_reporting_demo_cases():
        specs=[
            ('DEMO001','Ahmed Hassan Demo','M','1985-05-12','CT','CT-BRAIN-NC','DRAFT'),
            ('DEMO002','Mona Ali Demo','F','1992-11-03','MR','MR-LSPINE-NC','PARTIAL'),
            ('DEMO003','Omar Mahmoud Demo','M','1978-02-20','US','US-ABD','VERIFIED'),
            ('DEMO004','Sara Ibrahim Demo','F','1988-08-14','MR','MR-BRAIN-NC','SECOND_VERIFIED'),
            ('DEMO005','Youssef Adel Demo','M','1969-01-05','CT','CT-CHEST-C','FINAL'),
            ('DEMO006','Nour Sameh Demo','F','1995-09-30','DX','XR-CHEST-PA-LAT','ADDENDUM'),
        ]
        branch=_rb.Branch.query.first()
        created=[]
        for pid,name,sex,dob,modality,proc_code,status in specs:
            patient=_rb.Patient.query.filter_by(patient_id=pid).first()
            if not patient:
                patient=_rb.Patient(patient_id=pid,name=name,sex=sex,dob=_rb.datetime.strptime(dob,'%Y-%m-%d').date(),
                                phone='01000000000',national_id='DEMO-'+pid,address='Demo Patient')
                _rb.db.session.add(patient); _rb.db.session.flush()
            proc=_rb.Procedure.query.filter_by(code=proc_code).first() or _rb.Procedure.query.filter_by(modality=modality).first()
            if not proc:
                continue
            existing=_rb.Order.query.filter_by(patient_id=patient.id,procedure_id=proc.id).first()
            if existing:
                created.append(existing); continue
            device=_rb.route_device(branch.id,proc.modality) if branch else None
            order=_rb.Order(accession='DEMO-'+pid,patient_id=patient.id,procedure_id=proc.id,
                        branch_id=branch.id if branch else None,device_id=device.id if device else None,
                        modality=proc.modality,procedure=proc.name,station_ae=device.ae_title if device else '',
                        scheduled=_rb.datetime.utcnow(),status='FINAL' if status=='FINAL' else 'REPORTING',
                        gross_price=float(proc.base_price or 0),contract_price=float(proc.base_price or 0),
                        patient_share=float(proc.base_price or 0),company_share=0,paid_amount=0,
                        created_by=_rb.current_user().id if _rb.current_user() else None)
            _rb.db.session.add(order); _rb.db.session.flush()
            report=_rb.Report(order_id=order.id,accession=order.accession,status=status,radiologist='Dr. Demo',
                          findings=f'Demo findings for {proc.name}.',impression=f'Demo impression for {proc.name}.')
            if status in ('VERIFIED','SECOND_VERIFIED','FINAL'):
                report.verified_by='Dr. Demo Verifier'; report.verified_at=_rb.datetime.utcnow()
            if status in ('SECOND_VERIFIED','FINAL'):
                report.second_verified_by='Dr. Demo Second Verifier'; report.second_verified_at=_rb.datetime.utcnow()
            if status=='FINAL':
                report.finalized_by='Dr. Demo Finalizer'; report.finalized_at=_rb.datetime.utcnow()
            if status=='ADDENDUM':
                report.addendum_no=1
            _rb.db.session.add(report); _rb.db.session.flush()
            _rb.db.session.add(_rb.ReportVersion(report_id=report.id,accession=order.accession,version_no=1,
                                         action='DEMO_'+status,findings=report.findings,
                                         impression=report.impression,radiologist=report.radiologist))
            created.append(order)
        _rb.db.session.commit()
        return created
    return create_reporting_demo_cases


def install_0582(_rb):
    def granular_delete_reports_only_preview_snapshot(order, patient, reports):
        """Read-only dependency preflight for Delete Reports Only."""
        from datetime import datetime as _preview_datetime
        from pathlib import Path as _PreviewPath
        from sqlalchemy import inspect as _sa_inspect, text as _sa_text

        report_ids=[int(row.id) for row in reports]
        version_rows=[]
        coordinator_rows=[]
        artifacts=[]
        blockers=[]
        warnings=[]

        if report_ids:
            version_rows=(
                _rb.ReportVersion.query
                .filter(_rb.ReportVersion.report_id.in_(report_ids))
                .order_by(_rb.ReportVersion.report_id,_rb.ReportVersion.version_no)
                .all()
            )
            coordinator_rows=(
                _rb.CoordinatorTask.query
                .filter(_rb.CoordinatorTask.report_id.in_(report_ids))
                .order_by(_rb.CoordinatorTask.id)
                .all()
            )

        report_identity_mismatch=False
        version_identity_mismatch=False

        for report in reports:
            if int(getattr(report,'order_id',0) or 0) != int(order.id):
                report_identity_mismatch=True

        expected_accession=str(getattr(order,'accession','') or '').strip()
        for version in version_rows:
            version_accession=str(getattr(version,'accession','') or '').strip()
            if expected_accession and version_accession != expected_accession:
                version_identity_mismatch=True

        if report_identity_mismatch:
            blockers.append('Report/order identity mismatch.')
        if version_identity_mismatch:
            blockers.append('ReportVersion accession does not match the selected Order.')
        if coordinator_rows:
            blockers.append('CoordinatorTask references the report; Reports Only deletion is blocked.')

        lease_rows=[]
        lease_table_present=False
        try:
            inspector=_sa_inspect(_rb.db.engine)
            lease_table_present=inspector.has_table('report_edit_lease')
            if lease_table_present and report_ids:
                placeholders=','.join(str(int(value)) for value in report_ids)
                lease_rows=_rb.db.session.execute(
                    _sa_text(
                        'SELECT id,order_id,report_id,user_id,editor_type,expires_at '
                        'FROM report_edit_lease '
                        'WHERE order_id = :order_id OR report_id IN ('+placeholders+')'
                    ),
                    {'order_id':int(order.id)},
                ).mappings().all()
        except Exception as exc:
            blockers.append('Report edit lease state could not be verified.')
            warnings.append(type(exc).__name__)

        now=_preview_datetime.utcnow()
        active_lease_count=0
        expired_lease_count=0
        lease_preview=[]
        for row in lease_rows:
            expires_at=row.get('expires_at')
            compare_expiry=expires_at

            # Raw SQL returns native datetimes on PostgreSQL, but SQLite-backed
            # isolated tests may return DATETIME values as ISO strings. Normalize
            # both forms without mutating lease state. Fail closed when an expiry
            # cannot be interpreted safely.
            if isinstance(compare_expiry,str):
                raw_expiry=compare_expiry.strip()
                if raw_expiry.endswith('Z'):
                    raw_expiry=raw_expiry[:-1] + '+00:00'
                try:
                    compare_expiry=_preview_datetime.fromisoformat(raw_expiry)
                except ValueError:
                    compare_expiry=None
                    blockers.append('Report edit lease expiry could not be interpreted.')

            if compare_expiry is not None and getattr(compare_expiry,'tzinfo',None) is not None:
                compare_expiry=compare_expiry.astimezone(
                    __import__('datetime').timezone.utc
                ).replace(tzinfo=None)

            active=bool(compare_expiry is not None and compare_expiry > now)
            if active:
                active_lease_count += 1
            elif compare_expiry is not None:
                expired_lease_count += 1
            lease_preview.append({
                'id':row.get('id'),
                'order_id':row.get('order_id'),
                'report_id':row.get('report_id'),
                'user_id':row.get('user_id'),
                'editor_type':row.get('editor_type'),
                'expires_at':expires_at,
                'active':active,
            })

        if active_lease_count:
            blockers.append('Active report edit lease exists.')
        if expired_lease_count:
            warnings.append('Expired report edit lease requires cleanup during execution preflight.')

        if report_ids and not lease_table_present:
            blockers.append('report_edit_lease table is unavailable; lease safety cannot be verified.')

        case_root=None
        case_root_error=None
        try:
            from report_storage_safety import canonical_case_paths
            case_root=_PreviewPath(
                canonical_case_paths(_rb.REPORT_DIR,patient,order)['case_root']
            ).resolve()
        except Exception as exc:
            case_root_error=type(exc).__name__
            blockers.append('Canonical report case root could not be resolved.')

        seen_paths=set()
        path_sources=[]
        for report in reports:
            for field in ('source_path','docx_path','pdf_path'):
                value=str(getattr(report,field,None) or '').strip()
                if value:
                    path_sources.append(('REPORT',report.id,None,field,value))
        for version in version_rows:
            for field in ('source_path','docx_path','pdf_path'):
                value=str(getattr(version,field,None) or '').strip()
                if value:
                    path_sources.append(('REPORT_VERSION',version.report_id,version.id,field,value))

        unsafe_path_count=0
        missing_artifact_count=0
        for owner_type,report_id,version_id,field,value in path_sources:
            try:
                resolved=_PreviewPath(value).expanduser().resolve()
                path_key=str(resolved)
            except Exception:
                resolved=None
                path_key=value

            if path_key in seen_paths:
                continue
            seen_paths.add(path_key)

            inside_case_root=False
            if resolved is not None and case_root is not None:
                try:
                    resolved.relative_to(case_root)
                    inside_case_root=True
                except ValueError:
                    inside_case_root=False

            exists=bool(resolved is not None and resolved.exists())
            if not inside_case_root:
                unsafe_path_count += 1
            if not exists:
                missing_artifact_count += 1

            artifacts.append({
                'path':path_key,
                'owner_type':owner_type,
                'report_id':report_id,
                'version_id':version_id,
                'field':field,
                'exists':exists,
                'inside_case_root':inside_case_root,
            })

        if unsafe_path_count:
            blockers.append('One or more report artifact paths are outside the canonical case root.')
        if missing_artifact_count:
            warnings.append('One or more referenced report artifacts are missing on disk.')

        if not reports:
            blockers.append('No Report row exists for this Order.')

        blocker_codes=[]
        if report_identity_mismatch:
            blocker_codes.append('REPORT_ORDER_IDENTITY_MISMATCH')
        if version_identity_mismatch:
            blocker_codes.append('REPORT_VERSION_ACCESSION_MISMATCH')
        if coordinator_rows:
            blocker_codes.append('COORDINATOR_TASK_PRESENT')
        if active_lease_count:
            blocker_codes.append('ACTIVE_REPORT_EDIT_LEASE')
        if 'Report edit lease expiry could not be interpreted.' in blockers:
            blocker_codes.append('LEASE_EXPIRY_UNPARSEABLE')
        if report_ids and not lease_table_present:
            blocker_codes.append('LEASE_STATE_UNAVAILABLE')
        if case_root_error:
            blocker_codes.append('REPORT_CASE_ROOT_UNAVAILABLE')
        if unsafe_path_count:
            blocker_codes.append('REPORT_ARTIFACT_OUTSIDE_CASE_ROOT')
        if not reports:
            blocker_codes.append('NO_REPORT')

        return {
            'report_count':len(reports),
            'report_ids':report_ids,
            'version_count':len(version_rows),
            'versions':[
                {
                    'id':row.id,
                    'report_id':row.report_id,
                    'version_no':row.version_no,
                    'accession':row.accession,
                    'status':getattr(row,'status',None),
                    'source_type':getattr(row,'source_type',None),
                }
                for row in version_rows
            ],
            'coordinator_task_count':len(coordinator_rows),
            'coordinator_tasks':[
                {
                    'id':row.id,
                    'report_id':row.report_id,
                    'status':row.status,
                    'assigned_to':row.assigned_to,
                }
                for row in coordinator_rows
            ],
            'lease':{
                'table_present':lease_table_present,
                'active_count':active_lease_count,
                'expired_count':expired_lease_count,
                'rows':lease_preview,
            },
            'storage':{
                'report_root':str(_PreviewPath(_rb.REPORT_DIR).resolve()),
                'case_root':str(case_root) if case_root is not None else None,
                'case_root_error':case_root_error,
                'artifact_count':len(artifacts),
                'unsafe_path_count':unsafe_path_count,
                'missing_artifact_count':missing_artifact_count,
                'artifacts':artifacts,
            },
            'blocker_codes':blocker_codes,
            'blockers':blockers,
            'warnings':warnings,
            'can_delete_reports_only':bool(reports) and not blocker_codes,
            'readonly':True,
        }
    return granular_delete_reports_only_preview_snapshot


def install_0583(_rb):
    def _delete_reports_only_is_super_admin(user):
        return bool(
            user
            and getattr(user, 'role', None)
            and str(getattr(user.role, 'code', '') or '').strip().upper() == 'SUPER_ADMIN'
        )
    return _delete_reports_only_is_super_admin


def install_0584(_rb):
    def _delete_reports_only_quarantine_target(patient, order, operation_id):
        """Return a same-filesystem quarantine target under REPORT_DIR."""
        from pathlib import Path as _DeletePath
        from report_storage_safety import canonical_case_paths, safe_token

        paths=canonical_case_paths(_rb.REPORT_DIR,patient,order)
        report_root=_DeletePath(_rb.REPORT_DIR).resolve()
        quarantine_root=(report_root/'.quarantine'/'reports-only').resolve()
        quarantine_target=(
            quarantine_root
            / safe_token(str(operation_id))
            / safe_token(getattr(patient,'patient_id','PATIENT'))
            / safe_token(getattr(order,'accession','ORDER'))
        ).resolve()

        try:
            quarantine_target.relative_to(report_root)
        except ValueError as exc:
            raise RuntimeError('QUARANTINE_PATH_OUTSIDE_REPORT_ROOT') from exc

        return paths['case_root'].resolve(),quarantine_target
    return _delete_reports_only_quarantine_target


def install_0585(_rb):
    def _delete_reports_only_blocked_response(order, reason, code, blockers, status=409):
        try:
            _rb.audit(
                'REPORTS_ONLY_DELETE_BLOCKED_ADMIN',
                'order',
                order.id,
                (
                    f"accession={getattr(order,'accession','')}; "
                    f"code={code}; "
                    f"blockers={','.join(str(x) for x in (blockers or []))}; "
                    f"reason={reason}"
                ),
            )
            _rb.db.session.commit()
        except Exception:
            _rb.db.session.rollback()

        return {
            'ok':False,
            'deleted':False,
            'error':code,
            'blockers':list(blockers or []),
        },status
    return _delete_reports_only_blocked_response


def install_0716(_rb):
    def report_sla_snapshot(order, report=None, now=None):
        now = now or _rb.datetime.utcnow()

        priority=(order.priority or 'ROUTINE').strip().upper()

        # Unknown priorities safely fall back to ROUTINE.
        target_minutes=_rb.REPORT_SLA_MINUTES.get(
            priority,
            _rb.REPORT_SLA_MINUTES['ROUTINE']
        )

        # SLA starts when examination is completed.
        # Old imported cases may not have exam_completed_at.
        start_at=order.exam_completed_at or order.scheduled

        if not start_at:
            return {
                'priority':priority,
                'target_minutes':target_minutes,
                'elapsed_minutes':None,
                'remaining_minutes':None,
                'percent':0,
                'status':'NOT_STARTED',
                'start_at':None,
                'end_at':None,
            }

        report_status=(
            str(report.status or '').strip().upper()
            if report else ''
        )

        # finalized_at is the authoritative terminal timestamp.  It also covers
        # legacy rows whose status text was not synchronized during finalization.
        is_final=bool(
            report and
            (report_status=='FINAL' or report.finalized_at is not None)
        )

        # Once FINAL, SLA clock stops permanently.
        end_at=(
            report.finalized_at
            if is_final and report.finalized_at
            else now
        )

        elapsed=max(
            0,
            int((end_at-start_at).total_seconds()/60)
        )

        remaining=target_minutes-elapsed

        percent=(
            round((elapsed/target_minutes)*100,1)
            if target_minutes else 0
        )

        if elapsed > target_minutes:
            status='BREACHED'
        elif percent >= _rb.REPORT_SLA_NEAR_PERCENT:
            status='NEAR_SLA'
        else:
            status='ON_TIME'

        return {
            'priority':priority,
            'target_minutes':target_minutes,
            'elapsed_minutes':elapsed,
            'remaining_minutes':remaining,
            'percent':percent,
            'status':status,
            'start_at':start_at,
            'end_at':end_at,
            'is_final':is_final,
        }
    return report_sla_snapshot


def install_0839(_rb):
    def external_reporting_setting():
        row=_rb.ExternalReportingSetting.query.order_by(_rb.ExternalReportingSetting.id).first()
        if not row:
            row=_rb.ExternalReportingSetting(enabled=False)
            _rb.db.session.add(row);_rb.db.session.flush()
        return row
    return external_reporting_setting


def install_0861(_rb):
    def _ohif_report_json(order, report):
        return {
            'ok': True,
            'order': {
                'id': order.id,
                'accession': order.accession,
                'status': order.status,
                'modality': order.modality,
                'procedure': order.procedure,
                'study_instance_uid': _rb.ohif_study_uid(order),
            },
            'patient': {
                'id': order.patient.patient_id if order.patient else '',
                'name': order.patient.name if order.patient else '',
                'dob': str(order.patient.dob or '') if order.patient else '',
                'sex': order.patient.sex if order.patient else '',
            },
            'report': {
                'id': report.id,
                'status': report.status or 'DRAFT',
                'findings': report.findings or '',
                'impression': report.impression or '',
                'radiologist': report.radiologist or '',
                'updated_at': report.updated_at.isoformat() if report.updated_at else None,
                'allowed_transitions': _rb.allowed_report_transitions(report),
            }
        }
    return _ohif_report_json


def install_0866(_rb):
    def _ohif_validate_word_upload(order, document, final=False):
        if not document or not document.filename:
            return None, {
                'ok': False,
                'error': 'DOCUMENT_REQUIRED'
            }, 400

        if not document.filename.lower().endswith('.docx'):
            return None, {
                'ok': False,
                'error': 'DOCX_REQUIRED'
            }, 400

        tmpdir = _rb.tempfile.mkdtemp(prefix='ohif-word-identity-')
        tmppath = _rb.os.path.join(tmpdir, 'report.docx')

        document.save(tmppath)

        doc = _rb.Document(tmppath)
        values = []

        def add_text(value):
            value = str(value or '').strip()
            if value:
                values.append(value)

        # Main body
        for para in doc.paragraphs:
            add_text(para.text)

        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    add_text(cell.text)

        # Header -- RadBridge template stores patient demographics here
        for section in doc.sections:
            header = section.header

            for para in header.paragraphs:
                add_text(para.text)

            for table in header.tables:
                for row in table.rows:
                    for cell in row.cells:
                        add_text(cell.text)

        text_blob = '\n'.join(values)

        expected_pid = str(
            order.patient.patient_id if order.patient else ''
        ).strip()

        expected_acc = str(order.accession or '').strip()

        # --------------------------------------------------------
        # Find RIS Accession
        # --------------------------------------------------------

        found_acc = ''

        m = _rb.re.search(
            r'RIS_ACCESSION\s*:\s*([A-Za-z0-9_.-]+)',
            text_blob,
            _rb.re.I
        )

        if m:
            found_acc = m.group(1).strip()

        if not found_acc:
            for i, value in enumerate(values):

                if _rb.re.fullmatch(
                    r'\s*accession(?:\s+number)?\s*:?\s*',
                    value,
                    _rb.re.I
                ):
                    if i + 1 < len(values):
                        found_acc = values[i + 1].strip()
                        break

                m = _rb.re.match(
                    r'^accession(?:\s+number)?\s*:\s*(.+)$',
                    value,
                    _rb.re.I
                )

                if m:
                    found_acc = m.group(1).strip()
                    break

        # --------------------------------------------------------
        # Find Patient ID
        # --------------------------------------------------------

        found_pid = ''

        for i, value in enumerate(values):

            if _rb.re.fullmatch(
                r'\s*patient\s*id\s*:?\s*',
                value,
                _rb.re.I
            ):
                if i + 1 < len(values):
                    found_pid = values[i + 1].strip()
                    break

            m = _rb.re.match(
                r'^patient\s*id\s*:\s*(.+)$',
                value,
                _rb.re.I
            )

            if m:
                found_pid = m.group(1).strip()
                break

        # --------------------------------------------------------
        # STRICT DECISION
        # --------------------------------------------------------

        if not found_pid or not found_acc:
            result = 'IDENTITY_NOT_FOUND'

        elif found_pid != expected_pid:
            result = 'PATIENT_ID_MISMATCH'

        elif found_acc != expected_acc:
            result = 'ACCESSION_MISMATCH'

        else:
            result = 'MATCH'

        safety = {
            'result': result,
            'expected_patient_id': expected_pid,
            'found_patient_id': found_pid,
            'expected_accession': expected_acc,
            'found_accession': found_acc,
        }

        _rb.audit(
            'REPORT_PATIENT_SAFETY',
            'order',
            order.id,
            (
                f"OHIF_WORD result={result} "
                f"expected_pid={expected_pid} "
                f"found_pid={found_pid} "
                f"expected_acc={expected_acc} "
                f"found_acc={found_acc}"
            )
        )

        _rb.db.session.commit()

        # HARD BLOCK FOR BOTH DRAFT AND FINAL
        if result != 'MATCH':
            return None, {
                'ok': False,
                'error': 'WORD_PATIENT_IDENTITY_MISMATCH',
                'reason': result,
                'safety': safety,
                'message': (
                    'Upload blocked: Patient ID and Accession '
                    'inside this Word document do not match '
                    'the currently opened RIS case.'
                )
            }, 409

        return tmppath, {
            'ok': True,
            'safety': safety
        }, 200
    return _ohif_validate_word_upload


def install_0877(_rb):
    def _onlyoffice_serializer():
        return _rb.URLSafeTimedSerializer(
            _rb.app.secret_key,
            salt='radbridge-onlyoffice-v1'
        )
    return _onlyoffice_serializer


def install_0878(_rb):
    def _onlyoffice_link_token(order_id, purpose):
        return _rb._onlyoffice_serializer().dumps({
            'order_id': int(order_id),
            'purpose': str(purpose)
        })
    return _onlyoffice_link_token


def install_0879(_rb):
    def _onlyoffice_check_link_token(token, order_id, purpose):
        if not token:
            return False

        try:
            data = _rb._onlyoffice_serializer().loads(
                token,
                max_age=max(60, _rb.ONLYOFFICE_LINK_TTL)
            )
        except Exception:
            return False

        return (
            int(data.get('order_id', -1)) == int(order_id)
            and str(data.get('purpose') or '') == str(purpose)
        )
    return _onlyoffice_check_link_token


def install_0880(_rb):
    def _onlyoffice_b64url(raw):
        import base64
        return (
            base64.urlsafe_b64encode(raw)
            .decode('ascii')
            .rstrip('=')
        )
    return _onlyoffice_b64url


def install_0881(_rb):
    def _onlyoffice_jwt_encode(payload):
        import json
        import hashlib

        if not _rb.ONLYOFFICE_JWT_SECRET:
            raise RuntimeError('ONLYOFFICE_JWT_SECRET is not configured')

        header = {
            'alg': 'HS256',
            'typ': 'JWT'
        }

        h = _rb._onlyoffice_b64url(
            json.dumps(
                header,
                separators=(',', ':')
            ).encode()
        )

        b = _rb._onlyoffice_b64url(
            json.dumps(
                payload,
                separators=(',', ':'),
                default=str
            ).encode()
        )

        signing_input = f'{h}.{b}'.encode()

        sig = _rb.hmac.new(
            _rb.ONLYOFFICE_JWT_SECRET.encode(),
            signing_input,
            hashlib.sha256
        ).digest()

        return f'{h}.{b}.{_rb._onlyoffice_b64url(sig)}'
    return _onlyoffice_jwt_encode


def install_0882(_rb):
    def _onlyoffice_jwt_valid(token):
        import base64
        import hashlib

        if not token or not _rb.ONLYOFFICE_JWT_SECRET:
            return False

        try:
            parts = token.split('.')
            if len(parts) != 3:
                return False

            signing_input = f'{parts[0]}.{parts[1]}'.encode()

            expected = _rb.hmac.new(
                _rb.ONLYOFFICE_JWT_SECRET.encode(),
                signing_input,
                hashlib.sha256
            ).digest()

            pad = '=' * (-len(parts[2]) % 4)

            supplied = base64.urlsafe_b64decode(
                parts[2] + pad
            )

            return _rb.hmac.compare_digest(
                supplied,
                expected
            )
        except Exception:
            return False
    return _onlyoffice_jwt_valid


def install_0883(_rb):
    def _onlyoffice_working_dir():
        path = _rb.os.path.join(
            _rb.REPORT_DIR,
            '_onlyoffice_working'
        )
        _rb.os.makedirs(path, exist_ok=True)
        return path
    return _onlyoffice_working_dir


def install_0884(_rb):
    def _onlyoffice_working_path(order):
        safe_acc = _rb.re.sub(
            r'[^A-Za-z0-9_.-]+',
            '_',
            str(order.accession or order.id)
        )

        return _rb.os.path.join(
            _rb._onlyoffice_working_dir(),
            f'{safe_acc}.docx'
        )
    return _onlyoffice_working_path


def install_0885(_rb):
    def _onlyoffice_prepare_document(order, report):
        path = _rb._onlyoffice_working_path(order)

        if _rb.os.path.exists(path):
            return path

        # Patient-safety boundary:
        # Never reconstruct a missing ONLYOFFICE working document from a
        # previously committed clinical artifact.  Existing reports must fail
        # closed and require an explicit doctor-controlled action.
        existing_version = (
            _rb.ReportVersion.query
            .filter_by(report_id=report.id)
            .order_by(_rb.ReportVersion.version_no.desc())
            .first()
        )

        if existing_version is not None:
            raise ValueError('ONLYOFFICE_WORKING_COPY_NOT_FOUND')

        # First document for a report with no committed versions.
        buf = _rb.make_docx(order, report)

        with open(path, 'wb') as fh:
            fh.write(buf.getvalue())

        return path
    return _onlyoffice_prepare_document


def install_0889(_rb):
    def _onlyoffice_forcesave_ack_path(order_id):
        return _rb.os.path.join(
            _rb._onlyoffice_working_dir(),
            f'order-{int(order_id)}.forcesave-ack'
        )
    return _onlyoffice_forcesave_ack_path


def install_0890(_rb):
    def _onlyoffice_write_forcesave_ack(order_id, nonce):
        nonce = str(nonce or '').strip()

        if not nonce:
            return

        path = _rb._onlyoffice_forcesave_ack_path(order_id)
        tmp = path + '.tmp'

        with open(tmp, 'w', encoding='utf-8') as fh:
            fh.write(nonce)

        _rb.os.replace(tmp, path)
    return _onlyoffice_write_forcesave_ack


def install_0891(_rb):
    def _onlyoffice_read_forcesave_ack(order_id):
        path = _rb._onlyoffice_forcesave_ack_path(order_id)

        try:
            with open(path, 'r', encoding='utf-8') as fh:
                return fh.read().strip()
        except FileNotFoundError:
            return ''
    return _onlyoffice_read_forcesave_ack


def install_0894(_rb):
    def _rb_latest_report_version(report):
        return (
            _rb.ReportVersion.query
            .filter_by(report_id=report.id)
            .order_by(_rb.ReportVersion.version_no.desc())
            .first()
        )
    return _rb_latest_report_version


def install_0897(_rb):
    def _rb_onlyoffice_working_bytes(order):
        path = _rb._onlyoffice_working_path(order)

        if not path or not _rb.os.path.isfile(path):
            raise ValueError('ONLYOFFICE_WORKING_COPY_NOT_FOUND')

        with open(path, 'rb') as fh:
            return path, fh.read()
    return _rb_onlyoffice_working_bytes


def install_0898(_rb):
    def _rb_commit_onlyoffice_version(
        order,
        doctor_user,
        requested_status,
        base_version_no,
    ):
        """
    Compatibility bridge for existing ONLYOFFICE routes.

    ONLYOFFICE owns no clinical report storage.

    DRAFT:
        working copy -> unified commit writer

    VERIFIED:
        verify the existing latest DRAFT only
        no new ReportVersion

    FINAL / FINALIZED:
        finalize the existing latest VERIFIED only
        no new ReportVersion

    The ONLYOFFICE callback remains working-copy only.
    """

        import uuid

        from report_commit_core import (
            validate_base_version,
        )

        from report_version_safety import (
            validate_docx_bytes,
        )

        from onlyoffice_report_bridge import (
            onlyoffice_save_draft,
            onlyoffice_verify_latest,
            onlyoffice_finalize_latest,
        )

        requested_status = str(
            requested_status or ''
        ).strip().upper()

        if requested_status not in (
            'DRAFT',
            'VERIFIED',
            'FINAL',
            'FINALIZED',
        ):
            raise ValueError(
                'INVALID_ONLYOFFICE_COMMIT_STATUS'
            )

        report = _rb.get_report(order)

        if (
            (report.status or '').upper()
            == 'FINAL'
        ):
            raise ValueError(
                'FINAL_REPORT_LOCKED'
            )

        working_path, raw = \
            _rb._rb_onlyoffice_working_bytes(order)

        # --------------------------------------------------
        # Structural DOCX validation.
        # --------------------------------------------------

        meta = validate_docx_bytes(raw)

        incoming_hash = str(
            meta['sha256'] or ''
        ).strip().lower()

        # --------------------------------------------------
        # Patient / Accession identity gate.
        # --------------------------------------------------

        safety = _rb.validate_report_patient_file(
            order,
            working_path,
            '.docx'
        )

        if safety.get('result') != 'MATCH':
            raise ValueError(
                'REPORT_PATIENT_IDENTITY_MISMATCH'
            )

        # --------------------------------------------------
        # Latest version is re-read before explicit action.
        # --------------------------------------------------

        latest = _rb._rb_latest_report_version(
            report
        )

        current_no = (
            int(latest.version_no)
            if latest
            else 0
        )

        # DRAFT idempotency and stale-base ordering is owned by
        # commit_report_version() under the Report row lock:
        #
        #   existing commit_id -> return existing version
        #   otherwise          -> validate base version
        #
        # Running the base gate here for DRAFT would reject a
        # legitimate network retry before the idempotency lookup.
        #
        # VERIFY / FINALIZE remain non-content state transitions
        # and keep their helper-level base-version protection.
        if requested_status != 'DRAFT':
            validate_base_version(
                current_version_no=current_no,
                base_version_no=base_version_no,
            )

        current_hash = (
            str(latest.sha256 or '')
            .strip()
            .lower()
            if latest
            else ''
        )

        # --------------------------------------------------
        # DRAFT = the only content-creating action.
        # --------------------------------------------------

        # RB_DRAFT_SERIES_POLICY_V1
        # Repeating the latest identical DRAFT is an idempotent
        # success and must not allocate another version.
        if (
            requested_status == 'DRAFT'
            and latest is not None
            and str(latest.status or '').upper() == 'DRAFT'
            and incoming_hash == current_hash
        ):
            return latest

        if requested_status == 'DRAFT':
            try:
                draft_limit = max(
                    1,
                    int(_rb.os.getenv(
                        'REPORT_MAX_DRAFT_VERSIONS',
                        '10'
                    ))
                )
            except (TypeError, ValueError):
                draft_limit = 10

            draft_count = (
                _rb.ReportVersion.query
                .filter_by(
                    report_id=report.id,
                    status='DRAFT'
                )
                .count()
            )

            if draft_count >= draft_limit:
                limit_error = RuntimeError(
                    'DRAFT_VERSION_LIMIT_REACHED'
                )
                limit_error.code = (
                    'DRAFT_VERSION_LIMIT_REACHED'
                )
                raise limit_error

        if requested_status == 'DRAFT':

            findings, impression, radiologist = \
                _rb.extract_docx_sections(
                    working_path
                )

            #
            # Stable commit UUID:
            #
            # If the browser retries the same save request
            # with the same base version + same document,
            # the DB idempotency constraint resolves it to
            # the same clinical version.
            #

            commit_key = (
                'radbridge-onlyoffice:'
                f'order={order.id}:'
                f'base={int(base_version_no)}:'
                f'sha256={incoming_hash}'
            )

            commit_id = str(
                uuid.uuid5(
                    uuid.NAMESPACE_URL,
                    commit_key
                )
            )

            result = onlyoffice_save_draft(
                db=_rb.db,
                Report=_rb.Report,
                ReportVersion=_rb.ReportVersion,
                report_root=_rb.REPORT_DIR,
                order=order,
                patient=order.patient,
                user=doctor_user,
                source_file=working_path,
                base_version_no=base_version_no,
                commit_id=commit_id,
                findings=findings or '',
                impression=impression or '',
                radiologist=(
                    radiologist
                    if radiologist
                    and radiologist
                    != '____________________'
                    else (
                        doctor_user.full_name
                        or doctor_user.username
                        or 'Unknown'
                    )
                ),
            )

            version = result['version']

            try:
                _rb.audit_as_user(
                    doctor_user,
                    (
                        'REPORT_VERSION_RETRY'
                        if result.get('retry')
                        else 'REPORT_VERSION_COMMITTED'
                    ),
                    'order',
                    order.id,
                    (
                        f'version={version.version_no}; '
                        'status=DRAFT; '
                        'editor=ONLYOFFICE; '
                        f'commit_id={commit_id}; '
                        f'sha256={incoming_hash[:12]}'
                    )
                )

                _rb.db.session.commit()

            except Exception:

                artifact = (
                    getattr(
                        version,
                        'source_path',
                        None
                    )
                    if not result.get('retry')
                    else None
                )

                _rb.db.session.rollback()

                #
                # If DB commit failed after the unified
                # writer published the new immutable file,
                # remove only that uncommitted artifact.
                #

                if (
                    artifact
                    and
                    _rb.os.path.isfile(artifact)
                ):
                    try:
                        _rb.os.unlink(artifact)
                    except Exception:
                        pass

                raise

            return version

        # --------------------------------------------------
        # VERIFY / FINALIZE never create content versions.
        # --------------------------------------------------

        if latest is None:
            raise ValueError(
                'NO_REPORT_VERSION'
            )

        #
        # Clinical protection:
        #
        # The working document must exactly equal the latest
        # committed version before Verify or Finalize.
        #
        # Otherwise the doctor must Save Draft first.
        #

        if (
            not current_hash
            or incoming_hash != current_hash
        ):
            raise ValueError(
                'ONLYOFFICE_CHANGES_NOT_SAVED_AS_DRAFT'
            )

        if requested_status == 'VERIFIED':

            before_count = (
                _rb.ReportVersion.query
                .filter_by(
                    report_id=report.id
                )
                .count()
            )

            version = onlyoffice_verify_latest(
                db=_rb.db,
                Report=_rb.Report,
                ReportVersion=_rb.ReportVersion,
                order=order,
                user=doctor_user,
            )

            after_count = (
                _rb.ReportVersion.query
                .filter_by(
                    report_id=report.id
                )
                .count()
            )

            if after_count != before_count:
                _rb.db.session.rollback()

                raise RuntimeError(
                    'VERIFY_CREATED_EXTRA_VERSION'
                )

            _rb.audit_as_user(
                doctor_user,
                'REPORT_VERSION_VERIFIED',
                'order',
                order.id,
                (
                    f'version={version.version_no}; '
                    'editor=ONLYOFFICE'
                )
            )

            _rb.db.session.commit()

            return version

        # --------------------------------------------------
        # FINAL / FINALIZED
        # --------------------------------------------------

        before_count = (
            _rb.ReportVersion.query
            .filter_by(
                report_id=report.id
            )
            .count()
        )

        version = onlyoffice_finalize_latest(
            db=_rb.db,
            Report=_rb.Report,
            ReportVersion=_rb.ReportVersion,
            order=order,
            user=doctor_user,
        )

        after_count = (
            _rb.ReportVersion.query
            .filter_by(
                report_id=report.id
            )
            .count()
        )

        if after_count != before_count:
            _rb.db.session.rollback()

            raise RuntimeError(
                'FINALIZE_CREATED_EXTRA_VERSION'
            )

        _rb.audit_as_user(
            doctor_user,
            'REPORT_VERSION_FINALIZED',
            'order',
            order.id,
            (
                f'version={version.version_no}; '
                'editor=ONLYOFFICE'
            )
        )

        _rb.db.session.commit()

        return version
    return _rb_commit_onlyoffice_version
