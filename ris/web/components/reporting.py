"""Runtime-bound web.components.reporting; dependencies are supplied at composition.

Legacy behavior is preserved; new policies belong in the independent domain layer.
"""

def install_0190(_rb):
    @_rb.login_required
    def reporting_agent_download():
        path=_rb.os.path.join(_rb.os.path.dirname(_rb.__file__),'downloads','RIS-Reporting-Agent-Auto-v2.zip')
        if not _rb.os.path.exists(path):
            _rb.abort(404)
        return _rb.send_file(path,as_attachment=True,download_name='RIS-Reporting-Agent-Auto-v2.zip')
    return reporting_agent_download


def install_0191(_rb):
    def api_reporting_health():
        db_ok=True
        db_error=''
        try:
            _rb.db.session.execute(_rb.text('SELECT 1'))
        except Exception as exc:
            db_ok=False
            db_error=str(exc)

        return _rb.jsonify({
            'ok': bool(db_ok),
            'service': 'RIS Reporting API',
            'version': _rb.APP_VERSION,
            'database': db_ok,
            'database_error': db_error if not db_ok else '',
            'pacs': _rb.orthanc_ok(),
            'reports_dir': _rb.os.path.isdir(_rb.REPORT_DIR) and _rb.os.access(_rb.REPORT_DIR, _rb.os.W_OK),
            'attachments_dir': _rb.os.path.isdir(_rb.ATTACHMENT_DIR) and _rb.os.access(_rb.ATTACHMENT_DIR, _rb.os.W_OK),
            'word_agent': _rb.os.path.exists(_rb.os.path.join(_rb.os.path.dirname(_rb.__file__),'downloads','RIS-Reporting-Agent-Auto-v2.zip'))
        })
    return api_reporting_health


def install_0222(_rb):
    def reporting_actor(accession):
        user=_rb.current_user()

        if user and user.active:
            return user

        case_token=(
            _rb.request.headers.get('X-RadBridge-Case-Token')
            or ''
        ).strip()

        if not case_token:
            return None

        try:
            data=_rb._reporting_serializer().loads(
                case_token,
                max_age=max(
                    60,
                    _rb.REPORTING_CASE_TOKEN_TTL_SECONDS
                )
            )
        except (
            _rb.BadSignature,
            _rb.SignatureExpired,
            ValueError,
            TypeError,
        ):
            return None

        if (
            str(data.get('accession') or '')
            != str(accession or '')
        ):
            return None

        user_id=data.get('user_id')

        if not user_id:
            return None

        user=_rb.db.session.get(_rb.User,int(user_id))

        if not user or not user.active:
            return None

        return user
    return reporting_actor


def install_0223(_rb):
    def _reporting_api_authorized(accession, write=False):
        """Allow RIS session, accession-scoped agent token, or dedicated service token."""
        user = _rb.current_user()
        if user and user.active:
            return _rb.has_perm('reports.edit' if write else 'reports.view')

        case_token = (_rb.request.headers.get('X-RadBridge-Case-Token') or '').strip()
        if _rb._valid_reporting_case_token(case_token, accession, write=write):
            return True

        supplied = (_rb.request.headers.get('X-RadBridge-Reporting-Token') or '').strip()
        return bool(
            _rb.RADBRIDGE_REPORTING_TOKEN
            and supplied
            and _rb.hmac.compare_digest(supplied, _rb.RADBRIDGE_REPORTING_TOKEN)
        )
    return _reporting_api_authorized


def install_0224(_rb):
    def require_reporting_api(write=False):
        def deco(fn):
            @_rb.wraps(fn)
            def wrapped(*args, **kwargs):
                accession = kwargs.get('accession')
                if not _rb._reporting_api_authorized(accession, write=write):
                    status = 403 if _rb.current_user() else 401
                    return _rb.jsonify({'ok': False, 'error': 'REPORTING_AUTH_REQUIRED'}), status
                return fn(*args, **kwargs)
            return wrapped
        return deco
    return require_reporting_api


def install_0225(_rb):
    def word_addin_taskpane():
        return _rb.render_template(
            'word_addin_taskpane.html'
        )
    return word_addin_taskpane


def install_0226(_rb):
    def word_addin_manifest():
        return _rb.Response(
            _rb.render_template(
                'word_addin_manifest.xml',
                ris_public_url=_rb.RIS_PUBLIC_URL.rstrip('/')
            ),
            mimetype='application/xml'
        )
    return word_addin_manifest


def install_0586(_rb):
    def granular_delete_reports_only_execute(order, typed_accession, reason):
        """Dependency-safe Delete Reports Only execution.

    Invariants:
      * SUPER_ADMIN only.
      * exact typed Accession and mandatory reason.
      * Report/ReportVersion only; Order/Patient/PACS/Audit are preserved.
      * CoordinatorTask or active edit lease blocks execution.
      * report case directory is moved to same-filesystem quarantine first.
      * database deletion is revalidated under row locks and verified before commit.
      * any database failure attempts to restore quarantined files.
    """
        from pathlib import Path as _DeletePath
        from sqlalchemy import inspect as _delete_inspect, text as _delete_text

        user=_rb.current_user()
        reason=str(reason or '').strip()
        typed_accession=str(typed_accession or '').strip()
        expected_accession=str(getattr(order,'accession','') or '').strip()

        if not _rb._delete_reports_only_is_super_admin(user):
            _rb.abort(403)

        if len(reason) < 5:
            return _rb._delete_reports_only_blocked_response(
                order,reason,'REASON_REQUIRED',['REASON_REQUIRED'],400
            )

        if not typed_accession or typed_accession != expected_accession:
            return _rb._delete_reports_only_blocked_response(
                order,reason,'ACCESSION_CONFIRMATION_MISMATCH',
                ['ACCESSION_CONFIRMATION_MISMATCH'],409
            )

        patient=getattr(order,'patient',None)
        if patient is None:
            return _rb._delete_reports_only_blocked_response(
                order,reason,'PATIENT_NOT_FOUND',['PATIENT_NOT_FOUND'],409
            )

        initial_reports=(
            _rb.Report.query
            .filter_by(order_id=order.id)
            .order_by(_rb.Report.id)
            .all()
        )
        initial_preview=_rb.granular_delete_reports_only_preview_snapshot(
            order,patient,initial_reports
        )

        if not initial_preview.get('can_delete_reports_only'):
            return _rb._delete_reports_only_blocked_response(
                order,reason,'REPORTS_ONLY_PREFLIGHT_BLOCKED',
                initial_preview.get('blocker_codes') or ['PREFLIGHT_BLOCKED'],409
            )

        initial_report_ids=tuple(initial_preview.get('report_ids') or ())
        initial_version_ids=tuple(
            int(row.get('id')) for row in (initial_preview.get('versions') or [])
        )
        initial_artifact_paths=tuple(sorted(
            str(row.get('path') or '')
            for row in initial_preview.get('storage',{}).get('artifacts',[])
        ))
        pacs_before={
            'pacs_study_id':getattr(order,'pacs_study_id',None),
            'pacs_image_count':getattr(order,'pacs_image_count',None),
            'pacs_status':getattr(order,'pacs_status',None),
            'study_instance_uid':getattr(order,'study_instance_uid',None),
        }

        operation_id=(
            _rb.datetime.utcnow().strftime('%Y%m%d-%H%M%S')
            +'-'+_rb.secrets.token_hex(6)
        )
        case_root=None
        quarantine_target=None
        quarantined=False

        try:
            locked_order=(
                _rb.Order.query
                .filter_by(id=order.id)
                .with_for_update()
                .first()
            )
            if locked_order is None:
                raise RuntimeError('ORDER_NOT_FOUND_AFTER_LOCK')

            locked_patient=_rb.db.session.get(_rb.Patient,locked_order.patient_id)
            if locked_patient is None:
                raise RuntimeError('PATIENT_NOT_FOUND_AFTER_LOCK')

            locked_reports=(
                _rb.Report.query
                .filter_by(order_id=locked_order.id)
                .order_by(_rb.Report.id)
                .with_for_update()
                .all()
            )

            final_preview=_rb.granular_delete_reports_only_preview_snapshot(
                locked_order,locked_patient,locked_reports
            )
            final_blockers=list(final_preview.get('blocker_codes') or ())

            if tuple(final_preview.get('report_ids') or ()) != initial_report_ids:
                final_blockers.append('REPORT_SET_CHANGED_AFTER_PREFLIGHT')
            if tuple(
                int(row.get('id')) for row in (final_preview.get('versions') or [])
            ) != initial_version_ids:
                final_blockers.append('REPORT_VERSION_SET_CHANGED_AFTER_PREFLIGHT')
            if tuple(sorted(
                str(row.get('path') or '')
                for row in final_preview.get('storage',{}).get('artifacts',[])
            )) != initial_artifact_paths:
                final_blockers.append('REPORT_ARTIFACT_SET_CHANGED_AFTER_PREFLIGHT')
            if str(getattr(locked_order,'accession','') or '').strip() != expected_accession:
                final_blockers.append('ACCESSION_CHANGED_AFTER_PREFLIGHT')

            if final_blockers:
                _rb.db.session.rollback()
                return _rb._delete_reports_only_blocked_response(
                    order,reason,'FINAL_REVALIDATION_BLOCKED',final_blockers,409
                )

            case_root,quarantine_target=_rb._delete_reports_only_quarantine_target(
                locked_patient,locked_order,operation_id
            )
            report_root=_DeletePath(_rb.REPORT_DIR).resolve()
            case_root=_DeletePath(case_root).resolve()
            quarantine_target=_DeletePath(quarantine_target).resolve()
            case_root.relative_to(report_root)
            quarantine_target.relative_to(report_root)

            # Move the complete case report tree (versions + working files) before
            # DB deletion. os.replace is same-filesystem and does not silently copy.
            if case_root.exists():
                quarantine_target.parent.mkdir(parents=True,exist_ok=True)
                if quarantine_target.exists():
                    raise RuntimeError('QUARANTINE_TARGET_EXISTS')
                _rb.os.replace(str(case_root),str(quarantine_target))
                quarantined=True

            report_ids=[int(row.id) for row in locked_reports]
            version_count_before=int(final_preview.get('version_count') or 0)
            expired_lease_count=int(final_preview.get('lease',{}).get('expired_count') or 0)

            inspector=_delete_inspect(_rb.db.engine)
            if report_ids and inspector.has_table('report_edit_lease'):
                placeholders=','.join(str(int(value)) for value in report_ids)
                _rb.db.session.execute(
                    _delete_text(
                        'DELETE FROM report_edit_lease '
                        'WHERE (order_id = :order_id OR report_id IN ('+placeholders+')) '
                        'AND expires_at <= :now'
                    ),
                    {'order_id':int(locked_order.id),'now':_rb.datetime.utcnow()},
                )

            if report_ids:
                _rb.ReportVersion.query.filter(
                    _rb.ReportVersion.report_id.in_(report_ids)
                ).delete(synchronize_session=False)
                for row in locked_reports:
                    _rb.db.session.delete(row)

            _rb.db.session.flush()

            remaining_reports=_rb.Report.query.filter_by(order_id=locked_order.id).count()
            remaining_versions=(
                _rb.ReportVersion.query
                .filter(_rb.ReportVersion.report_id.in_(report_ids))
                .count()
                if report_ids else 0
            )
            order_still_present=_rb.db.session.get(_rb.Order,locked_order.id) is not None
            patient_still_present=_rb.db.session.get(_rb.Patient,locked_patient.id) is not None

            if remaining_reports or remaining_versions:
                raise RuntimeError('REPORT_DELETE_POSTCHECK_FAILED')
            if not order_still_present or not patient_still_present:
                raise RuntimeError('CORE_CASE_PRESERVATION_FAILED')

            for key,value in pacs_before.items():
                if getattr(locked_order,key,None) != value:
                    raise RuntimeError('PACS_STATE_CHANGED_DURING_REPORT_DELETE')

            _rb.audit(
                'REPORTS_ONLY_DELETED_ADMIN',
                'order',
                locked_order.id,
                (
                    f"accession={expected_accession}; "
                    f"report_ids={','.join(str(x) for x in report_ids)}; "
                    f"report_count={len(report_ids)}; "
                    f"version_count={version_count_before}; "
                    f"expired_leases_removed={expired_lease_count}; "
                    f"quarantined={'yes' if quarantined else 'no'}; "
                    f"quarantine={str(quarantine_target) if quarantined else ''}; "
                    f"operation_id={operation_id}; "
                    f"reason={reason}"
                ),
            )
            _rb.db.session.commit()

            return {
                'ok':True,
                'deleted':True,
                'order_id':locked_order.id,
                'accession':expected_accession,
                'report_count_deleted':len(report_ids),
                'version_count_deleted':version_count_before,
                'expired_leases_removed':expired_lease_count,
                'quarantined':quarantined,
                'quarantine_path':str(quarantine_target) if quarantined else None,
                'operation_id':operation_id,
                'post_delete':{
                    'report_count':0,
                    'version_count':0,
                    'order_preserved':True,
                    'patient_preserved':True,
                    'pacs_state_preserved':True,
                },
            },200

        except Exception as exc:
            _rb.db.session.rollback()
            restored=False
            restore_error=None

            if quarantined and quarantine_target is not None and case_root is not None:
                try:
                    case_root.parent.mkdir(parents=True,exist_ok=True)
                    if case_root.exists():
                        raise RuntimeError('RESTORE_TARGET_ALREADY_EXISTS')
                    _rb.os.replace(str(quarantine_target),str(case_root))
                    restored=True
                except Exception as restore_exc:
                    restore_error=type(restore_exc).__name__

            try:
                _rb.audit(
                    'REPORTS_ONLY_DELETE_FAILED_ADMIN',
                    'order',
                    getattr(order,'id',''),
                    (
                        f"accession={expected_accession}; "
                        f"operation_id={operation_id}; "
                        f"error={type(exc).__name__}; "
                        f"quarantined={'yes' if quarantined else 'no'}; "
                        f"restored={'yes' if restored else 'no'}; "
                        f"restore_error={restore_error or ''}; "
                        f"reason={reason}"
                    ),
                )
                _rb.db.session.commit()
            except Exception:
                _rb.db.session.rollback()

            return {
                'ok':False,
                'deleted':False,
                'error':'REPORTS_ONLY_DELETE_FAILED',
                'failure_type':type(exc).__name__,
                'quarantined':quarantined,
                'restored':restored,
                'restore_error':restore_error,
            },500
    return granular_delete_reports_only_execute


def install_0864(_rb):
    @_rb.require_ohif_token
    def api_ohif_reporting_agent_download():
        path = _rb.os.path.join(
            _rb.os.path.dirname(_rb.__file__),
            'downloads',
            'RIS-Reporting-Agent-Auto-v2.zip'
        )

        if not _rb.os.path.exists(path):
            return _rb.jsonify({
                'ok': False,
                'error': 'REPORTING_AGENT_NOT_FOUND'
            }), 404

        return _rb.send_file(
            path,
            as_attachment=True,
            download_name='RIS-Reporting-Agent-Auto-v2.zip'
        )
    return api_ohif_reporting_agent_download


def install_0876(_rb):
    def api_ohif_reporting_health():
        return _rb.jsonify({
            'ok': True,
            'service': 'OHIF Reporting API',
            'version': '5.36'
        })
    return api_ohif_reporting_health


def install_0887(_rb):
    def api_ohif_onlyoffice_health():
        result = {
            'ok': False,
            'service': 'RadBridge ONLYOFFICE Integration',
            'jwt_configured': bool(_rb.ONLYOFFICE_JWT_SECRET),
            'document_server': _rb.ONLYOFFICE_INTERNAL_URL
        }

        try:
            r = _rb.requests.get(
                _rb.ONLYOFFICE_INTERNAL_URL + '/healthcheck',
                timeout=5
            )

            result['onlyoffice_http'] = r.status_code
            result['onlyoffice_body'] = r.text[:100]
            result['ok'] = (
                r.status_code == 200
                and r.text.strip().lower() == 'true'
                and bool(_rb.ONLYOFFICE_JWT_SECRET)
            )

        except Exception as exc:
            result['error'] = str(exc)

        return _rb.jsonify(result), (200 if result['ok'] else 503)
    return api_ohif_onlyoffice_health

