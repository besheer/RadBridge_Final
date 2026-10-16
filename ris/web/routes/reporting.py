"""Runtime-bound web.routes.reporting; dependencies are supplied at composition.

Legacy behavior is preserved; new policies belong in the independent domain layer.
"""

def install_0174(_rb):
    @_rb.app.route('/portal/<token>/report')
    def patient_portal_report(token):
        x=_rb.PortalAccessToken.query.filter_by(token=token,revoked=False).first_or_404()
        if x.expires_at<_rb.datetime.utcnow(): _rb.abort(410)
        o=x.order
        if not o or o.status!='FINAL' or not o.report or o.report.status!='FINAL': _rb.abort(404)
        corrected=_rb._rb_final_revision_document(o)
        if corrected:return _rb._rb_revision_pdf_download(o,corrected)
        path=o.report.pdf_path or o.report.source_path
        if not path or not _rb.os.path.exists(path): _rb.abort(404)
        return _rb.send_file(path,as_attachment=True,download_name=_rb.os.path.basename(path))
    return patient_portal_report


def install_0198(_rb):
    @_rb.app.route('/doctor')
    @_rb.require_perm('reports.view')
    def doctor_workspace():
        # RB_DOCTOR_UNIFIED_WORKSPACE_V1: personal queue, never a global worklist.
        if not _rb.doctor_workspace_user(_rb.current_user()):
            _rb.abort(403)
        return _rb.render_template(
            'doctor_unified_workspace.html',
            saved_views=_rb._saved_views_for('DOCTOR'),
            saved_view_page='DOCTOR',
        )
    return doctor_workspace


def install_0199(_rb):
    @_rb.app.get('/api/doctor/workspace')
    @_rb.require_perm('reports.view')
    def doctor_workspace_data():
        u=_rb.current_user()
        if not _rb.doctor_workspace_user(u):
            _rb.abort(403)
        # Preserve the existing offer-page/popup expiry maintenance behavior.
        _rb.expire_assignment_offers()
        now=_rb.datetime.utcnow()
        orders=_rb.Order.query.filter_by(assigned_doctor_id=u.id).order_by(_rb.Order.scheduled.desc()).limit(500).all()
        offers=_rb.AssignmentOffer.query.filter_by(doctor_user_id=u.id,status='PENDING').filter(_rb.AssignmentOffer.expires_at>now).order_by(_rb.AssignmentOffer.offered_at.desc()).limit(100).all()
        def case_data(o):
            external=_rb.ExternalIntakeCase.query.filter_by(order_id=o.id).first()
            report=o.report
            sla=_rb.report_sla_snapshot(o,report,now=now)
            assessment=_rb.ClinicalAssessment.query.filter_by(order_id=o.id).first()
            performing=_rb.OrderPerformingDoctor.query.filter_by(order_id=o.id).first()
            attachment_count=_rb.PatientDocument.query.filter_by(order_id=o.id).count()
            prior_count=_rb.PriorStudySelection.query.filter_by(order_id=o.id).count()
            iso=lambda value: value.isoformat(sep=' ') if value else ''
            return {'id':o.id,'accession':o.accession,'patient':o.patient.name,
                    'patient_id':o.patient.patient_id,
                    'patient_worklist':_rb.patient_worklist_display_name(o.patient),
                    'dob':o.patient.dob or '','sex':o.patient.sex or '',
                    'procedure':o.procedure,
                    'procedure_code':o.proc.code if o.proc else '',
                    'modality':o.modality,
                    'body_part':o.proc.body_part if o.proc else '',
                    'contrast':bool(o.proc.contrast) if o.proc else False,
                    'priority':o.priority or 'ROUTINE','status':o.status,
                    'exam_status':o.exam_status or '','pacs_status':o.pacs_status or '',
                    'images':int(o.pacs_image_count or 0),
                    'branch':o.branch.name if o.branch else '',
                    'device':o.device.name if o.device else '',
                    'room':o.device.room if o.device else '',
                    'station_ae':o.station_ae or '',
                    'referring_doctor':o.referring_doctor.name if o.referring_doctor else '',
                    'assigned_doctor':o.assigned_doctor.full_name if o.assigned_doctor else '',
                    'performing_doctor':performing.doctor.full_name if performing and performing.doctor else '',
                    'clinical_indication':assessment.clinical_indication if assessment else '',
                    'clinical_history':assessment.history if assessment else '',
                    'clinical_diagnosis':assessment.diagnosis if assessment else '',
                    'allergy_notes':assessment.allergy_notes if assessment else '',
                    'attachment_count':attachment_count,'prior_count':prior_count,
                    'study_instance_uid':o.study_instance_uid or '',
                    'scheduled_at':iso(o.scheduled),'assigned_at':iso(o.assigned_at),
                    'exam_started_at':iso(o.exam_started_at),
                    'exam_completed_at':iso(o.exam_completed_at),
                    'pacs_last_seen_at':iso(o.pacs_last_seen_at),
                    'report_status':report.status if report else 'UNREPORTED',
                    'reported_by':report.radiologist if report else '',
                    'verified_by':report.verified_by if report else '',
                    'verified_at':iso(report.verified_at) if report else '',
                    'second_verified_by':report.second_verified_by if report else '',
                    'second_verified_at':iso(report.second_verified_at) if report else '',
                    'finalized_by':report.finalized_by if report else '',
                    'finalized_at':iso(report.finalized_at) if report else '',
                    'report_updated_at':iso(report.updated_at) if report else '',
                    'report_delivered':bool(o.report_delivered),
                    'images_delivered':bool(o.images_delivered),
                    'sla_status':sla['status'],
                    'sla_elapsed_minutes':sla['elapsed_minutes'],
                    'sla_remaining_minutes':sla['remaining_minutes'],
                    'source':'EXTERNAL' if external else 'INTERNAL',
                    'center':external.center.name if external else '',
                    'has_linked_study':bool(o.pacs_study_id),
                    'open_url':_rb.url_for('doctor_workspace_open',order_id=o.id),
                    'viewer_choice_url':_rb.url_for('viewer_choice.choose',order_id=o.id),
                    'start_url':_rb.url_for('doctor_reading_start',order_id=o.id),
                    **_rb.assignment_visit_summary(o),
                    'return_url':_rb.url_for('return_case_form',order_id=o.id),
                    'return_allowed':bool((o.status or '').upper() not in ('FINAL','CANCELLED') and
                        (getattr(report,'status','') or '').upper() not in ('VERIFIED','FINAL'))}
        profile=_rb.UserProfile.query.filter_by(user_id=u.id).first()
        profile_settings=_rb.user_profile_settings(profile) if profile else {}
        response=_rb.jsonify(ok=True,cases=[case_data(o) for o in orders],offers=[
            {'id':offer.id,'case':case_data(offer.order),'expires_at':offer.expires_at.isoformat()+'Z',
             'respond_url':_rb.url_for('assignment_offer_respond',offer_id=offer.id)} for offer in offers],
            column_layout=profile_settings.get('doctor_worklist_columns'))
        response.headers['Cache-Control']='no-store'
        return response
    return doctor_workspace_data


def install_0201(_rb):
    @_rb.app.post('/api/doctor/workspace/column-layout')
    @_rb.require_perm('reports.view')
    def doctor_workspace_column_layout_save():
        user=_rb.current_user()
        if not _rb.doctor_workspace_user(user):
            _rb.abort(403)
        payload=_rb.request.get_json(silent=True)
        if not isinstance(payload,dict):
            return _rb.jsonify(ok=False,error='INVALID_COLUMN_LAYOUT'),400
        layout=_rb.normalize_doctor_worklist_layout(payload)
        profile=_rb.get_user_profile(user)
        settings=_rb.user_profile_settings(profile)
        settings['doctor_worklist_columns']=layout
        profile.settings_json=_rb.json.dumps(settings,separators=(',',':'))
        _rb.db.session.commit()
        return _rb.jsonify(ok=True,column_layout=layout)
    return doctor_workspace_column_layout_save


def install_0204(_rb):
    @_rb.app.before_request
    def doctor_report_ownership_guard():
        # Apply to legacy report URLs too, before get_report can create a record.
        if not _rb.request.path.startswith('/reports/'):
            return None
        user=_rb.current_user()
        role=(user.role.code if user and user.role else '').upper()
        if role not in ('RADIOLOGIST','DOCTOR','CONSULTANT','RADIOLOGY_CONSULTANT'):
            return None
        order_id=(_rb.request.view_args or {}).get('order_id')
        if order_id is not None and not _rb.doctor_case_access_allowed(user,_rb.db.session.get(_rb.Order,order_id)):
            _rb.abort(403)
    return doctor_report_ownership_guard


def install_0205(_rb):
    @_rb.app.get('/doctor/cases/<int:order_id>/open')
    @_rb.require_perm('reports.view')
    def doctor_workspace_open(order_id):
        order=_rb.Order.query.get_or_404(order_id)
        if not _rb.doctor_case_access_allowed(_rb.current_user(),order):
            _rb.abort(403)
        return _rb.open_image_viewer_case(order)
    return doctor_workspace_open


def install_0212(_rb):
    @_rb.app.post('/doctor/cases/<int:order_id>/start-reading')
    @_rb.require_perm('reports.view')
    def doctor_reading_start(order_id):
        from assignment_distribution import mark_reading_started
        user=_rb.current_user()
        if not _rb.doctor_workspace_user(user): _rb.abort(403)
        order=_rb.Order.query.get_or_404(order_id)
        if order.assigned_doctor_id != user.id or not _rb.doctor_case_access_allowed(user,order): _rb.abort(403)
        if not mark_reading_started(order.id,user.id): _rb.abort(409)
        _rb.db.session.commit()
        return _rb.redirect(_rb.url_for('doctor_workspace_open',order_id=order.id))
    return doctor_reading_start


def install_0213(_rb):
    @_rb.app.route('/reports')
    @_rb.require_perm('reports.view')
    def reports():
        rows=_rb.Order.query.order_by(_rb.Order.scheduled.desc()).limit(400).all()
        return _rb.render_template('reports.html',orders=rows)
    return reports


def install_0214(_rb):
    @_rb.app.post('/reports/<int:order_id>/admin-reopen')
    @_rb.require_perm('reports.edit')
    def admin_report_reopen(order_id):
        u=_rb.current_user()

        role=(
            u.role.code.upper()
            if u and u.role and u.role.code
            else ''
        )

        if role not in ('SUPER_ADMIN','ADMIN'):
            _rb.abort(403)

        order=_rb.Order.query.get_or_404(order_id)
        report=_rb.get_report(order)

        _rb.audit_as_user(
            u,
            'REPORT_REOPEN_BLOCKED',
            'order',
            order.id,
            (
                'Legacy FINAL->DRAFT reopen disabled. '
                'A dedicated Addendum workflow is required.'
            )
        )

        _rb.db.session.commit()

        _rb.flash(
            'Reopening a FINAL report is disabled. '
            'A dedicated Addendum workflow must be used.',
            'danger'
        )

        return _rb.redirect(
            _rb.url_for(
                'report_editor',
                order_id=order.id
            )
        )
    return admin_report_reopen


def install_0215(_rb):
    @_rb.app.post('/reports/<int:order_id>/lease/acquire')
    @_rb.require_perm('reports.edit')
    def report_lease_acquire(order_id):
        import secrets

        order=_rb.Order.query.get_or_404(order_id)
        report=_rb.get_report(order)
        user=_rb.current_user()

        data=_rb.request.get_json(silent=True) or {}

        editor_type=str(
            data.get('editor_type') or 'BROWSER'
        ).strip().upper()

        supplied_token=str(
            data.get('lease_token') or
            _rb.request.headers.get('X-RadBridge-Report-Lease') or
            ''
        ).strip()

        lease_token=(
            supplied_token
            if supplied_token
            else secrets.token_urlsafe(32)
        )

        try:
            lease=_rb.acquire_or_renew_lease(
                db=_rb.db,
                order=order,
                report=report,
                user=user,
                editor_type=editor_type,
                lease_token=lease_token,
            )

            _rb.audit(
                'REPORT_EDIT_LEASE_ACQUIRED',
                'order',
                order.id,
                f'editor={editor_type}; user={user.id}'
            )

            _rb.db.session.commit()

            return _rb.jsonify({
                'ok': True,
                'lease_token': lease_token,
                'editor_type': lease.editor_type,
                'expires_at': lease.expires_at.isoformat(),
            })

        except _rb.ReportEditControlError as exc:
            _rb.db.session.rollback()

            code=getattr(
                exc,
                'code',
                type(exc).__name__
            )

            try:
                _rb.audit(
                    'REPORT_EDIT_LEASE_DENIED',
                    'order',
                    order.id,
                    f'editor={editor_type}; code={code}; user={user.id}'
                )
                _rb.db.session.commit()
            except Exception:
                _rb.db.session.rollback()

            return _rb.jsonify({
                'ok': False,
                'error': code,
            }), 409 if code in (
                'FINAL_REPORT_LOCKED',
                'REPORT_EDIT_LOCKED',
            ) else 403
    return report_lease_acquire


def install_0216(_rb):
    @_rb.app.post('/reports/<int:order_id>/lease/release')
    @_rb.require_perm('reports.edit')
    def report_lease_release(order_id):
        order=_rb.Order.query.get_or_404(order_id)
        user=_rb.current_user()

        data=_rb.request.get_json(silent=True) or {}

        lease_token=str(
            data.get('lease_token') or
            _rb.request.headers.get('X-RadBridge-Report-Lease') or
            ''
        ).strip()

        if not lease_token:
            return _rb.jsonify({
                'ok': False,
                'error': 'REPORT_LEASE_TOKEN_REQUIRED',
            }), 400

        try:
            released=_rb.release_lease(
                db=_rb.db,
                order_id=order.id,
                user_id=user.id,
                lease_token=lease_token,
            )

            _rb.audit(
                'REPORT_EDIT_LEASE_RELEASED',
                'order',
                order.id,
                f'user={user.id}; released={released}'
            )

            _rb.db.session.commit()

            return _rb.jsonify({
                'ok': True,
                'released': released,
            })

        except Exception:
            _rb.db.session.rollback()
            raise
    return report_lease_release


def install_0217(_rb):
    @_rb.app.route('/reports/<int:order_id>',methods=['GET','POST'])
    @_rb.require_perm('reports.edit')
    def report_editor(order_id):
        order=_rb.Order.query.get_or_404(order_id)
        if not _rb.doctor_case_access_allowed(_rb.current_user(),order):
            _rb.abort(403)
        report=_rb.get_report(order)

        if _rb.request.method=='POST':
            target=_rb.request.form.get('action','DRAFT').upper().strip()

            user=_rb.current_user()

            try:
                _rb.assert_not_final(report)
                _rb.assert_role_allowed(user,target)

                if target=='DRAFT':
                    lease_token=str(
                        _rb.request.form.get('lease_token') or
                        _rb.request.headers.get('X-RadBridge-Report-Lease') or
                        ''
                    ).strip()

                    _rb.assert_lease_owner(
                        db=_rb.db,
                        order=order,
                        report=report,
                        user=user,
                        lease_token=lease_token,
                    )

            except _rb.ReportEditControlError as exc:
                code=getattr(exc,'code',type(exc).__name__)

                try:
                    _rb.audit(
                        'REPORT_EDIT_DENIED',
                        'order',
                        order.id,
                        f'action={target}; editor=BROWSER; code={code}; user={user.id}'
                    )
                    _rb.db.session.commit()
                except Exception:
                    _rb.db.session.rollback()

                _rb.flash(
                    'Report editing is currently blocked.',
                    'danger'
                )

                return _rb.redirect(
                    _rb.url_for('report_editor',order_id=order.id)
                )

            # Browser clinical workflow is intentionally restricted to the
            # unified DRAFT -> VERIFIED -> FINAL state machine.
            if target not in ('DRAFT','VERIFIED','FINAL'):
                _rb.flash(
                    'This workflow action is not available in the Web editor. '
                    'Use Save Draft, Verify, then Finalize.',
                    'danger'
                )
                return _rb.redirect(
                    _rb.url_for('report_editor',order_id=order.id)
                )

            if (report.status or '').upper()=='FINAL':
                _rb.flash(
                    'Final report is locked. '
                    'A dedicated Addendum workflow is required.',
                    'danger'
                )
                return _rb.redirect(
                    _rb.url_for('report_editor',order_id=order.id)
                )

            user=_rb.current_user()

            if not user:
                _rb.abort(403)

            submitted_base=_rb.request.form.get(
                'base_version_no',
                ''
            ).strip()

            if not submitted_base:
                _rb.flash(
                    'Report version context is missing. Reload the report.',
                    'danger'
                )
                return _rb.redirect(
                    _rb.url_for('report_editor',order_id=order.id)
                )

            try:
                submitted_base=int(submitted_base)
            except Exception:
                _rb.flash(
                    'Invalid report version context. Reload the report.',
                    'danger'
                )
                return _rb.redirect(
                    _rb.url_for('report_editor',order_id=order.id)
                )

            latest=(
                _rb.ReportVersion.query
                .filter_by(report_id=report.id)
                .order_by(_rb.ReportVersion.version_no.desc())
                .first()
            )

            latest_no=int(latest.version_no) if latest else 0

            if submitted_base != latest_no:
                _rb.flash(
                    'This report changed after the page was opened. '
                    'Reload before continuing.',
                    'danger'
                )
                return _rb.redirect(
                    _rb.url_for('report_editor',order_id=order.id)
                )

            username=(
                user.full_name
                or user.username
                or 'Unknown'
            )

            findings=_rb.request.form.get(
                'findings',
                ''
            ).strip()

            impression=_rb.request.form.get(
                'impression',
                ''
            ).strip()

            radiologist=_rb.request.form.get(
                'radiologist',
                ''
            ).strip()

            # VERIFY and FINALIZE are state transitions only.
            # They must never implicitly save edited text.
            if target in ('VERIFIED','FINAL'):
                try:
                    _rb.assert_no_foreign_active_lease(
                        db=_rb.db,
                        order_id=order.id,
                        user=user,
                    )
                except _rb.ReportEditControlError as exc:
                    code=getattr(
                        exc,
                        'code',
                        type(exc).__name__
                    )

                    _rb.audit(
                        'REPORT_EDIT_DENIED',
                        'order',
                        order.id,
                        f'action={target}; editor=BROWSER; code={code}; user={user.id}'
                    )
                    _rb.db.session.commit()

                    _rb.flash(
                        'This report is currently being edited by another user.',
                        'danger'
                    )

                    return _rb.redirect(
                        _rb.url_for(
                            'report_editor',
                            order_id=order.id
                        )
                    )

                if (
                    findings != str(report.findings or '')
                    or impression != str(report.impression or '')
                    or radiologist != str(report.radiologist or '')
                ):
                    _rb.flash(
                        'Unsaved report changes detected. '
                        'Save Draft before Verify or Finalize.',
                        'danger'
                    )
                    return _rb.redirect(
                        _rb.url_for('report_editor',order_id=order.id)
                    )

            try:
                if target=='DRAFT':
                    commit_id=_rb.request.form.get(
                        'commit_id',
                        ''
                    ).strip()

                    if not commit_id:
                        _rb.flash(
                            'Commit identity is missing. Reload the report.',
                            'danger'
                        )
                        return _rb.redirect(
                            _rb.url_for(
                                'report_editor',
                                order_id=order.id
                            )
                        )

                    from report_transaction_writer import \
                        commit_report_version

                    # Browser reports are text-based. Build a temporary DOCX
                    # adapter and send it through the single content writer.
                    tmpdir=_rb.tempfile.mkdtemp(
                        prefix='ris-browser-draft-'
                    )

                    try:
                        tmppath=_rb.os.path.join(
                            tmpdir,
                            'browser-draft.docx'
                        )

                        class _BrowserDraft:
                            pass

                        draft=_BrowserDraft()
                        draft.findings=findings
                        draft.impression=impression
                        draft.radiologist=radiologist

                        buf=_rb.make_docx(order,draft)

                        with open(tmppath,'wb') as fh:
                            fh.write(buf.getvalue())

                        result=commit_report_version(
                            db=_rb.db,
                            Report=_rb.Report,
                            ReportVersion=_rb.ReportVersion,
                            report_root=_rb.REPORT_DIR,
                            order=order,
                            patient=order.patient,
                            user=user,
                            editor_type='BROWSER',
                            requested_status='DRAFT',
                            source_file=tmppath,
                            base_version_no=submitted_base,
                            commit_id=commit_id,
                            findings=findings,
                            impression=impression,
                            radiologist=radiologist,
                            change_summary='Browser Save Draft',
                        )

                    finally:
                        _rb.shutil.rmtree(
                            tmpdir,
                            ignore_errors=True
                        )

                    _rb.audit(
                        'REPORT_BROWSER_DRAFT',
                        'order',
                        order.id,
                        (
                            f'version={result.get("version_no")}; '
                            f'commit_id={commit_id}'
                        )
                    )

                    _rb.db.session.commit()

                    _rb.flash(
                        'Draft saved.',
                        'success'
                    )

                elif target=='VERIFIED':
                    from onlyoffice_report_bridge import \
                        verify_latest_report_version

                    version=verify_latest_report_version(
                        db=_rb.db,
                        Report=_rb.Report,
                        ReportVersion=_rb.ReportVersion,
                        order=order,
                        user=user,
                    )

                    _rb.audit(
                        'REPORT_VERIFIED',
                        'order',
                        order.id,
                        (
                            f'version={version.version_no}; '
                            f'by={username}; editor=BROWSER'
                        )
                    )

                    _rb.db.session.commit()

                    _rb.flash(
                        'Report verified.',
                        'success'
                    )

                elif target=='FINAL':
                    demographic_ok, demographic_reason = \
                        _rb.pacs_demographic_gate(order)

                    if not demographic_ok:
                        _rb.audit(
                            'REPORT_FINALIZE_BLOCKED_DEMOGRAPHICS',
                            'order',
                            order.id,
                            demographic_reason
                        )

                        _rb.db.session.commit()

                        _rb.flash(
                            'Report finalization blocked: '
                            'PACS demographics must be verified '
                            'or reconciled first.',
                            'danger'
                        )

                        return _rb.redirect(
                            _rb.url_for(
                                'report_editor',
                                order_id=order.id
                            )
                        )

                    from onlyoffice_report_bridge import \
                        finalize_latest_report_version

                    version=finalize_latest_report_version(
                        db=_rb.db,
                        Report=_rb.Report,
                        ReportVersion=_rb.ReportVersion,
                        order=order,
                        user=user,
                    )

                    _rb.audit(
                        'REPORT_FINALIZED',
                        'order',
                        order.id,
                        (
                            f'version={version.version_no}; '
                            f'by={username}; editor=BROWSER'
                        )
                    )

                    _rb.db.session.commit()

                    _rb.queue_final_delivery(order)

                    _rb.enqueue_event(
                        'REPORT_FINALIZED',
                        'order',
                        order.id,
                        {
                            'accession':order.accession
                        }
                    )

                    _rb.db.session.commit()

                    _rb.flash(
                        'Report finalized.',
                        'success'
                    )

            except Exception:
                _rb.db.session.rollback()

                eid=(
                    _rb._error_id()
                    if '_error_id' in _rb.namespace()
                    else 'REPORT-ERROR'
                )

                _rb.app.logger.exception(
                    'Web report workflow failed %s',
                    eid
                )

                _rb.flash(
                    f'Report action failed. Error ID: {eid}',
                    'danger'
                )

            return _rb.redirect(
                _rb.url_for(
                    'report_editor',
                    order_id=order.id
                )
            )

        history=(
            _rb.ReportVersion.query
            .filter_by(report_id=report.id)
            .order_by(_rb.ReportVersion.version_no.desc())
            .all()
        )

        latest_version_no=(
            int(history[0].version_no)
            if history
            else 0
        )

        import uuid as _uuid

        web_commit_id=str(_uuid.uuid4())
        upload_commit_id=str(_uuid.uuid4())

        word_templates=_rb.DoctorWordTemplate.query.filter(
            _rb.DoctorWordTemplate.active.is_(True),
            _rb.or_(
                _rb.DoctorWordTemplate.owner_user_id==_rb.current_user().id,
                _rb.DoctorWordTemplate.visibility.in_(
                    ['DEPARTMENT','SHARED']
                )
            ),
            _rb.or_(
                _rb.DoctorWordTemplate.modality=='',
                _rb.DoctorWordTemplate.modality==order.modality
            ),
            _rb.or_(
                _rb.DoctorWordTemplate.procedure_id.is_(None),
                _rb.DoctorWordTemplate.procedure_id==order.procedure_id
            )
        ).order_by(
            _rb.DoctorWordTemplate.created_at.desc()
        ).all()

        viewer=_rb.current_user()

        viewer_role=(
            viewer.role.code.upper()
            if viewer
            and viewer.role
            and viewer.role.code
            else ''
        )

        # Legacy FINAL->DRAFT reopen is intentionally disabled.
        # A future dedicated Addendum workflow must be used.
        can_admin_reopen=False

        return _rb.render_template(
            'report_editor.html',
            order=order,
            report=report,
            history=history,
            pacs_url=_rb.case_pacs_url(order),
            transitions=_rb.allowed_report_transitions(report),
            word_templates=word_templates,
            can_admin_reopen=can_admin_reopen,
            base_version_no=latest_version_no,
            web_commit_id=web_commit_id,
            upload_commit_id=upload_commit_id,
        )
    return report_editor


def install_0218(_rb):
    @_rb.app.route('/reports/<int:order_id>/word')
    @_rb.require_perm('reports.view')
    def word_template(order_id):
        order=_rb.Order.query.get_or_404(order_id)
        report=_rb.get_report(order)

        authoritative = _rb._rb_authoritative_docx_download(
            order,
            report,
        )

        if authoritative:
            return _rb.send_file(
                authoritative['path'],
                as_attachment=True,
                download_name=_rb.build_report_filename(
                    order,
                    authoritative['version_no'],
                    authoritative['status'],
                    'docx',
                ),
                mimetype=(
                    'application/vnd.openxmlformats-officedocument.'
                    'wordprocessingml.document'
                ),
            )

        version_no=_rb._next_report_version(report)

        try:
            doc=_rb.Document()
            section=doc.sections[0]
            header=section.header
            table=header.add_table(rows=5,cols=4,width=_rb.Inches(7.0))
            table.style='Table Grid'

            p=order.patient
            proc_name=(order.proc.name if order.proc else order.procedure) or ''
            ref_name=(order.referring_doctor.name if getattr(order,'referring_doctor',None) else '')

            values=[
                ('Patient Name',p.name or '','Patient ID',p.patient_id or ''),
                ('DOB',str(p.dob or ''),'Sex',p.sex or ''),
                ('Accession',order.accession or '','Modality',order.modality or ''),
                ('Exam',proc_name,'Study Date',str(order.scheduled or '')),
                ('Referring Doctor',ref_name,'Report Status',report.status or 'DRAFT'),
            ]
            for r,row in enumerate(values):
                for c,val in enumerate(row):
                    table.cell(r,c).text=str(val)

            doc.add_heading(proc_name or 'Radiology Report',level=1)
            doc.add_heading('Findings',level=2)
            doc.add_paragraph(report.findings or '')
            doc.add_heading('Impression',level=2)
            doc.add_paragraph(report.impression or '')
            if report.radiologist:
                doc.add_paragraph(f'Radiologist: {report.radiologist}')

            out=_rb.io.BytesIO()
            doc.save(out)
            out.seek(0)
            return _rb.send_file(
                out,as_attachment=True,
                download_name=_rb.build_report_filename(order,version_no,'DRAFT','docx'),
                mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
            )
        except Exception as exc:
            eid=_rb._error_id()
            _rb.app.logger.exception('Word generation failed %s',eid)
            _rb.flash(f'Word generation failed. Error ID: {eid}. You can still upload DOCX/ODT/PDF manually.','danger')
            return _rb.redirect(_rb.url_for('report_editor',order_id=order.id))
    return word_template


def install_0228(_rb):
    @_rb.app.route('/api/reporting/cases/<accession>')
    @_rb.require_reporting_api(write=False)
    def api_reporting_case(accession):
        order=_rb.Order.query.filter_by(accession=accession).first_or_404(); return _rb.jsonify(_rb.case_json(order,_rb.get_report(order)))
    return api_reporting_case


def install_0229(_rb):
    @_rb.app.post('/api/reporting/cases/<accession>/lease/acquire')
    @_rb.require_reporting_api(write=True)
    def api_reporting_lease_acquire(accession):
        import secrets

        order=_rb.Order.query.filter_by(
            accession=accession
        ).first_or_404()

        report=_rb.get_report(order)
        user=_rb.reporting_actor(accession)

        if not user:
            return _rb.jsonify({
                'ok': False,
                'error': 'REPORTING_ACTOR_REQUIRED'
            }), 403

        data=_rb.request.get_json(silent=True) or {}

        editor_type=str(
            data.get('editor_type') or 'WORD'
        ).strip().upper()

        supplied_token=str(
            data.get('lease_token') or
            _rb.request.headers.get('X-RadBridge-Report-Lease') or
            ''
        ).strip()

        lease_token=(
            supplied_token
            if supplied_token
            else secrets.token_urlsafe(32)
        )

        try:
            lease=_rb.acquire_or_renew_lease(
                db=_rb.db,
                order=order,
                report=report,
                user=user,
                editor_type=editor_type,
                lease_token=lease_token,
            )

            _rb.audit_as_user(user,
                'REPORT_EDIT_LEASE_ACQUIRED',
                'order',
                order.id,
                f'editor={editor_type}; user={user.id}'
            )

            _rb.db.session.commit()

            return _rb.jsonify({
                'ok': True,
                'lease_token': lease_token,
                'editor_type': lease.editor_type,
                'expires_at': lease.expires_at.isoformat(),
            })

        except _rb.ReportEditControlError as exc:
            _rb.db.session.rollback()

            code=getattr(
                exc,
                'code',
                type(exc).__name__
            )

            try:
                _rb.audit_as_user(user,
                    'REPORT_EDIT_LEASE_DENIED',
                    'order',
                    order.id,
                    f'editor={editor_type}; code={code}; user={user.id}'
                )
                _rb.db.session.commit()
            except Exception:
                _rb.db.session.rollback()

            return _rb.jsonify({
                'ok': False,
                'error': code,
            }), 409 if code in (
                'FINAL_REPORT_LOCKED',
                'REPORT_EDIT_LOCKED',
            ) else 403
    return api_reporting_lease_acquire


def install_0230(_rb):
    @_rb.app.post('/api/reporting/cases/<accession>/lease/release')
    @_rb.require_reporting_api(write=True)
    def api_reporting_lease_release(accession):
        order=_rb.Order.query.filter_by(
            accession=accession
        ).first_or_404()

        user=_rb.reporting_actor(accession)

        if not user:
            return _rb.jsonify({
                'ok': False,
                'error': 'REPORTING_ACTOR_REQUIRED'
            }), 403

        data=_rb.request.get_json(silent=True) or {}

        lease_token=str(
            data.get('lease_token') or
            _rb.request.headers.get('X-RadBridge-Report-Lease') or
            ''
        ).strip()

        if not lease_token:
            return _rb.jsonify({
                'ok': False,
                'error': 'REPORT_LEASE_TOKEN_REQUIRED'
            }), 400

        released=_rb.release_lease(
            db=_rb.db,
            order_id=order.id,
            user_id=user.id,
            lease_token=lease_token,
        )

        _rb.audit_as_user(user,
            'REPORT_EDIT_LEASE_RELEASED',
            'order',
            order.id,
            f'user={user.id}; released={released}'
        )

        _rb.db.session.commit()

        return _rb.jsonify({
            'ok': True,
            'released': released,
        })
    return api_reporting_lease_release


def install_0231(_rb):
    @_rb.app.route('/api/reporting/cases/<accession>/draft',methods=['POST'])
    @_rb.require_reporting_api(write=True)
    def api_reporting_draft(accession):
        import os

        from report_transaction_writer import (
            commit_report_version,
            TransactionalReportCommitError,
        )

        order=_rb.Order.query.filter_by(
            accession=accession
        ).first_or_404()

        report=_rb.get_report(order)
        user=_rb.reporting_actor(accession)

        if not user:
            return _rb.jsonify({
                'ok': False,
                'error': 'REPORTING_ACTOR_REQUIRED'
            }), 403

        try:
            _rb.assert_not_final(report)
            _rb.assert_role_allowed(user,'DRAFT')

            lease_token=str(
                _rb.request.form.get('lease_token') or
                _rb.request.headers.get('X-RadBridge-Report-Lease') or
                ''
            ).strip()

            _rb.assert_lease_owner(
                db=_rb.db,
                order=order,
                report=report,
                user=user,
                lease_token=lease_token,
            )

        except _rb.ReportEditControlError as exc:
            code=getattr(exc,'code',type(exc).__name__)

            try:
                _rb.audit(
                    'REPORT_EDIT_DENIED',
                    'order',
                    order.id,
                    f'action=DRAFT; editor=WORD_ADDIN; code={code}; user={user.id}'
                )
                _rb.db.session.commit()
            except Exception:
                _rb.db.session.rollback()

            return _rb.jsonify({
                'ok':False,
                'error':code,
            }), 409 if code in (
                'FINAL_REPORT_LOCKED',
                'REPORT_EDIT_LOCKED',
            ) else 403

        document=_rb.request.files.get('document')

        if 'base_version_no' not in _rb.request.form:
            return _rb.jsonify({
                'ok': False,
                'error': 'BASE_VERSION_REQUIRED'
            }), 400

        commit_id=str(
            _rb.request.form.get('commit_id')
            or ''
        ).strip()

        if not commit_id:
            return _rb.jsonify({
                'ok': False,
                'error': 'COMMIT_ID_REQUIRED'
            }), 400

        tmppath, validation, status_code = \
            _rb._ohif_validate_word_upload(
                order,
                document,
                final=False
            )

        if not tmppath:
            return _rb.jsonify(validation), status_code

        owned_artifact=None

        try:
            findings, impression, radiologist = \
                _rb.extract_docx_sections(tmppath)

            radiologist=str(
                (
                    radiologist
                    if radiologist
                    and radiologist != '____________________'
                    else (
                        getattr(user,'full_name',None)
                        or getattr(user,'username',None)
                        or report.radiologist
                        or ''
                    )
                )
            ).strip()

            result=commit_report_version(
                db=_rb.db,
                Report=_rb.Report,
                ReportVersion=_rb.ReportVersion,
                report_root=_rb.REPORT_DIR,
                order=order,
                patient=order.patient,
                user=user,
                editor_type='WORD',
                requested_status='DRAFT',
                source_file=tmppath,
                base_version_no=int(
                    _rb.request.form['base_version_no']
                ),
                commit_id=commit_id,
                findings=findings or '',
                impression=impression or '',
                radiologist=radiologist,
                change_summary='Word Add-in Draft',
            )

            version=result.get('version')

            if (
                version is not None
                and not result.get('retry')
            ):
                owned_artifact=version.docx_path

            if user:
                _rb.audit_as_user(
                    user,
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
                        'editor=WORD; '
                        f'commit_id={commit_id}'
                    )
                )

            _rb.db.session.commit()

            return _rb.jsonify({
                'ok': True,
                'status': 'DRAFT',
                'version_no': (
                    version.version_no
                    if version is not None
                    else None
                ),
                'editor_type': 'WORD',
                'retry': bool(result.get('retry')),
            })

        except TransactionalReportCommitError as exc:
            _rb.db.session.rollback()

            if owned_artifact:
                try:
                    os.unlink(owned_artifact)
                except FileNotFoundError:
                    pass

            return _rb.jsonify({
                'ok': False,
                'error': getattr(
                    exc,
                    'code',
                    type(exc).__name__
                ),
                'message': str(exc)
            }), 409

        except Exception as exc:
            _rb.db.session.rollback()

            if owned_artifact:
                try:
                    os.unlink(owned_artifact)
                except FileNotFoundError:
                    pass

            return _rb.jsonify({
                'ok': False,
                'error': type(exc).__name__,
                'message': str(exc)
            }), 400

        finally:
            if tmppath:
                try:
                    os.unlink(tmppath)
                except FileNotFoundError:
                    pass

                try:
                    os.rmdir(
                        os.path.dirname(tmppath)
                    )
                except OSError:
                    pass
    return api_reporting_draft


def install_0232(_rb):
    @_rb.app.post('/api/reporting/cases/<accession>/verify')
    @_rb.require_reporting_api(write=True)
    def api_reporting_verify(accession):
        order=_rb.Order.query.filter_by(
            accession=accession
        ).first_or_404()

        report=_rb.get_report(order)
        user=_rb.reporting_actor(accession)

        if not user:
            return _rb.jsonify({
                'ok': False,
                'error': 'REPORTING_ACTOR_REQUIRED'
            }), 403

        try:
            _rb.assert_not_final(report)
            _rb.assert_role_allowed(user,'VERIFY')
            _rb.assert_no_foreign_active_lease(
                db=_rb.db,
                order_id=order.id,
                user=user,
            )

        except _rb.ReportEditControlError as exc:
            code=getattr(exc,'code',type(exc).__name__)

            try:
                _rb.audit(
                    'REPORT_EDIT_DENIED',
                    'order',
                    order.id,
                    f'action=VERIFY; editor=WORD_ADDIN; code={code}; user={user.id}'
                )
                _rb.db.session.commit()
            except Exception:
                _rb.db.session.rollback()

            return _rb.jsonify({
                'ok':False,
                'error':code,
            }), 409 if code in {'FINAL_REPORT_LOCKED','REPORT_EDIT_LOCKED'} else 403

        report=_rb.get_report(order)

        if (
            (report.status or '').upper() == 'FINAL'
        ):
            return _rb.jsonify({
                'ok': False,
                'error': 'FINAL_REPORT_LOCKED'
            }), 409

        if 'base_version_no' not in _rb.request.form:
            return _rb.jsonify({
                'ok': False,
                'error': 'BASE_VERSION_REQUIRED'
            }), 400

        latest=_rb._rb_latest_report_version(report)

        if latest is None:
            return _rb.jsonify({
                'ok': False,
                'error': 'NO_REPORT_VERSION'
            }), 409

        if str(latest.editor_type or '').upper() != 'WORD':
            return _rb.jsonify({
                'ok': False,
                'error': 'LATEST_VERSION_NOT_WORD',
                'version_no': latest.version_no,
                'editor_type': latest.editor_type
            }), 409

        if (latest.status or '').upper() != 'DRAFT':
            return _rb.jsonify({
                'ok': False,
                'error': 'REPORT_VERIFY_CONFLICT',
                'message': 'VERSION_ALREADY_VERIFIED'
            }), 409

        demographic_ok, demographic_reason = \
            _rb.pacs_demographic_gate(order)

        if not demographic_ok:
            return _rb.jsonify({
                'ok': False,
                'error': 'PACS_DEMOGRAPHIC_REVIEW_REQUIRED',
                'reason': demographic_reason
            }), 409

        try:
            from report_commit_core import (
                validate_base_version,
            )

            from onlyoffice_report_bridge import (
                onlyoffice_verify_latest,
            )

            validate_base_version(
                current_version_no=int(latest.version_no),
                base_version_no=int(
                    _rb.request.form['base_version_no']
                ),
            )

            before_count=(
                _rb.ReportVersion.query
                .filter_by(report_id=report.id)
                .count()
            )

            before_id=latest.id
            before_sha=latest.sha256
            before_path=latest.docx_path

            version=onlyoffice_verify_latest(
                db=_rb.db,
                Report=_rb.Report,
                ReportVersion=_rb.ReportVersion,
                order=order,
                user=user,
            )

            after_count=(
                _rb.ReportVersion.query
                .filter_by(report_id=report.id)
                .count()
            )

            if after_count != before_count:
                _rb.db.session.rollback()
                raise RuntimeError(
                    'VERIFY_CREATED_EXTRA_VERSION'
                )

            if version.id != before_id:
                _rb.db.session.rollback()
                raise RuntimeError(
                    'VERIFY_CHANGED_VERSION_ID'
                )

            if version.sha256 != before_sha:
                _rb.db.session.rollback()
                raise RuntimeError(
                    'VERIFY_CHANGED_CONTENT_SHA'
                )

            if version.docx_path != before_path:
                _rb.db.session.rollback()
                raise RuntimeError(
                    'VERIFY_CHANGED_DOCUMENT_PATH'
                )

            if user:
                _rb.audit_as_user(
                    user,
                    'REPORT_VERIFIED',
                    'order',
                    order.id,
                    (
                        f'version={version.version_no}; '
                        'editor=WORD_ADDIN; '
                        'content_immutable=YES'
                    )
                )

            _rb.db.session.commit()

            return _rb.jsonify({
                'ok': True,
                'status': 'VERIFIED',
                'version_no': version.version_no,
                'editor_type': 'WORD',
                'authoritative': True
            })

        except Exception as exc:
            _rb.db.session.rollback()

            code=getattr(
                exc,
                'code',
                type(exc).__name__
            )

            conflict_codes={
                'REPORT_VERSION_CONFLICT',
                'REPORT_VERIFY_CONFLICT',
                'VERSION_ALREADY_VERIFIED',
            }

            return _rb.jsonify({
                'ok': False,
                'error': code,
                'message': str(exc)
            }), (409 if code in conflict_codes else 400)
    return api_reporting_verify


def install_0233(_rb):
    @_rb.app.route('/api/reporting/cases/<accession>/finalize',methods=['POST'])
    @_rb.require_reporting_api(write=True)
    def api_reporting_finalize(accession):
        order=_rb.Order.query.filter_by(
            accession=accession
        ).first_or_404()

        report=_rb.get_report(order)
        user=_rb.reporting_actor(accession)

        if not user:
            return _rb.jsonify({
                'ok': False,
                'error': 'REPORTING_ACTOR_REQUIRED'
            }), 403

        try:
            _rb.assert_not_final(report)
            _rb.assert_role_allowed(user,'FINALIZE')
            _rb.assert_no_foreign_active_lease(
                db=_rb.db,
                order_id=order.id,
                user=user,
            )

        except _rb.ReportEditControlError as exc:
            code=getattr(exc,'code',type(exc).__name__)

            try:
                _rb.audit(
                    'REPORT_EDIT_DENIED',
                    'order',
                    order.id,
                    f'action=FINALIZE; editor=WORD_ADDIN; code={code}; user={user.id}'
                )
                _rb.db.session.commit()
            except Exception:
                _rb.db.session.rollback()

            return _rb.jsonify({
                'ok':False,
                'error':code,
            }), 409 if code in {'FINAL_REPORT_LOCKED','REPORT_EDIT_LOCKED'} else 403

        report=_rb.get_report(order)

        demographic_ok, demographic_reason = \
            _rb.pacs_demographic_gate(order)

        if not demographic_ok:
            return _rb.jsonify({
                'ok': False,
                'error': 'PACS_DEMOGRAPHIC_REVIEW_REQUIRED',
                'reason': demographic_reason
            }), 409

        if 'base_version_no' not in _rb.request.form:
            return _rb.jsonify({
                'ok': False,
                'error': 'BASE_VERSION_REQUIRED'
            }), 400

        latest=_rb._rb_latest_report_version(report)

        if latest is None:
            return _rb.jsonify({
                'ok': False,
                'error': 'NO_REPORT_VERSION'
            }), 409

        if str(latest.editor_type or '').upper() != 'WORD':
            return _rb.jsonify({
                'ok': False,
                'error': 'LATEST_VERSION_NOT_WORD',
                'version_no': latest.version_no,
                'editor_type': latest.editor_type
            }), 409

        if (
            (report.status or '').upper() == 'FINAL'
            or latest.finalized_at is not None
        ):
            return _rb.jsonify({
                'ok': False,
                'error': 'FINAL_REPORT_LOCKED'
            }), 409

        if (latest.status or '').upper() != 'VERIFIED':
            return _rb.jsonify({
                'ok': False,
                'error': 'LATEST_VERSION_NOT_VERIFIED',
                'version_no': latest.version_no,
                'status': latest.status
            }), 409

        try:
            from report_commit_core import (
                validate_base_version,
            )

            from onlyoffice_report_bridge import (
                onlyoffice_finalize_latest,
            )

            validate_base_version(
                current_version_no=int(latest.version_no),
                base_version_no=int(
                    _rb.request.form['base_version_no']
                ),
            )

            before_count=(
                _rb.ReportVersion.query
                .filter_by(report_id=report.id)
                .count()
            )

            version=onlyoffice_finalize_latest(
                db=_rb.db,
                Report=_rb.Report,
                ReportVersion=_rb.ReportVersion,
                order=order,
                user=user,
            )

            after_count=(
                _rb.ReportVersion.query
                .filter_by(report_id=report.id)
                .count()
            )

            if after_count != before_count:
                _rb.db.session.rollback()
                raise RuntimeError(
                    'FINALIZE_CREATED_EXTRA_VERSION'
                )

            if user:
                _rb.audit_as_user(
                    user,
                    'REPORT_FINALIZED',
                    'order',
                    order.id,
                    (
                        f'version={version.version_no}; '
                        'editor=WORD_ADDIN; '
                        'content_immutable=YES'
                    )
                )

            _rb.db.session.commit()

            _rb.queue_final_delivery(order)

            _rb.enqueue_event(
                'REPORT_FINALIZED',
                'order',
                order.id,
                {
                    'accession': order.accession,
                    'version_no': version.version_no,
                    'source': 'WORD_ADDIN'
                }
            )

            _rb.db.session.commit()

            return _rb.jsonify({
                'ok': True,
                'status': 'FINALIZED',
                'version_no': version.version_no,
                'editor_type': 'WORD',
                'authoritative': True
            })

        except Exception as exc:
            _rb.db.session.rollback()

            code=getattr(
                exc,
                'code',
                type(exc).__name__
            )

            status=409 if code in (
                'REPORT_VERSION_CONFLICT',
                'REPORT_VERSION_DUPLICATE',
                'REPORT_FINALIZE_CONFLICT',
            ) else 400

            return _rb.jsonify({
                'ok': False,
                'error': code,
                'message': str(exc)
            }), status
    return api_reporting_finalize


def install_0468(_rb):
    @_rb.app.route('/reports/<int:order_id>/upload',methods=['POST'])
    @_rb.require_perm('reports.edit')
    def report_upload(order_id):
        order=_rb.Order.query.get_or_404(order_id)
        report=_rb.get_report(order)
        user=_rb.current_user()

        try:
            _rb.assert_not_final(report)
            _rb.assert_role_allowed(user,'DRAFT')

            lease_token=str(
                _rb.request.form.get('lease_token') or
                _rb.request.headers.get('X-RadBridge-Report-Lease') or
                ''
            ).strip()

            _rb.assert_lease_owner(
                db=_rb.db,
                order=order,
                report=report,
                user=user,
                lease_token=lease_token,
            )

        except _rb.ReportEditControlError as exc:
            code=getattr(exc,'code',type(exc).__name__)

            try:
                _rb.audit(
                    'REPORT_EDIT_DENIED',
                    'order',
                    order.id,
                    f'action=DRAFT; editor=UPLOAD; code={code}; user={user.id}'
                )
                _rb.db.session.commit()
            except Exception:
                _rb.db.session.rollback()

            _rb.flash(
                'Report upload is currently blocked.',
                'danger'
            )

            return _rb.redirect(
                _rb.url_for('report_editor',order_id=order.id)
            )

        if (report.status or '').upper()=='FINAL':
            _rb.flash(
                'This report is FINAL. '
                'A dedicated Addendum workflow is required.',
                'danger'
            )
            return _rb.redirect(
                _rb.url_for('report_editor',order_id=order.id)
            )

        # Upload is content ingestion only.
        # Verification and Finalization are separate explicit actions.
        target=_rb.request.form.get(
            'action',
            'DRAFT'
        ).upper().strip()

        if target!='DRAFT':
            _rb.flash(
                'Manual upload can create a DRAFT only. '
                'Verify and Finalize separately.',
                'danger'
            )
            return _rb.redirect(
                _rb.url_for('report_editor',order_id=order.id)
            )

        f=_rb.request.files.get('document')

        if not f or not f.filename:
            _rb.flash(
                'Choose a report file first.',
                'danger'
            )
            return _rb.redirect(
                _rb.url_for('report_editor',order_id=order.id)
            )

        # Unified writer is currently validated for DOCX clinical content.
        ext=_rb.os.path.splitext(
            f.filename
        )[1].lower()

        if ext!='.docx':
            _rb.flash(
                'Manual unified upload currently accepts DOCX only.',
                'danger'
            )
            return _rb.redirect(
                _rb.url_for('report_editor',order_id=order.id)
            )

        base_raw=_rb.request.form.get(
            'base_version_no',
            ''
        ).strip()

        commit_id=_rb.request.form.get(
            'commit_id',
            ''
        ).strip()

        if not base_raw or not commit_id:
            _rb.flash(
                'Report version context is missing. Reload the report.',
                'danger'
            )
            return _rb.redirect(
                _rb.url_for('report_editor',order_id=order.id)
            )

        try:
            base_version_no=int(base_raw)
        except Exception:
            _rb.flash(
                'Invalid report version context. Reload the report.',
                'danger'
            )
            return _rb.redirect(
                _rb.url_for('report_editor',order_id=order.id)
            )

        tmpdir=_rb.tempfile.mkdtemp(
            prefix='ris-upload-'
        )

        tmppath=_rb.os.path.join(
            tmpdir,
            'upload.docx'
        )

        try:
            f.save(tmppath)

            safety=_rb.validate_report_patient_file(
                order,
                tmppath,
                ext
            )

            _rb.audit(
                'REPORT_PATIENT_SAFETY',
                'order',
                order.id,
                (
                    f'{safety["result"]} '
                    f'expected_pid={safety["expected_patient_id"]} '
                    f'found_pid={safety["found_patient_id"]} '
                    f'expected_acc={safety["expected_accession"]} '
                    f'found_acc={safety["found_accession"]}'
                )
            )

            _rb.db.session.commit()

            if safety['result']=='BLOCKED':
                _rb.flash(
                    'PATIENT MISMATCH — upload blocked.',
                    'danger'
                )
                return _rb.redirect(
                    _rb.url_for(
                        'report_editor',
                        order_id=order.id
                    )
                )

            override=(
                _rb.request.form.get(
                    'safety_override'
                )=='1'
            )

            if (
                safety['result']=='WARNING'
                and not override
            ):
                _rb.flash(
                    'Patient safety warning — review the '
                    'document identifiers and confirm before upload.',
                    'warning'
                )
                return _rb.redirect(
                    _rb.url_for(
                        'report_editor',
                        order_id=order.id
                    )
                )

            latest=(
                _rb.ReportVersion.query
                .filter_by(report_id=report.id)
                .order_by(_rb.ReportVersion.version_no.desc())
                .first()
            )

            latest_no=(
                int(latest.version_no)
                if latest
                else 0
            )

            if base_version_no != latest_no:
                _rb.flash(
                    'This report changed after the page was opened. '
                    'Reload before uploading.',
                    'danger'
                )
                return _rb.redirect(
                    _rb.url_for(
                        'report_editor',
                        order_id=order.id
                    )
                )

            findings,impression,radiologist = \
                _rb.extract_docx_sections(tmppath)

            user=_rb.current_user()

            if not user:
                _rb.abort(403)

            from report_transaction_writer import \
                commit_report_version

            result=commit_report_version(
                db=_rb.db,
                Report=_rb.Report,
                ReportVersion=_rb.ReportVersion,
                report_root=_rb.REPORT_DIR,
                order=order,
                patient=order.patient,
                user=user,
                editor_type='UPLOAD',
                requested_status='DRAFT',
                source_file=tmppath,
                base_version_no=base_version_no,
                commit_id=commit_id,
                findings=findings or '',
                impression=impression or '',
                radiologist=(
                    radiologist
                    or user.full_name
                    or user.username
                    or 'Unknown'
                ),
                change_summary='Manual DOCX Upload Draft',
            )

            _rb.audit(
                'REPORT_UPLOAD_DRAFT',
                'order',
                order.id,
                (
                    f'version={result.get("version_no")}; '
                    f'patient_safety={safety["result"]}; '
                    f'commit_id={commit_id}'
                )
            )

            _rb.db.session.commit()

            _rb.flash(
                'Report uploaded as DRAFT. '
                'Verify and Finalize separately.',
                'success'
            )

            return _rb.redirect(
                _rb.url_for(
                    'report_editor',
                    order_id=order.id
                )
            )

        except Exception:
            _rb.db.session.rollback()

            eid=(
                _rb._error_id()
                if '_error_id' in _rb.namespace()
                else 'UPLOAD-ERROR'
            )

            _rb.app.logger.exception(
                'Report upload failed %s',
                eid
            )

            _rb.flash(
                f'Report upload failed. Error ID: {eid}',
                'danger'
            )

            return _rb.redirect(
                _rb.url_for(
                    'report_editor',
                    order_id=order.id
                )
            )

        finally:
            _rb.shutil.rmtree(
                tmpdir,
                ignore_errors=True
            )
    return report_upload


def install_0469(_rb):
    @_rb.app.route('/reports/<int:order_id>/source')
    @_rb.require_perm('reports.view')
    def report_source(order_id):
        order=_rb.Order.query.get_or_404(order_id)
        report=_rb.Report.query.filter_by(order_id=order.id).first()
        if not report:
            _rb.abort(404)

        # Public/source download is FINAL-only. Draft/verified working copies
        # stay inside their authenticated editor/version endpoints.
        if not _rb.report_source_allowed(report.status):
            _rb.abort(409,'Report source is available only after FINAL.')

        path=report.source_path or report.docx_path or report.pdf_path

        if not path or not _rb.os.path.exists(path):
            _rb.abort(404)

        ext=_rb.os.path.splitext(path)[1].lstrip('.') or 'bin'
        history=_rb.ReportVersion.query.filter_by(report_id=report.id).order_by(_rb.ReportVersion.version_no.desc()).all()
        version_no=history[0].version_no if history else 1
        filename=_rb.report_filename(order,version_no,report.status,ext)
        return _rb.send_file(path,as_attachment=True,download_name=filename)
    return report_source


def install_0526(_rb):
    @_rb.app.route('/accounting/reports')
    @_rb.require_perm('financial.view')
    def accounting_reports():
        start=_rb.request.args.get('start','').strip()
        end=_rb.request.args.get('end','').strip()
        branch_id=_rb.request.args.get('branch_id',type=int)
        q=_rb.Order.query
        if start: q=q.filter(_rb.Order.scheduled>=_rb.datetime.fromisoformat(start))
        if end: q=q.filter(_rb.Order.scheduled<_rb.datetime.fromisoformat(end)+_rb.timedelta(days=1))
        if branch_id: q=q.filter(_rb.Order.branch_id==branch_id)
        rows=q.order_by(_rb.Order.scheduled.desc()).all()
        gross=sum(float(o.contract_price or o.gross_price or 0) for o in rows)
        patient_share=sum(float(o.patient_share or 0) for o in rows)
        company_share=sum(float(o.company_share or 0) for o in rows)
        collected=sum(float(o.paid_amount or 0) for o in rows)
        balance=sum(max(_rb.order_balance(o),0) for o in rows)
        cash=visa=wallet=bank=0
        receipts=[]
        ids=[o.id for o in rows]
        if ids:
            receipts=_rb.Receipt.query.filter(_rb.Receipt.order_id.in_(ids)).all()
        for r in receipts:
            val=float(r.amount or 0)
            m=(r.payment_method or '').upper()
            if m=='CASH': cash+=val
            elif m in ('VISA','MASTERCARD','CARD'): visa+=val
            elif m=='WALLET': wallet+=val
            else: bank+=val
        report_only=sum(1 for o in rows if o.report_delivered and not o.images_delivered)
        images_only=sum(1 for o in rows if o.images_delivered and not o.report_delivered)
        both=sum(1 for o in rows if o.report_delivered and o.images_delivered)
        none=sum(1 for o in rows if not o.report_delivered and not o.images_delivered)
        return _rb.render_template('accounting_reports.html',rows=rows,gross=gross,patient_share=patient_share,
            company_share=company_share,collected=collected,balance=balance,cash=cash,visa=visa,wallet=wallet,bank=bank,
            report_only=report_only,images_only=images_only,both=both,none=none,
            branches=_rb.Branch.query.order_by(_rb.Branch.name).all())
    return accounting_reports


def install_0527(_rb):
    @_rb.app.route('/accounting/reports.csv')
    @_rb.require_perm('export.view')
    def accounting_reports_csv():
        s=_rb.io.StringIO(); w=_rb.csv.writer(s)
        w.writerow(['Accession','Patient','Procedure','Gross/Contract','Patient Share','Company Share','Paid','Balance','Report Delivered','Images Delivered','Status'])
        for o in _rb.Order.query.order_by(_rb.Order.scheduled.desc()).all():
            w.writerow([o.accession,o.patient.name,o.proc.name if o.proc else o.procedure,
                o.contract_price or o.gross_price or 0,o.patient_share or 0,o.company_share or 0,o.paid_amount or 0,
                _rb.order_balance(o),'YES' if o.report_delivered else 'NO','YES' if o.images_delivered else 'NO',o.status])
        return _rb.send_file(_rb.io.BytesIO(s.getvalue().encode('utf-8-sig')),as_attachment=True,
            download_name='accounting-report.csv',mimetype='text/csv; charset=utf-8')
    return accounting_reports_csv


def install_0530(_rb):
    @_rb.app.route('/admin/demo/reporting',methods=['GET','POST'])
    @_rb.require_perm('users.view')
    def admin_reporting_demo():
        if _rb.request.method=='POST':
            rows=_rb.create_reporting_demo_cases()
            _rb.flash(f'{len(rows)} demo cases are ready.','success')
            return _rb.redirect(_rb.url_for('doctor_workspace'))
        return _rb.render_template('demo_reporting.html')
    return admin_reporting_demo


def install_0545(_rb):
    @_rb.app.route('/assignment/unassigned')
    @_rb.require_perm('reports.view')
    def unassigned_cases():
        from registration_policy import allowed_registration_branches
        allowed_branches=allowed_registration_branches()
        branch_id=_rb.request.args.get('branch_id',type=int)
        specialty=(_rb.request.args.get('specialty') or '').strip()
        modality=(_rb.request.args.get('modality') or '').strip().upper()
        priority=(_rb.request.args.get('priority') or '').strip().upper()
        readiness_filter=(_rb.request.args.get('readiness') or '').strip().upper()
        sla_filter=(_rb.request.args.get('sla') or '').strip().upper()
        search=(_rb.request.args.get('q') or '').strip()

        scoped_orders=_rb.Order.query
        if allowed_branches is not None:
            scoped_orders=(scoped_orders.filter(_rb.Order.branch_id.in_(allowed_branches))
                           if allowed_branches else scoped_orders.filter(_rb.db.false()))
        if branch_id and allowed_branches is not None and branch_id not in allowed_branches:
            _rb.abort(403)

        query=scoped_orders.join(_rb.Patient).filter(
            _rb.Order.assigned_doctor_id.is_(None),
            _rb.Order.status.notin_(['FINAL','CANCELLED'])
        )
        if branch_id:
            query=query.filter(_rb.Order.branch_id==branch_id)
        if modality:
            query=query.filter(_rb.db.func.upper(_rb.Order.modality)==modality)
        if priority:
            query=query.filter(_rb.db.func.upper(_rb.Order.priority)==priority)
        if specialty:
            query=query.outerjoin(_rb.Procedure,_rb.Order.procedure_id==_rb.Procedure.id).filter(
                _rb.Procedure.category==specialty
            )
        if search:
            like=f'%{search}%'
            query=query.filter(_rb.or_(
                _rb.Patient.name.ilike(like),_rb.Patient.patient_id.ilike(like),
                _rb.Order.accession.ilike(like),_rb.Order.procedure.ilike(like)
            ))

        orders=query.order_by(
            _rb.db.case(
                (_rb.Order.priority=='STAT',0),
                (_rb.Order.priority=='URGENT',1),
                else_=2
            ),
            _rb.Order.scheduled.asc()
        ).limit(500).all()

        readiness_by_order={
            row.order_id:row for row in _rb.CaseReadiness.query.filter(
                _rb.CaseReadiness.order_id.in_([o.id for o in orders])
            ).all()
        } if orders else {}
        policies=_rb.TATPolicy.query.filter_by(active=True).all()
        now=_rb.datetime.utcnow()
        rows=[]
        for order in orders:
            readiness=readiness_by_order.get(order.id)
            snapshot=_rb.unassigned_case_snapshot(order,readiness,policies,now)
            if readiness_filter and snapshot['readiness_status']!=readiness_filter:
                continue
            if sla_filter and snapshot['sla']['status']!=sla_filter:
                continue
            rows.append(snapshot)

        doctors=_rb.assignable_doctors()
        if allowed_branches is not None:
            doctors=[doctor for doctor in doctors if doctor.branch_id in allowed_branches]
        branches=_rb.Branch.query.filter_by(active=True)
        if allowed_branches is not None:
            branches=branches.filter(_rb.Branch.id.in_(allowed_branches))
        specialties=(scoped_orders.join(_rb.Procedure,_rb.Order.procedure_id==_rb.Procedure.id)
            .filter(_rb.Procedure.active.is_(True),_rb.Procedure.category!='')
            .with_entities(_rb.Procedure.category).distinct().order_by(_rb.Procedure.category).all())
        modalities=(scoped_orders.filter(_rb.Order.modality.isnot(None),_rb.Order.modality!='')
            .with_entities(_rb.Order.modality).distinct().order_by(_rb.Order.modality).all())
        return _rb.render_template(
            'unassigned_cases.html',rows=rows,doctors=doctors,
            branches=branches.order_by(_rb.Branch.name).all(),
            specialties=[x[0] for x in specialties],
            modalities=[x[0] for x in modalities],
            filters={
                'branch_id':branch_id,'specialty':specialty,'modality':modality,
                'priority':priority,'readiness':readiness_filter,
                'sla':sla_filter,'q':search,
            }
        )
    return unassigned_cases


def install_0598(_rb):
    @_rb.app.post(
        '/admin/cancellation-center/order/<int:order_id>/delete-reports'
    )
    @_rb.require_perm('data.cancel.case')
    def granular_delete_order_reports_only(order_id):
        order=_rb.Order.query.get_or_404(order_id)
        user=_rb.current_user()
        if not _rb._delete_reports_only_is_super_admin(user):
            _rb.abort(403)

        reason=(_rb.request.form.get('reason') or '').strip()
        typed_accession=(
            _rb.request.form.get('confirm_accession')
            or ''
        ).strip()

        return _rb.granular_delete_reports_only_execute(
            order,
            typed_accession,
            reason,
        )
    return granular_delete_order_reports_only


def install_0658(_rb):
    @_rb.app.get('/reports/<int:order_id>/word-template/<int:template_id>')
    @_rb.require_perm('reports.view')
    def report_word_from_doctor_template(order_id,template_id):
        order=_rb.Order.query.get_or_404(order_id)
        tpl=_rb.DoctorWordTemplate.query.get_or_404(template_id)
        if not tpl.active: _rb.abort(404)
        if tpl.visibility=='PERSONAL' and tpl.owner_user_id!=_rb.current_user().id and not _rb.has_perm('*'):
            _rb.abort(403)
        if tpl.procedure_id and tpl.procedure_id!=order.procedure_id:
            _rb.abort(400)
        if tpl.modality and tpl.modality.upper()!=str(order.modality or '').upper():
            _rb.abort(400)
        report=_rb.get_report(order)

        authoritative = _rb._rb_authoritative_docx_download(
            order,
            report,
        )

        if authoritative:
            return _rb.send_file(
                authoritative['path'],
                as_attachment=True,
                download_name=_rb.build_report_filename(
                    order,
                    authoritative['version_no'],
                    authoritative['status'],
                    'docx',
                ),
                mimetype=(
                    'application/vnd.openxmlformats-officedocument.'
                    'wordprocessingml.document'
                ),
            )

        doc=_rb.Document(tpl.file_path)
        values={
          'PATIENT_NAME':order.patient.name,
          'PATIENT_ID':order.patient.patient_id,
          'DOB':order.patient.dob or '',
          'SEX':order.patient.sex or '',
          'ACCESSION':order.accession,
          'MODALITY':order.modality,
          'EXAM':order.procedure,
          'STUDY_DATE':order.scheduled or '',
          'REFERRING_DOCTOR':order.referring_doctor.name if getattr(order,'referring_doctor',None) else '',
          'RADIOLOGIST':report.radiologist or '',
          'FINDINGS':report.findings or '',
          'IMPRESSION':report.impression or ''
        }
        _rb.replace_docx_placeholders(doc,values)
        out=_rb.io.BytesIO(); doc.save(out); out.seek(0)
        return _rb.send_file(out,as_attachment=True,
          download_name=_rb.build_report_filename(order,_rb._next_report_version(report),'DRAFT','docx'),
          mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document')
    return report_word_from_doctor_template


def install_0659(_rb):
    @_rb.app.route('/admin/ai-reporting',methods=['GET','POST'])
    @_rb.require_perm('users.view')
    def admin_ai_reporting():
        row=_rb.AIProviderSetting.query.order_by(_rb.AIProviderSetting.id).first()
        if _rb.request.method=='POST':
            if not row:
                row=_rb.AIProviderSetting(provider_key='GENERIC_REST');_rb.db.session.add(row)
            row.enabled=_rb.request.form.get('enabled')=='1'
            row.provider_key=(_rb.request.form.get('provider_key') or 'GENERIC_REST').strip().upper()
            row.base_url=(_rb.request.form.get('base_url') or '').strip()
            row.model_name=(_rb.request.form.get('model_name') or '').strip()
            row.timeout_seconds=_rb.request.form.get('timeout_seconds',type=int) or 60
            row.updated_by=_rb.current_user().id
            _rb.db.session.commit()
            return _rb.redirect(_rb.url_for('admin_ai_reporting'))
        return _rb.render_template('admin_ai_reporting.html',row=row)
    return admin_ai_reporting


def install_0660(_rb):
    @_rb.app.get('/reports/<int:order_id>/ai-assistant')
    @_rb.require_perm('reports.view')
    def ai_report_assistant(order_id):
        order=_rb.Order.query.get_or_404(order_id)
        drafts=_rb.AIDraftReport.query.filter_by(order_id=order.id).order_by(_rb.AIDraftReport.created_at.desc()).limit(20).all()
        sel=_rb.PriorStudySelection.query.filter_by(order_id=order.id).all()
        return _rb.render_template('ai_report_assistant.html',order=order,drafts=drafts,
          ris_priors=_rb.related_prior_orders(order),external_priors=_rb.external_priors_for_order(order),
          selected_ris={x.prior_order_id for x in sel if x.prior_order_id},
          selected_ext={x.external_prior_id for x in sel if x.external_prior_id},
          provider=_rb.ai_provider_setting())
    return ai_report_assistant


def install_0661(_rb):
    @_rb.app.post('/reports/<int:order_id>/ai-assistant/generate')
    @_rb.require_perm('reports.edit')
    def ai_report_generate(order_id):
        order=_rb.Order.query.get_or_404(order_id)
        result,error=_rb.call_configured_ai_provider(order)
        if not result:
            _rb.flash('AI draft not generated: '+error,'danger')
            return _rb.redirect(_rb.url_for('ai_report_assistant',order_id=order.id))
        cfg=_rb.ai_provider_setting()
        row=_rb.AIDraftReport(order_id=order.id,provider_key=cfg.provider_key,model_name=cfg.model_name,
          input_context=_rb.json.dumps(_rb.generate_ai_draft_payload(order),ensure_ascii=False,default=str),
          findings_draft=result['findings'],impression_draft=result['impression'],
          comparison_draft=result['comparison'],safety_notes=result['safety_notes'],
          created_by=_rb.current_user().id)
        _rb.db.session.add(row);_rb.audit('AI_REPORT_DRAFT_GENERATED','order',order.id,f'draft={row.id}');_rb.db.session.commit()
        return _rb.redirect(_rb.url_for('ai_report_assistant',order_id=order.id))
    return ai_report_generate


def install_0662(_rb):
    @_rb.app.post('/reports/<int:order_id>/ai-assistant/<int:draft_id>/apply')
    @_rb.require_perm('reports.edit')
    def ai_report_apply(order_id,draft_id):
        order=_rb.Order.query.get_or_404(order_id)
        draft=_rb.AIDraftReport.query.filter_by(id=draft_id,order_id=order.id).first_or_404()
        report=_rb.get_report(order)
        report.findings=draft.findings_draft;report.impression=draft.impression_draft
        draft.status='ACCEPTED';draft.reviewed_by=_rb.current_user().id;draft.reviewed_at=_rb.datetime.utcnow()
        _rb.audit('AI_REPORT_DRAFT_APPLIED','order',order.id,f'draft={draft.id}');_rb.db.session.commit()
        _rb.flash('AI draft copied to editable report. Doctor review is required.','success')
        return _rb.redirect(_rb.url_for('report_editor',order_id=order.id))
    return ai_report_apply


def install_0663(_rb):
    @_rb.app.post('/reports/<int:order_id>/ai-assistant/<int:draft_id>/reject')
    @_rb.require_perm('reports.edit')
    def ai_report_reject(order_id,draft_id):
        d=_rb.AIDraftReport.query.filter_by(id=draft_id,order_id=order_id).first_or_404()
        d.status='REJECTED';d.reviewed_by=_rb.current_user().id;d.reviewed_at=_rb.datetime.utcnow();_rb.db.session.commit()
        return _rb.redirect(_rb.url_for('ai_report_assistant',order_id=order_id))
    return ai_report_reject


def install_0664(_rb):
    @_rb.app.post('/reports/<int:order_id>/priors/select')
    @_rb.require_perm('reports.view')
    def report_prior_select(order_id):
        po=_rb.request.form.get('prior_order_id',type=int); ex=_rb.request.form.get('external_prior_id',type=int)
        if bool(po)==bool(ex): _rb.abort(400)
        row=_rb.PriorStudySelection.query.filter_by(order_id=order_id,prior_order_id=po,external_prior_id=ex).first()
        if not row:
            row=_rb.PriorStudySelection(order_id=order_id,prior_order_id=po,external_prior_id=ex,selected_by=_rb.current_user().id)
            _rb.db.session.add(row)
        row.include_in_ai=True;_rb.db.session.commit()
        return _rb.redirect(_rb.request.referrer or _rb.url_for('ai_report_assistant',order_id=order_id))
    return report_prior_select


def install_0666(_rb):
    @_rb.app.post('/external-priors/<int:prior_id>/confirm-match')
    @_rb.require_perm('reports.view')
    def external_prior_confirm_match(prior_id):
        row=_rb.ExternalPriorStudy.query.get_or_404(prior_id);row.match_status='MATCH';_rb.db.session.commit()
        return _rb.redirect(_rb.request.referrer or _rb.url_for('patient_external_priors',patient_id=row.patient_id))
    return external_prior_confirm_match


def install_0667(_rb):
    @_rb.app.post('/external-priors/<int:prior_id>/mark-mismatch')
    @_rb.require_perm('reports.view')
    def external_prior_mark_mismatch(prior_id):
        row=_rb.ExternalPriorStudy.query.get_or_404(prior_id);row.match_status='MISMATCH';_rb.db.session.commit()
        return _rb.redirect(_rb.request.referrer or _rb.url_for('patient_external_priors',patient_id=row.patient_id))
    return external_prior_mark_mismatch


def install_0675(_rb):
    @_rb.app.get('/reports/<int:order_id>/imaging-ai')
    @_rb.require_perm('reports.view')
    def imaging_ai_workspace(order_id):
        order=_rb.Order.query.get_or_404(order_id)
        rows=_rb.ImagingAIAnalysis.query.filter_by(order_id=order.id).order_by(_rb.ImagingAIAnalysis.requested_at.desc()).limit(20).all()
        return _rb.render_template('imaging_ai_workspace.html',order=order,rows=rows,provider=_rb.imaging_ai_provider_for_modality(order.modality))
    return imaging_ai_workspace


def install_0676(_rb):
    @_rb.app.post('/reports/<int:order_id>/imaging-ai/verify-demographics')
    @_rb.require_perm('reports.view')
    def imaging_ai_verify_demographics(order_id):
        order=_rb.Order.query.get_or_404(order_id)

        demographic_ok, demographic_reason = _rb.pacs_demographic_gate(order)

        if not demographic_ok:
            _rb.audit(
                'IMAGING_AI_BLOCKED_PACS_DEMOGRAPHICS',
                'order',
                order.id,
                demographic_reason
            )
            _rb.db.session.commit()
            _rb.flash(
                'Imaging AI blocked: PACS demographics require authorized reconciliation.',
                'danger'
            )
            return _rb.redirect(_rb.url_for('imaging_ai_workspace',order_id=order.id))

        pacs,error=_rb.pacs_study_lookup(order)
        if not pacs:
            _rb.flash('PACS lookup failed: '+error,'danger')
            return _rb.redirect(_rb.url_for('imaging_ai_workspace',order_id=order.id))
        result=_rb.demographic_verification(order,pacs)
        provider=_rb.imaging_ai_provider_for_modality(order.modality)
        row=_rb.ImagingAIAnalysis(
          order_id=order.id,
          provider_key=(provider.provider_key if provider else ''),
          model_name=(provider.model_name if provider else ''),
          study_instance_uid=pacs.get('study_instance_uid',''),
          accession=order.accession,
          status='DEMOGRAPHICS_CHECKED',
          demographic_status=result['status'],
          demographic_score=result['score'],
          demographic_details_json=_rb.json.dumps({'pacs':pacs,'verification':result},ensure_ascii=False),
          requested_by=_rb.current_user().id
        )
        _rb.db.session.add(row)
        _rb.audit('IMAGING_AI_DEMOGRAPHIC_CHECK','order',order.id,f"{result['status']}:{result['score']:.2f}")
        _rb.db.session.commit()
        return _rb.redirect(_rb.url_for('imaging_ai_workspace',order_id=order.id))
    return imaging_ai_verify_demographics


def install_0677(_rb):
    @_rb.app.post('/reports/<int:order_id>/imaging-ai/<int:analysis_id>/override')
    @_rb.require_perm('users.view')
    def imaging_ai_demographic_override(order_id,analysis_id):
        row=_rb.ImagingAIAnalysis.query.filter_by(id=analysis_id,order_id=order_id).first_or_404()
        reason=(_rb.request.form.get('reason') or '').strip()
        if not reason:
            _rb.flash('Override reason is required.','danger')
            return _rb.redirect(_rb.url_for('imaging_ai_workspace',order_id=order_id))
        old=row.demographic_status
        row.demographic_status='VERIFIED'
        _rb.db.session.add(_rb.DemographicOverrideAudit(
          order_id=order_id,analysis_id=row.id,original_status=old,
          override_reason=reason,overridden_by=_rb.current_user().id
        ))
        _rb.audit('IMAGING_AI_DEMOGRAPHIC_OVERRIDE','order',order_id,f'{old}->VERIFIED')
        _rb.db.session.commit()
        return _rb.redirect(_rb.url_for('imaging_ai_workspace',order_id=order_id))
    return imaging_ai_demographic_override


def install_0678(_rb):
    @_rb.app.post('/reports/<int:order_id>/imaging-ai/<int:analysis_id>/analyze')
    @_rb.require_perm('reports.edit')
    def imaging_ai_analyze(order_id,analysis_id):
        order=_rb.Order.query.get_or_404(order_id)

        demographic_ok, demographic_reason = _rb.pacs_demographic_gate(order)

        if not demographic_ok:
            _rb.audit(
                'IMAGING_AI_BLOCKED_PACS_DEMOGRAPHICS',
                'order',
                order.id,
                demographic_reason
            )
            _rb.db.session.commit()
            _rb.flash(
                'Imaging AI blocked: PACS demographics require authorized reconciliation.',
                'danger'
            )
            return _rb.redirect(_rb.url_for('imaging_ai_workspace',order_id=order.id))

        row=_rb.ImagingAIAnalysis.query.filter_by(id=analysis_id,order_id=order.id).first_or_404()
        if row.demographic_status!='VERIFIED':
            _rb.flash('Image AI analysis blocked until demographics are VERIFIED.','danger')
            return _rb.redirect(_rb.url_for('imaging_ai_workspace',order_id=order.id))
        details=_rb.json.loads(row.demographic_details_json or '{}')
        pacs=details.get('pacs') or {}
        row.status='ANALYZING'
        _rb.db.session.commit()
        result,error=_rb.call_imaging_ai(order,pacs,row)
        if not result:
            row.status='FAILED';row.error_text=error;_rb.db.session.commit()
            _rb.flash('Imaging AI failed: '+error,'danger')
            return _rb.redirect(_rb.url_for('imaging_ai_workspace',order_id=order.id))
        row.structured_findings_json=_rb.json.dumps(result['structured_findings'],ensure_ascii=False)
        row.summary_text=result['summary']
        row.uncertainty_text=result['uncertainty']
        row.raw_response_json=_rb.json.dumps(result['raw'],ensure_ascii=False,default=str)
        row.status='AI_FINDINGS_READY'
        row.completed_at=_rb.datetime.utcnow()
        _rb.audit('IMAGING_AI_ANALYSIS_COMPLETE','order',order.id,f'analysis={row.id}')
        _rb.db.session.commit()
        return _rb.redirect(_rb.url_for('imaging_ai_workspace',order_id=order.id))
    return imaging_ai_analyze


def install_0679(_rb):
    @_rb.app.post('/reports/<int:order_id>/imaging-ai/<int:analysis_id>/mark-reviewed')
    @_rb.require_perm('reports.edit')
    def imaging_ai_mark_reviewed(order_id,analysis_id):
        row=_rb.ImagingAIAnalysis.query.filter_by(id=analysis_id,order_id=order_id).first_or_404()
        row.reviewed_by=_rb.current_user().id;row.reviewed_at=_rb.datetime.utcnow()
        if row.status=='AI_FINDINGS_READY':
            row.status='DOCTOR_REVIEWED'
        _rb.db.session.commit()
        return _rb.redirect(_rb.url_for('imaging_ai_workspace',order_id=order_id))
    return imaging_ai_mark_reviewed


def install_0709(_rb):
    @_rb.app.post('/reports/<int:order_id>/return-case')
    @_rb.login_required
    def return_case_to_workflow(order_id):
        o=_rb.Order.query.get_or_404(order_id)
        from technician_queue import return_actor
        return_actor(_rb._reporting_support_sys.modules[_rb.__name__],o)
        code=(_rb.request.form.get('reason_code') or 'OTHER').upper()
        rr=_rb.CaseReturnReason.query.filter_by(code=code,active=True).first()
        note=(_rb.request.form.get('note') or '').strip()
        if not rr or len(note)<5 or len(note)>10000:
            _rb.abort(400)
        action_owner=(_rb.request.form.get('action_owner') or '').strip().upper()
        if action_owner not in ('','TECHNICIAN'):
            _rb.abort(400)
        route=action_owner or rr.route_to
        _rb.db.session.add(_rb.CaseWorkflowEvent(order_id=o.id,event_type='RETURNED',owner_role=route,reason_code=code,note=note,created_by=_rb.current_user().id))
        now=_rb.datetime.utcnow()
        for a in _rb.CaseAssignment.query.filter_by(order_id=o.id,active=True).all():
            a.active=False
            a.unassigned_at=now
            a.notes=(f'Returned by doctor: {code}. {note}')[:500]

        for offer in _rb.AssignmentOffer.query.filter_by(order_id=o.id,status='PENDING').all():
            offer.status='CANCELLED'
            offer.responded_at=now
            offer.response_note=(f'Cancelled because case was returned: {code}')[:500]

        o.assigned_doctor_id=None
        if (o.status or '').upper() not in ('FINAL','CANCELLED'):
            o.status='COMPLETED'
        _rb.create_ris_notification(o,'RETURNED_TO_TECH' if route=='TECHNICIAN' else 'CASE_RETURNED',
          'Case returned for correction',f'{code}: {note}','WARNING',route,commit=False)
        _rb.audit(
            'CASE_RETURNED_FOR_ACTION',
            'order',
            o.id,
            f'reason={code}; route={route}; note={note}'
        )

        _rb.db.session.commit()

        _rb.flash(
            f'Case returned successfully: {rr.label if rr else code} → {route}',
            'success'
        )

        return _rb.redirect(_rb.url_for('doctor') if _rb.has_perm('reports.edit') else _rb.url_for('returned_cases_queue'))
    return return_case_to_workflow


def install_0710(_rb):
    @_rb.app.get('/reports/<int:order_id>/return-case')
    @_rb.login_required
    def return_case_form(order_id):
        order=_rb.Order.query.get_or_404(order_id)
        from technician_queue import return_actor
        return_actor(_rb._reporting_support_sys.modules[_rb.__name__],order)
        return _rb.render_template('return_case.html',order=order,reasons=_rb.CaseReturnReason.query.filter_by(active=True).order_by(_rb.CaseReturnReason.label).all())
    return return_case_form


def install_0713(_rb):
    @_rb.app.get('/reports-portal/<int:order_id>/download')
    @_rb.require_perm('reports.view')
    def report_portal_download(order_id):
        order=_rb.Order.query.get_or_404(order_id)
        report=order.report

        if not report or (report.status or '').upper()!='FINAL':
            _rb.flash('Report is not FINAL yet.','warning')
            return _rb.redirect(_rb.url_for('reports_portal'))

        corrected=_rb._rb_final_revision_document(order)
        if corrected:return _rb._rb_revision_pdf_download(order,corrected)
        # Prefer the final PDF.
        if report.pdf_path and _rb.os.path.isfile(report.pdf_path):
            return _rb.send_file(
                report.pdf_path,
                as_attachment=True,
                download_name=f'{order.accession}-FINAL.pdf'
            )

        # Then the final DOCX/source document.
        for path in [report.docx_path, report.source_path]:
            if path and _rb.os.path.isfile(path):
                ext=_rb.os.path.splitext(path)[1].lower() or '.docx'

                return _rb.send_file(
                    path,
                    as_attachment=True,
                    download_name=f'{order.accession}-FINAL{ext}'
                )

        # FINAL report exists in DB but physical file is missing:
        # create a PDF from the stored report content.
        try:
            folder=_rb.os.path.join(_rb.REPORT_DIR,order.accession)
            _rb.os.makedirs(folder,exist_ok=True)

            pdf_path=_rb.os.path.join(
                folder,
                f'{order.accession}-FINAL.pdf'
            )

            _rb.make_pdf(order,report,pdf_path)

            report.pdf_path=pdf_path
            _rb.db.session.commit()

            return _rb.send_file(
                pdf_path,
                as_attachment=True,
                download_name=f'{order.accession}-FINAL.pdf'
            )

        except Exception as exc:
            _rb.app.logger.exception(
                'Report Portal download generation failed for order %s',
                order.id
            )

            _rb.flash(
                f'Final report exists but the downloadable file is not available: {exc}',
                'danger'
            )

            return _rb.redirect(_rb.url_for('reports_portal'))
    return report_portal_download


def install_0714(_rb):
    @_rb.app.get('/reports-portal/<int:order_id>/pdf')
    @_rb.require_perm('reports.view')
    def report_portal_download_pdf(order_id):
        order=_rb.Order.query.get_or_404(order_id)
        report=order.report

        if not report or (report.status or '').upper()!='FINAL':
            _rb.abort(404)

        corrected=_rb._rb_final_revision_document(order)
        if corrected:return _rb._rb_revision_pdf_download(order,corrected)
        if not report.pdf_path or not _rb.os.path.isfile(report.pdf_path):
            _rb.abort(404)

        return _rb.send_file(
            report.pdf_path,
            as_attachment=True,
            download_name=f'{order.accession}-FINAL.pdf'
        )
    return report_portal_download_pdf


def install_0715(_rb):
    @_rb.app.get('/reports-portal/<int:order_id>/docx')
    @_rb.require_perm('reports.view')
    def report_portal_download_docx(order_id):
        order=_rb.Order.query.get_or_404(order_id)
        report=order.report

        if not report:
            _rb.abort(404)

        authoritative = _rb._rb_authoritative_docx_download(
            order,
            report,
        )

        if authoritative:
            return _rb.send_file(
                authoritative['path'],
                as_attachment=True,
                download_name=_rb.build_report_filename(
                    order,
                    authoritative['version_no'],
                    authoritative['status'],
                    'docx',
                ),
                mimetype=(
                    'application/vnd.openxmlformats-officedocument.'
                    'wordprocessingml.document'
                ),
            )

        path=report.docx_path or report.source_path

        if not path or not _rb.os.path.isfile(path):
            _rb.abort(404)

        return _rb.send_file(
            path,
            as_attachment=True,
            download_name=f'{order.accession}-{report.status or "REPORT"}.docx'
        )
    return report_portal_download_docx


def install_0718(_rb):
    @_rb.app.get('/reports-portal')
    @_rb.require_perm('reports.view')
    def reports_portal():
        view=(_rb.request.args.get('view') or 'all').lower()
        q=(_rb.request.args.get('q') or '').strip()

        branch_id=_rb.request.args.get('branch_id',type=int)
        doctor_id=_rb.request.args.get('doctor_id',type=int)
        modality=(_rb.request.args.get('modality') or '').strip().upper()
        report_status=(_rb.request.args.get('report_status') or '').strip().upper()

        date_from=(_rb.request.args.get('date_from') or '').strip()
        date_to=(_rb.request.args.get('date_to') or '').strip()

        orders=_rb.Order.query.join(_rb.Patient)

        if q:
            like=f'%{q}%'
            orders=orders.filter(
                _rb.or_(
                    _rb.Patient.name.ilike(like),
                    _rb.Patient.patient_id.ilike(like),
                    _rb.Order.accession.ilike(like),
                    _rb.Order.procedure.ilike(like)
                )
            )

        if branch_id:
            orders=orders.filter(_rb.Order.branch_id==branch_id)

        if doctor_id:
            orders=orders.filter(_rb.Order.assigned_doctor_id==doctor_id)

        if modality:
            orders=orders.filter(_rb.Order.modality==modality)

        if date_from:
            try:
                dt=_rb.datetime.strptime(date_from,'%Y-%m-%d')
                orders=orders.filter(_rb.Order.scheduled>=dt)
            except Exception:
                pass

        if date_to:
            try:
                dt=_rb.datetime.strptime(date_to,'%Y-%m-%d')+_rb.timedelta(days=1)
                orders=orders.filter(_rb.Order.scheduled<dt)
            except Exception:
                pass

        # Keep portal responsive while allowing useful management reporting.
        source_rows=orders.order_by(
            _rb.Order.id.desc()
        ).limit(5000).all()

        all_result=[]

        for o in source_rows:
            report=o.report

            if report_status:
                current_report_status=(
                    (report.status or 'UNREPORTED').upper()
                    if report else 'UNREPORTED'
                )

                if current_report_status!=report_status:
                    continue

            latest_return=_rb.CaseWorkflowEvent.query.filter_by(
                order_id=o.id,
                event_type='RETURNED'
            ).order_by(
                _rb.CaseWorkflowEvent.created_at.desc()
            ).first()

            latest_ready=_rb.CaseWorkflowEvent.query.filter_by(
                order_id=o.id,
                event_type='READY_FOR_REREVIEW'
            ).order_by(
                _rb.CaseWorkflowEvent.created_at.desc()
            ).first()

            state='WAITING'

            if latest_return and (
                not latest_ready or latest_ready.created_at < latest_return.created_at
            ):
                state='NEEDS_ACTION'

            elif latest_ready and (
                not latest_return or latest_ready.created_at >= latest_return.created_at
            ):
                state='READY_FOR_REREVIEW'

            elif report and (report.status or '').upper()=='FINAL':
                state='FINAL'

            elif report and (report.status or '').upper() not in ('','UNREPORTED'):
                state='REPORTING'

            elif report:
                state='WAITING'

            # Report TAT:
            # exam completion -> report finalization.
            # Fallback for old records: scheduled -> finalized.
            tat_minutes=None

            if report and report.finalized_at:
                start_at=o.exam_completed_at or o.scheduled

                if start_at:
                    tat_minutes=max(
                        0,
                        int(
                            (report.finalized_at-start_at).total_seconds()/60
                        )
                    )

            sla=_rb.report_sla_snapshot(o,report)

            all_result.append({
                'order':o,
                'report':report,
                'portal_state':state,
                'latest_return':latest_return,
                'latest_ready':latest_ready,
                'tat_minutes':tat_minutes,
                'sla':sla
            })

        # ------------------------------------------------------------
        # Statistics are calculated BEFORE the view tab filter.
        # They therefore represent all results matching search/date/etc.
        # ------------------------------------------------------------

        total=len(all_result)

        final_count=sum(
            1 for x in all_result
            if x['portal_state']=='FINAL'
        )

        reporting_count=sum(
            1 for x in all_result
            if x['portal_state']=='REPORTING'
        )

        needs_action_count=sum(
            1 for x in all_result
            if x['portal_state']=='NEEDS_ACTION'
        )

        rereview_count=sum(
            1 for x in all_result
            if x['portal_state']=='READY_FOR_REREVIEW'
        )

        waiting_count=sum(
            1 for x in all_result
            if x['portal_state']=='WAITING'
        )

        delivered_count=sum(
            1 for x in all_result
            if bool(x['order'].report_delivered)
        )

        tat_values=[
            x['tat_minutes']
            for x in all_result
            if x['tat_minutes'] is not None
        ]

        avg_tat_minutes=(
            round(sum(tat_values)/len(tat_values))
            if tat_values else None
        )

        finalization_rate=(
            round((final_count/total)*100,1)
            if total else 0
        )

        sla_on_time=sum(
            1 for x in all_result
            if x['sla']['status']=='ON_TIME'
        )

        sla_near=sum(
            1 for x in all_result
            if x['sla']['status']=='NEAR_SLA'
        )

        sla_breached=sum(
            1 for x in all_result
            if x['sla']['status']=='BREACHED'
        )

        urgent_open=sum(
            1 for x in all_result
            if x['sla']['priority']=='URGENT'
            and x['portal_state']!='FINAL'
        )

        stat_open=sum(
            1 for x in all_result
            if x['sla']['priority'] in ('STAT','EMERGENCY')
            and x['portal_state']!='FINAL'
        )

        vip_open=sum(
            1 for x in all_result
            if x['sla']['priority']=='VIP'
            and x['portal_state']!='FINAL'
        )

        stats={
            'sla_on_time':sla_on_time,
            'sla_near':sla_near,
            'sla_breached':sla_breached,
            'urgent_open':urgent_open,
            'stat_open':stat_open,
            'vip_open':vip_open,
            'total':total,
            'final':final_count,
            'reporting':reporting_count,
            'waiting':waiting_count,
            'needs_action':needs_action_count,
            'rereview':rereview_count,
            'delivered':delivered_count,
            'avg_tat_minutes':avg_tat_minutes,
            'finalization_rate':finalization_rate
        }

        result=all_result

        if view!='all':
            result=[
                x for x in all_result
                if x['portal_state'].lower()==view
            ]

        branches=_rb.Branch.query.filter_by(
            active=True
        ).order_by(_rb.Branch.name).all()

        doctors=_rb.User.query.join(_rb.Role).filter(
            _rb.Role.code.in_(['RADIOLOGIST','DOCTOR']),
            _rb.User.active.is_(True)
        ).order_by(_rb.User.full_name).all()

        modalities=sorted({
            (x['order'].modality or '').upper()
            for x in all_result
            if x['order'].modality
        })

        return _rb.render_template(
            'reports_portal.html',
            rows=result,
            stats=stats,
            branches=branches,
            doctors=doctors,
            modalities=modalities,
            view=view,
            q=q,
            branch_id=branch_id,
            doctor_id=doctor_id,
            modality=modality,
            report_status=report_status,
            date_from=date_from,
            date_to=date_to,
            format_sla_minutes=_rb.format_sla_minutes
        )
    return reports_portal


def install_0719(_rb):
    @_rb.app.get('/reports-portal.csv')
    @_rb.require_perm('reports.view')
    def reports_portal_csv():

        args=_rb.request.args.to_dict(flat=True)
        args['view']=args.get('view') or 'all'

        q=(args.get('q') or '').strip()
        branch_id=_rb.request.args.get('branch_id',type=int)
        doctor_id=_rb.request.args.get('doctor_id',type=int)
        modality=(args.get('modality') or '').strip().upper()
        report_status=(args.get('report_status') or '').strip().upper()
        view=(args.get('view') or 'all').lower()
        date_from=(args.get('date_from') or '').strip()
        date_to=(args.get('date_to') or '').strip()

        orders=_rb.Order.query.join(_rb.Patient)

        if q:
            like=f'%{q}%'
            orders=orders.filter(
                _rb.or_(
                    _rb.Patient.name.ilike(like),
                    _rb.Patient.patient_id.ilike(like),
                    _rb.Order.accession.ilike(like),
                    _rb.Order.procedure.ilike(like)
                )
            )

        if branch_id:
            orders=orders.filter(_rb.Order.branch_id==branch_id)

        if doctor_id:
            orders=orders.filter(_rb.Order.assigned_doctor_id==doctor_id)

        if modality:
            orders=orders.filter(_rb.Order.modality==modality)

        if date_from:
            try:
                orders=orders.filter(
                    _rb.Order.scheduled>=_rb.datetime.strptime(date_from,'%Y-%m-%d')
                )
            except Exception:
                pass

        if date_to:
            try:
                orders=orders.filter(
                    _rb.Order.scheduled<
                    _rb.datetime.strptime(date_to,'%Y-%m-%d')+_rb.timedelta(days=1)
                )
            except Exception:
                pass

        rows=orders.order_by(_rb.Order.id.desc()).limit(5000).all()

        output=_rb.io.StringIO()
        writer=_rb.csv.writer(output)

        writer.writerow([
            'Patient ID',
            'Patient Name',
            'Accession',
            'Study Date',
            'Branch',
            'Modality',
            'Exam',
            'Doctor',
            'Report Status',
            'Case State',
            'Doctor Request',
            'Finalized At',
            'Report TAT Minutes',
            'Delivered'
        ])

        for o in rows:
            report=o.report

            current_status=(
                (report.status or 'UNREPORTED').upper()
                if report else 'UNREPORTED'
            )

            if report_status and current_status!=report_status:
                continue

            latest_return=_rb.CaseWorkflowEvent.query.filter_by(
                order_id=o.id,
                event_type='RETURNED'
            ).order_by(
                _rb.CaseWorkflowEvent.created_at.desc()
            ).first()

            latest_ready=_rb.CaseWorkflowEvent.query.filter_by(
                order_id=o.id,
                event_type='READY_FOR_REREVIEW'
            ).order_by(
                _rb.CaseWorkflowEvent.created_at.desc()
            ).first()

            state='WAITING'

            if latest_return and (
                not latest_ready or latest_ready.created_at<latest_return.created_at
            ):
                state='NEEDS_ACTION'

            elif latest_ready and (
                not latest_return or latest_ready.created_at>=latest_return.created_at
            ):
                state='READY_FOR_REREVIEW'

            elif current_status=='FINAL':
                state='FINAL'

            elif report and current_status not in ('','UNREPORTED'):
                state='REPORTING'

            if view!='all' and state.lower()!=view:
                continue

            tat_minutes=''

            if report and report.finalized_at:
                start_at=o.exam_completed_at or o.scheduled

                if start_at:
                    tat_minutes=max(
                        0,
                        int(
                            (report.finalized_at-start_at).total_seconds()/60
                        )
                    )

            doctor_request=''

            if state=='NEEDS_ACTION' and latest_return:
                doctor_request=(
                    f'{latest_return.reason_code}: '
                    f'{latest_return.note or ""}'
                )

            writer.writerow([
                o.patient.patient_id,
                o.patient.name,
                o.accession,
                o.scheduled.isoformat(sep=' ') if o.scheduled else '',
                o.branch.name if o.branch else '',
                o.modality,
                o.procedure,
                (
                    o.assigned_doctor.full_name
                    if o.assigned_doctor else ''
                ),
                current_status,
                state,
                doctor_request,
                (
                    report.finalized_at.isoformat(sep=' ')
                    if report and report.finalized_at else ''
                ),
                tat_minutes,
                'YES' if o.report_delivered else 'NO'
            ])

        data='\ufeff'+output.getvalue()

        return _rb.Response(
            data,
            mimetype='text/csv; charset=utf-8',
            headers={
                'Content-Disposition':
                'attachment; filename=radbridge-report-portal.csv'
            }
        )
    return reports_portal_csv


def install_0740(_rb):
    @_rb.app.get('/operations/assignment-reports')
    @_rb.require_perm('orders.view')
    def assignment_reports():
        rows=_rb.assignment_report_rows()
        return _rb.render_template('assignment_reports.html',rows=rows)
    return assignment_reports


def install_0742(_rb):
    @_rb.app.get('/operations/assignment-report.csv')
    @_rb.require_perm('orders.view')
    def assignment_report_csv():
        import csv,io
        from flask import make_response
        buf=io.StringIO()
        w=csv.writer(buf)
        w.writerow(['Accession','Patient','Modality','Procedure','Priority','Readiness','Assigned Doctor','Assignment Type','Offer Attempts','Last Offer','TAT Min','Delay Owner','Report Status'])
        for x in _rb.assignment_report_rows():
            o=x['order'];ca=x['assignment'];rp=x['report']
            w.writerow([o.accession,o.patient.name,o.modality,o.procedure,o.priority,
              x['readiness'].status if x['readiness'] else '',
              ca.doctor_user_id if ca else '',ca.assignment_type if ca else '',
              x['offer_attempts'],x['last_offer_status'],x['tat']['total_min'],x['tat']['owner'],
              rp.status if rp else ''])
        resp=make_response(buf.getvalue());resp.headers['Content-Type']='text/csv'
        resp.headers['Content-Disposition']='attachment; filename=assignment-report.csv'
        return resp
    return assignment_report_csv


def install_0761(_rb):
    @_rb.app.route('/doctor/case/<int:order_id>/workspace',methods=['GET','POST'])
    @_rb.require_perm('reports.view')
    def doctor_clinical_workspace(order_id):
        order=_rb.Order.query.get_or_404(order_id)
        assessment=_rb.ClinicalAssessment.query.filter_by(order_id=order.id).first()
        if not assessment:
            assessment=_rb.ClinicalAssessment(order_id=order.id,created_by=_rb.current_user().id)
            _rb.db.session.add(assessment);_rb.db.session.flush()

        if _rb.request.method=='POST':
            section=(_rb.request.form.get('section') or '').upper()

            if section=='CLINICAL':
                assessment.complaint=(_rb.request.form.get('complaint') or '').strip()
                assessment.history=(_rb.request.form.get('history') or '').strip()
                assessment.examination=(_rb.request.form.get('examination') or '').strip()
                assessment.clinical_indication=(_rb.request.form.get('clinical_indication') or '').strip()
                assessment.allergy_notes=(_rb.request.form.get('allergy_notes') or '').strip()
                assessment.updated_by=_rb.current_user().id

            elif section=='VITALS':
                _rb.db.session.add(_rb.VitalSign(
                    order_id=order.id,
                    temperature=_rb.request.form.get('temperature',type=float),
                    pulse=_rb.request.form.get('pulse',type=int),
                    systolic=_rb.request.form.get('systolic',type=int),
                    diastolic=_rb.request.form.get('diastolic',type=int),
                    spo2=_rb.request.form.get('spo2',type=int),
                    respiratory_rate=_rb.request.form.get('respiratory_rate',type=int),
                    weight_kg=_rb.request.form.get('weight_kg',type=float),
                    height_cm=_rb.request.form.get('height_cm',type=float),
                    recorded_by=_rb.current_user().id
                ))

            elif section=='DIAGNOSIS':
                txt=(_rb.request.form.get('diagnosis_text') or '').strip()
                if txt:
                    _rb.db.session.add(_rb.ClinicalDiagnosis(
                        order_id=order.id,
                        diagnosis_text=txt,
                        diagnosis_type=(_rb.request.form.get('diagnosis_type') or 'WORKING').upper(),
                        code=(_rb.request.form.get('code') or '').strip(),
                        created_by=_rb.current_user().id
                    ))

            elif section=='TREATMENT':
                assessment.treatment_plan=(_rb.request.form.get('treatment_plan') or '').strip()
                assessment.updated_by=_rb.current_user().id

            elif section=='MEDICATION':
                name=(_rb.request.form.get('medication_name') or '').strip()
                if name:
                    _rb.db.session.add(_rb.ClinicalMedication(
                        order_id=order.id,
                        medication_name=name,
                        dose=(_rb.request.form.get('dose') or '').strip(),
                        route=(_rb.request.form.get('route') or '').strip(),
                        frequency=(_rb.request.form.get('frequency') or '').strip(),
                        duration=(_rb.request.form.get('duration') or '').strip(),
                        notes=(_rb.request.form.get('notes') or '').strip(),
                        created_by=_rb.current_user().id
                    ))

            elif section=='LAB':
                test_name=(_rb.request.form.get('test_name') or '').strip()
                if test_name:
                    _rb.db.session.add(_rb.ClinicalLabItem(
                        order_id=order.id,
                        test_name=test_name,
                        created_by=_rb.current_user().id
                    ))

            _rb.db.session.commit()
            _rb.audit('CLINICAL_WORKSPACE_UPDATE','order',order.id,section)
            return _rb.redirect(_rb.url_for('doctor_clinical_workspace',order_id=order.id,tab=(_rb.request.form.get('return_tab') or '').lower()))

        attachments=_rb.Attachment.query.filter_by(order_id=order.id).order_by(_rb.Attachment.created_at.desc()).all()
        priors=_rb.related_prior_orders(order,20)
        ext_priors=_rb.external_priors_for_order(order)
        reports=_rb.Report.query.filter_by(order_id=order.id).order_by(_rb.Report.id.desc()).all()
        vitals=_rb.VitalSign.query.filter_by(order_id=order.id).order_by(_rb.VitalSign.recorded_at.desc()).all()
        diagnoses=_rb.ClinicalDiagnosis.query.filter_by(order_id=order.id).order_by(_rb.ClinicalDiagnosis.created_at.desc()).all()
        medications=_rb.ClinicalMedication.query.filter_by(order_id=order.id,active=True).order_by(_rb.ClinicalMedication.created_at.desc()).all()
        labs=_rb.ClinicalLabItem.query.filter_by(order_id=order.id).order_by(_rb.ClinicalLabItem.created_at.desc()).all()
        readiness=__import__('reception_readiness').view(order,_rb.CaseReadiness.query.filter_by(order_id=order.id).first())
        assignment=_rb.CaseAssignment.query.filter_by(order_id=order.id,active=True).first()

        return _rb.render_template(
            'doctor_clinical_workspace.html',
            order=order,
            assessment=assessment,
            attachments=attachments,
            priors=priors,
            external_priors=ext_priors,
            reports=reports,
            vitals=vitals,
            diagnoses=diagnoses,
            medications=medications,
            labs=labs,
            readiness=readiness,
            assignment=assignment,
            tab=_rb.request.args.get('tab','overview')
        )
    return doctor_clinical_workspace


def install_0784(_rb):
    @_rb.app.get('/finance/doctor-earnings')
    @_rb.require_perm('finance.doctor_share.view')
    def doctor_earnings_report():
        start,end,start_dt,end_dt=_rb.management_date_range()
        doctor_id=_rb.request.args.get('doctor_id',type=int)
        from replacement_settlements import actor
        user=actor(_rb._reporting_support_sys.modules[_rb.__name__])
        branch_id=_rb.request.args.get('branch_id',type=int)
        if not _rb.has_perm('*'):
            if branch_id and branch_id!=user.branch_id:_rb.abort(403)
            branch_id=user.branch_id
        query=_rb.management_orders_query(start_dt,end_dt)
        if branch_id:query=query.filter(_rb.Order.branch_id==branch_id)
        orders=query.all()
        visible_doctors={}
        rows=[];tot_share=tot_revenue=tot_discount=0.0
        for o in orders:
            share,rule,doctor=_rb.performing_doctor_share_for_order(o)
            if not doctor: continue
            visible_doctors[doctor.id]=doctor
            if doctor_id and doctor.id!=doctor_id: continue
            revenue=float(o.contract_price or o.gross_price or 0)
            discount=_rb.total_order_discount(o)
            rows.append({'order':o,'doctor':doctor,'share':share,'rule':rule,'revenue':revenue,'discount':discount,'net':_rb.effective_patient_due(o)})
            tot_share+=share;tot_revenue+=revenue;tot_discount+=discount
        return _rb.render_template('doctor_earnings.html',rows=rows,start=start,end=end,doctor_id=doctor_id,
            doctors=sorted(visible_doctors.values(),key=lambda d:d.full_name or d.username),
            total_share=tot_share,total_revenue=tot_revenue,total_discount=tot_discount)
    return doctor_earnings_report


def install_0800(_rb):
    @_rb.app.get('/inventory/ledger')
    @_rb.require_perm('inventory.reports')
    def inventory_ledger():
        warehouse_id=_rb.request.args.get('warehouse_id',type=int);item_id=_rb.request.args.get('item_id',type=int)
        q=_rb.WarehouseStockMovement.query
        if warehouse_id:q=q.filter_by(warehouse_id=warehouse_id)
        if item_id:q=q.filter_by(item_id=item_id)
        rows=q.order_by(_rb.WarehouseStockMovement.id.desc()).limit(1000).all()
        return _rb.render_template('inventory_ledger.html',rows=rows,
            warehouses=_rb.Warehouse.query.filter_by(active=True).order_by(_rb.Warehouse.name).all(),
            items=_rb.InventoryItem.query.filter_by(active=True).order_by(_rb.InventoryItem.name).all(),
            warehouse_id=warehouse_id,item_id=item_id)
    return inventory_ledger


def install_0801(_rb):
    @_rb.app.get('/inventory/consumption-report')
    @_rb.require_perm('inventory.reports')
    def inventory_consumption_report():
        start,end,start_dt,end_dt=_rb.management_date_range()
        rows=_rb.OrderConsumableUsage.query.filter(_rb.OrderConsumableUsage.created_at>=start_dt,_rb.OrderConsumableUsage.created_at<end_dt).order_by(_rb.OrderConsumableUsage.created_at.desc()).all()
        total=sum(((-1 if x.usage_type=='RETURN' else 1)*float(x.qty or 0)*float(x.unit_cost or 0)) for x in rows)
        return _rb.render_template('inventory_consumption_report.html',rows=rows,start=start,end=end,total_cost=round(total,2))
    return inventory_consumption_report


def install_0825(_rb):
    @_rb.app.get('/coordinator')
    @_rb.require_perm('reports.coordinate')
    def coordinator_queue():
        u=_rb.current_user()
        rows=_rb.CoordinatorTask.query.filter(
          _rb.or_(_rb.CoordinatorTask.assigned_to.is_(None),_rb.CoordinatorTask.assigned_to==u.id),
          _rb.CoordinatorTask.status.notin_(['COMPLETED'])
        ).order_by(_rb.CoordinatorTask.created_at).limit(300).all()
        return _rb.render_template('coordinator_queue.html',rows=rows)
    return coordinator_queue


def install_0826(_rb):
    @_rb.app.post('/coordinator/<int:task_id>/action')
    @_rb.require_perm('reports.coordinate')
    def coordinator_action(task_id):
        task=_rb.CoordinatorTask.query.get_or_404(task_id);action=(_rb.request.form.get('action') or '').upper()
        if task.assigned_to and task.assigned_to!=_rb.current_user().id:_rb.abort(403)
        if not task.assigned_to:task.assigned_to=_rb.current_user().id;task.started_at=_rb.datetime.utcnow()
        note=(_rb.request.form.get('note') or '').strip()
        task.coordinator_note=note
        report=task.report
        if action=='START':
            task.status='FORMATTING';report.status='FORMATTING'
        elif action=='READY_APPROVAL':
            task.status='COMPLETED';task.completed_at=_rb.datetime.utcnow();report.status='READY_APPROVAL'
            _rb.audit(
                'COORDINATOR_FORMATTING_COMPLETE',
                'order',
                task.order_id,
                note or 'Formatting / quality review completed'
            )
        elif action=='RETURN_TO_DOCTOR':
            task.status='RETURNED_TO_DOCTOR';task.returned_at=_rb.datetime.utcnow();report.status='DRAFT'
            _rb.audit(
                'COORDINATOR_RETURNED_TO_DOCTOR',
                'order',
                task.order_id,
                note or 'Returned to doctor'
            )
        else:_rb.abort(400)
        _rb.audit('COORDINATOR_ACTION','order',task.order_id,f'{action}: {note}');_rb.db.session.commit()
        return _rb.redirect(_rb.url_for('coordinator_queue'))
    return coordinator_action


def install_0863(_rb):
    @_rb.app.get('/api/ohif/report/<int:order_id>')
    @_rb.require_ohif_token
    def api_ohif_report_get(order_id):
        order = _rb.Order.query.get_or_404(order_id)

        context_block = _rb.require_valid_ohif_case_context(order)
        if context_block:
            return context_block

        doctor_user, identity_block = _rb.require_ohif_doctor_user(order.id)
        if identity_block:
            return identity_block

        # Record a real reporting-panel open, but suppress refresh/reload noise
        # for the same doctor and order for five minutes.
        opened_since = _rb.datetime.utcnow() - _rb.timedelta(minutes=5)

        recent_open = (
            _rb.AuditLog.query
            .filter_by(
                user_id=doctor_user.id,
                action='OHIF_REPORT_OPENED',
                entity='order',
                entity_id=str(order.id)
            )
            .filter(_rb.AuditLog.created_at >= opened_since)
            .first()
        )

        if recent_open is None:
            _rb.audit_as_user(
                doctor_user,
                'OHIF_REPORT_OPENED',
                'order',
                order.id,
                'OHIF reporting panel opened'
            )
            _rb.db.session.commit()

        report = _rb.get_report(order)
        return _rb.jsonify(_rb._ohif_report_json(order, report))
    return api_ohif_report_get


def install_0865(_rb):
    @_rb.app.get('/api/ohif/report/<int:order_id>/word')
    @_rb.require_ohif_token
    def api_ohif_report_word(order_id):
        order = _rb.Order.query.get_or_404(order_id)

        # The exported clinical document requires the same doctor identity
        # and order authorization as the report panel.
        doctor_user, identity_block = _rb.require_ohif_doctor_user(order.id)
        if identity_block:
            return identity_block

        context_block = _rb.require_valid_ohif_case_context(order)
        if context_block:
            return context_block
        report = _rb.get_report(order)

        authoritative = _rb._rb_authoritative_docx_download(
            order,
            report,
        )

        if authoritative:
            return _rb.send_file(
                authoritative['path'],
                as_attachment=True,
                download_name=_rb.build_report_filename(
                    order,
                    authoritative['version_no'],
                    authoritative['status'],
                    'docx',
                ),
                mimetype=(
                    'application/vnd.openxmlformats-officedocument.'
                    'wordprocessingml.document'
                ),
            )

        version_no = _rb._next_report_version(report)

        doc = _rb.Document()
        section = doc.sections[0]
        header = section.header

        table = header.add_table(
            rows=5,
            cols=4,
            width=_rb.Inches(7.0)
        )
        table.style = 'Table Grid'

        patient = order.patient
        proc_name = (
            order.proc.name
            if order.proc
            else order.procedure
        ) or ''

        ref_name = (
            order.referring_doctor.name
            if getattr(order, 'referring_doctor', None)
            else ''
        )

        values = [
            (
                'Patient Name',
                patient.name or '',
                'Patient ID',
                patient.patient_id or ''
            ),
            (
                'DOB',
                str(patient.dob or ''),
                'Sex',
                patient.sex or ''
            ),
            (
                'Accession',
                order.accession or '',
                'Modality',
                order.modality or ''
            ),
            (
                'Exam',
                proc_name,
                'Study Date',
                str(order.scheduled or '')
            ),
            (
                'Referring Doctor',
                ref_name,
                'Report Status',
                report.status or 'DRAFT'
            ),
        ]

        for r, row in enumerate(values):
            for c, val in enumerate(row):
                table.cell(r, c).text = str(val)

        doc.add_paragraph(
            f'RIS_ACCESSION: {order.accession}'
        )

        doc.add_heading(
            proc_name or 'Radiology Report',
            level=1
        )

        doc.add_heading('FINDINGS', level=2)
        doc.add_paragraph(report.findings or '')

        doc.add_heading('IMPRESSION', level=2)
        doc.add_paragraph(report.impression or '')

        if report.radiologist:
            doc.add_paragraph(
                f'RADIOLOGIST: {report.radiologist}'
            )

        out = _rb.io.BytesIO()
        doc.save(out)
        out.seek(0)

        return _rb.send_file(
            out,
            as_attachment=True,
            download_name=_rb.build_report_filename(
                order,
                version_no,
                'DRAFT',
                'docx'
            ),
            mimetype=(
                'application/vnd.openxmlformats-officedocument.'
                'wordprocessingml.document'
            )
        )
    return api_ohif_report_word


def install_0867(_rb):
    @_rb.app.post('/api/ohif/report/<int:order_id>/word/draft')
    @_rb.require_ohif_token
    def api_ohif_report_word_draft(order_id):
        import os
        import uuid

        from report_transaction_writer import (
            commit_report_version,
            TransactionalReportCommitError,
        )

        order = _rb.Order.query.get_or_404(order_id)

        context_block = _rb.require_valid_ohif_case_context(order)
        if context_block:
            return context_block

        doctor_user, identity_block = \
            _rb.require_ohif_doctor_user(order.id)

        if identity_block:
            return identity_block

        try:
            report=_rb.get_report(order)
            _rb.assert_not_final(report)
            _rb.assert_role_allowed(doctor_user,'DRAFT')

            lease_token=str(
                _rb.request.headers.get('X-RadBridge-Report-Lease') or
                (_rb.request.get_json(silent=True) or {}).get('lease_token') or
                _rb.request.form.get('lease_token') or
                ''
            ).strip()

            _rb.assert_lease_owner(
                db=_rb.db,
                order=order,
                report=report,
                user=doctor_user,
                lease_token=lease_token,
            )

        except _rb.ReportEditControlError as exc:
            code=getattr(exc,'code',type(exc).__name__)

            try:
                _rb.audit(
                    'REPORT_EDIT_DENIED',
                    'order',
                    order.id,
                    f'action=DRAFT; editor=WORD; code={code}; user={doctor_user.id}'
                )
                _rb.db.session.commit()
            except Exception:
                _rb.db.session.rollback()

            return _rb.jsonify({
                'ok':False,
                'error':code,
            }), 409 if code in (
                'FINAL_REPORT_LOCKED',
                'REPORT_EDIT_LOCKED',
            ) else 403

        report = _rb.get_report(order)

        if (report.status or '').upper() == 'FINAL':
            return _rb.jsonify({
                'ok': False,
                'error': 'FINAL_REPORT_LOCKED'
            }), 409

        if 'base_version_no' not in _rb.request.form:
            return _rb.jsonify({
                'ok': False,
                'error': 'BASE_VERSION_REQUIRED'
            }), 400

        commit_id = str(
            _rb.request.form.get('commit_id')
            or uuid.uuid4()
        )

        document = _rb.request.files.get('document')

        tmppath, validation, status_code = \
            _rb._ohif_validate_word_upload(
                order,
                document,
                final=False
            )

        if not tmppath:
            return _rb.jsonify(validation), status_code

        owned_artifact = None

        try:
            findings, impression, radiologist = \
                _rb.extract_docx_sections(tmppath)

            radiologist = str(
                (
                    radiologist
                    if radiologist
                    and radiologist != '____________________'
                    else (
                        doctor_user.full_name
                        or doctor_user.username
                        or ''
                    )
                )
            ).strip()

            result = commit_report_version(
                db=_rb.db,
                Report=_rb.Report,
                ReportVersion=_rb.ReportVersion,
                report_root=_rb.REPORT_DIR,
                order=order,
                patient=order.patient,
                user=doctor_user,
                editor_type='WORD',
                requested_status='DRAFT',
                source_file=tmppath,
                base_version_no=int(
                    _rb.request.form['base_version_no']
                ),
                commit_id=commit_id,
                findings=findings or '',
                impression=impression or '',
                radiologist=radiologist,
                change_summary='OHIF Word Upload Draft',
            )

            version = result.get('version')

            if version is not None and not result.get('retry'):
                owned_artifact = version.docx_path

            _rb.audit_as_user(
                doctor_user,
                'REPORT_VERSION_COMMITTED',
                'order',
                order.id,
                (
                    f"version={(version.version_no if version is not None else None)}; "
                    "editor=WORD; status=DRAFT; "
                    "patient_safety=MATCH"
                )
            )

            _rb.db.session.commit()

            payload = _rb._ohif_report_json(order, report)

            payload.update({
                'ok': True,
                'patient_safety': validation['safety'],
                'version_no': (version.version_no if version is not None else None),
                'commit_id': (
                    result.get('commit_id')
                    or commit_id
                ),
                'editor_type': 'WORD',
                'status': 'DRAFT',
            })

            return _rb.jsonify(payload)

        except TransactionalReportCommitError as exc:
            _rb.db.session.rollback()

            if owned_artifact:
                try:
                    os.unlink(owned_artifact)
                except FileNotFoundError:
                    pass

            return _rb.jsonify({
                'ok': False,
                'error': getattr(
                    exc,
                    'code',
                    type(exc).__name__
                ),
                'message': str(exc)
            }), 409

        except Exception as exc:
            _rb.db.session.rollback()

            if owned_artifact:
                try:
                    os.unlink(owned_artifact)
                except FileNotFoundError:
                    pass

            return _rb.jsonify({
                'ok': False,
                'error': type(exc).__name__,
                'message': str(exc)
            }), 400

        finally:
            if tmppath:
                try:
                    os.unlink(tmppath)
                except FileNotFoundError:
                    pass

                try:
                    os.rmdir(os.path.dirname(tmppath))
                except OSError:
                    pass
    return api_ohif_report_word_draft


def install_0868(_rb):
    @_rb.app.post('/api/ohif/report/<int:order_id>/word/verify')
    @_rb.require_ohif_token
    def api_ohif_report_word_verify(order_id):
        order = _rb.Order.query.get_or_404(order_id)

        context_block = _rb.require_valid_ohif_case_context(order)
        if context_block:
            return context_block

        doctor_user, identity_block = \
            _rb.require_ohif_doctor_user(order.id)

        if identity_block:
            return identity_block

        try:
            report=_rb.get_report(order)
            _rb.assert_not_final(report)
            _rb.assert_role_allowed(doctor_user,'VERIFY')
            _rb.assert_no_foreign_active_lease(
                db=_rb.db,
                order_id=order.id,
                user=doctor_user,
            )

        except _rb.ReportEditControlError as exc:
            code=getattr(exc,'code',type(exc).__name__)

            try:
                _rb.audit(
                    'REPORT_EDIT_DENIED',
                    'order',
                    order.id,
                    f'action=VERIFY; editor=WORD; code={code}; user={doctor_user.id}'
                )
                _rb.db.session.commit()
            except Exception:
                _rb.db.session.rollback()

            return _rb.jsonify({
                'ok':False,
                'error':code,
            }), 409 if code in (
                'FINAL_REPORT_LOCKED',
                'REPORT_EDIT_LOCKED',
            ) else 403

        demographic_ok, demographic_reason = \
            _rb.pacs_demographic_gate(order)

        if not demographic_ok:
            return _rb.jsonify({
                'ok': False,
                'error': 'PACS_DEMOGRAPHIC_REVIEW_REQUIRED',
                'reason': demographic_reason
            }), 409

        data = _rb.request.get_json(silent=True) or {}

        if 'base_version_no' not in data:
            return _rb.jsonify({
                'ok': False,
                'error': 'BASE_VERSION_REQUIRED'
            }), 400

        try:
            from report_commit_core import (
                validate_base_version,
            )

            from onlyoffice_report_bridge import (
                onlyoffice_verify_latest,
            )

            report = _rb.get_report(order)

            latest = _rb._rb_latest_report_version(report)

            if latest is None:
                raise ValueError('NO_REPORT_VERSION')

            if str(latest.editor_type or '').upper() != 'WORD':
                return _rb.jsonify({
                    'ok': False,
                    'error': 'LATEST_VERSION_NOT_WORD',
                    'version_no': latest.version_no,
                    'editor_type': latest.editor_type
                }), 409

            validate_base_version(
                current_version_no=int(latest.version_no),
                base_version_no=int(data['base_version_no']),
            )

            before_count = (
                _rb.ReportVersion.query
                .filter_by(report_id=report.id)
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
                .filter_by(report_id=report.id)
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
                    'editor=WORD'
                )
            )

            _rb.db.session.commit()

            return _rb.jsonify({
                'ok': True,
                'status': 'VERIFIED',
                'version_no': version.version_no,
                'authoritative': True,
                'editor_type': 'WORD'
            })

        except Exception as exc:
            _rb.db.session.rollback()

            code = getattr(
                exc,
                'code',
                type(exc).__name__
            )

            status = 409 if code in (
                'REPORT_VERSION_CONFLICT',
                'REPORT_VERSION_DUPLICATE',
                'REPORT_VERIFY_CONFLICT',
            ) else 400

            return _rb.jsonify({
                'ok': False,
                'error': code,
                'message': str(exc)
            }), status
    return api_ohif_report_word_verify


def install_0869(_rb):
    @_rb.app.post('/api/ohif/report/<int:order_id>/word/finalize')
    @_rb.require_ohif_token
    def api_ohif_report_word_finalize(order_id):
        order = _rb.Order.query.get_or_404(order_id)

        context_block = _rb.require_valid_ohif_case_context(order)
        if context_block:
            return context_block

        doctor_user, identity_block = \
            _rb.require_ohif_doctor_user(order.id)

        if identity_block:
            return identity_block

        try:
            report=_rb.get_report(order)
            _rb.assert_not_final(report)
            _rb.assert_role_allowed(doctor_user,'FINALIZE')
            _rb.assert_no_foreign_active_lease(
                db=_rb.db,
                order_id=order.id,
                user=doctor_user,
            )

        except _rb.ReportEditControlError as exc:
            code=getattr(exc,'code',type(exc).__name__)

            try:
                _rb.audit(
                    'REPORT_EDIT_DENIED',
                    'order',
                    order.id,
                    f'action=FINALIZE; editor=WORD; code={code}; user={doctor_user.id}'
                )
                _rb.db.session.commit()
            except Exception:
                _rb.db.session.rollback()

            return _rb.jsonify({
                'ok':False,
                'error':code,
            }), 409 if code in (
                'FINAL_REPORT_LOCKED',
                'REPORT_EDIT_LOCKED',
            ) else 403

        demographic_ok, demographic_reason = \
            _rb.pacs_demographic_gate(order)

        if not demographic_ok:
            return _rb.jsonify({
                'ok': False,
                'error': 'PACS_DEMOGRAPHIC_REVIEW_REQUIRED',
                'reason': demographic_reason
            }), 409

        data = _rb.request.get_json(silent=True) or {}

        if 'base_version_no' not in data:
            return _rb.jsonify({
                'ok': False,
                'error': 'BASE_VERSION_REQUIRED'
            }), 400

        try:
            from report_commit_core import (
                validate_base_version,
            )

            from onlyoffice_report_bridge import (
                onlyoffice_finalize_latest,
            )

            report = _rb.get_report(order)

            latest = _rb._rb_latest_report_version(report)

            if latest is None:
                return _rb.jsonify({
                    'ok': False,
                    'error': 'NO_REPORT_VERSION'
                }), 409

            if str(latest.editor_type or '').upper() != 'WORD':
                return _rb.jsonify({
                    'ok': False,
                    'error': 'LATEST_VERSION_NOT_WORD',
                    'version_no': latest.version_no,
                    'editor_type': latest.editor_type
                }), 409

            if (
                (report.status or '').upper() == 'FINAL'
                or latest.finalized_at is not None
            ):
                return _rb.jsonify({
                    'ok': False,
                    'error': 'FINAL_REPORT_LOCKED'
                }), 409

            if (latest.status or '').upper() != 'VERIFIED':
                return _rb.jsonify({
                    'ok': False,
                    'error': 'LATEST_VERSION_NOT_VERIFIED',
                    'version_no': latest.version_no,
                    'status': latest.status
                }), 409

            validate_base_version(
                current_version_no=int(latest.version_no),
                base_version_no=int(data['base_version_no']),
            )

            before_count = (
                _rb.ReportVersion.query
                .filter_by(report_id=report.id)
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
                .filter_by(report_id=report.id)
                .count()
            )

            if after_count != before_count:
                _rb.db.session.rollback()
                raise RuntimeError(
                    'FINALIZE_CREATED_EXTRA_VERSION'
                )

            _rb.audit_as_user(
                doctor_user,
                'REPORT_FINALIZED',
                'order',
                order.id,
                (
                    f'version={version.version_no}; '
                    'editor=WORD; '
                    'content_immutable=YES'
                )
            )

            _rb.db.session.commit()

            _rb.queue_final_delivery(order)

            _rb.enqueue_event(
                'REPORT_FINALIZED',
                'order',
                order.id,
                {
                    'accession': order.accession,
                    'version_no': version.version_no,
                    'source': 'OHIF_WORD'
                }
            )

            _rb.db.session.commit()

            return _rb.jsonify({
                'ok': True,
                'status': 'FINALIZED',
                'version_no': version.version_no,
                'authoritative': True,
                'editor_type': 'WORD'
            })

        except Exception as exc:
            _rb.db.session.rollback()

            code = getattr(
                exc,
                'code',
                type(exc).__name__
            )

            status = 409 if code in (
                'REPORT_VERSION_CONFLICT',
                'REPORT_VERSION_DUPLICATE',
                'REPORT_FINALIZE_CONFLICT',
            ) else 400

            return _rb.jsonify({
                'ok': False,
                'error': code,
                'message': str(exc)
            }), status
    return api_ohif_report_word_finalize


def install_0870(_rb):
    @_rb.app.post('/api/ohif/report/<int:order_id>/lease/acquire')
    @_rb.require_ohif_token
    def api_ohif_report_lease_acquire(order_id):
        import secrets

        order=_rb.Order.query.get_or_404(order_id)

        context_block=_rb.require_valid_ohif_case_context(order)
        if context_block:
            return context_block

        doctor_user, identity_block = \
            _rb.require_ohif_doctor_user(order.id)

        if identity_block:
            return identity_block

        report=_rb.get_report(order)
        data=_rb.request.get_json(silent=True) or {}

        editor_type=str(
            data.get('editor_type') or 'OHIF'
        ).strip().upper()

        supplied_token=str(
            data.get('lease_token') or
            _rb.request.headers.get('X-RadBridge-Report-Lease') or
            ''
        ).strip()

        lease_token=(
            supplied_token
            if supplied_token
            else secrets.token_urlsafe(32)
        )

        try:
            lease=_rb.acquire_or_renew_lease(
                db=_rb.db,
                order=order,
                report=report,
                user=doctor_user,
                editor_type=editor_type,
                lease_token=lease_token,
            )

            _rb.audit_as_user(doctor_user,
                'REPORT_EDIT_LEASE_ACQUIRED',
                'order',
                order.id,
                f'editor={editor_type}; user={doctor_user.id}'
            )

            _rb.db.session.commit()

            return _rb.jsonify({
                'ok': True,
                'lease_token': lease_token,
                'editor_type': lease.editor_type,
                'expires_at': lease.expires_at.isoformat(),
            })

        except _rb.ReportEditControlError as exc:
            _rb.db.session.rollback()

            code=getattr(
                exc,
                'code',
                type(exc).__name__
            )

            try:
                _rb.audit_as_user(doctor_user,
                    'REPORT_EDIT_LEASE_DENIED',
                    'order',
                    order.id,
                    f'editor={editor_type}; code={code}; user={doctor_user.id}'
                )
                _rb.db.session.commit()
            except Exception:
                _rb.db.session.rollback()

            return _rb.jsonify({
                'ok': False,
                'error': code,
            }), 409 if code in (
                'FINAL_REPORT_LOCKED',
                'REPORT_EDIT_LOCKED',
            ) else 403
    return api_ohif_report_lease_acquire


def install_0871(_rb):
    @_rb.app.post('/api/ohif/report/<int:order_id>/lease/release')
    @_rb.require_ohif_token
    def api_ohif_report_lease_release(order_id):
        order=_rb.Order.query.get_or_404(order_id)

        context_block=_rb.require_valid_ohif_case_context(order)
        if context_block:
            return context_block

        doctor_user, identity_block = \
            _rb.require_ohif_doctor_user(order.id)

        if identity_block:
            return identity_block

        data=_rb.request.get_json(silent=True) or {}

        lease_token=str(
            data.get('lease_token') or
            _rb.request.headers.get('X-RadBridge-Report-Lease') or
            ''
        ).strip()

        if not lease_token:
            return _rb.jsonify({
                'ok': False,
                'error': 'REPORT_LEASE_TOKEN_REQUIRED',
            }), 400

        try:
            deleted=_rb.release_lease(
                db=_rb.db,
                order_id=order.id,
                user_id=doctor_user.id,
                lease_token=lease_token,
            )

            _rb.audit_as_user(doctor_user,
                'REPORT_EDIT_LEASE_RELEASED',
                'order',
                order.id,
                f'user={doctor_user.id}; released={deleted}'
            )

            _rb.db.session.commit()

            return _rb.jsonify({
                'ok': True,
                'released': deleted,
            })

        except Exception:
            _rb.db.session.rollback()
            raise
    return api_ohif_report_lease_release


def install_0872(_rb):
    @_rb.app.post('/api/ohif/report/<int:order_id>/draft')
    @_rb.require_ohif_token
    def api_ohif_report_draft(order_id):
        import os
        import tempfile
        import uuid

        from report_transaction_writer import (
            commit_report_version,
            TransactionalReportCommitError,
        )

        order = _rb.Order.query.get_or_404(order_id)

        context_block = _rb.require_valid_ohif_case_context(order)
        if context_block:
            return context_block

        doctor_user, identity_block = \
            _rb.require_ohif_doctor_user(order.id)

        if identity_block:
            return identity_block

        try:
            report=_rb.get_report(order)
            _rb.assert_not_final(report)
            _rb.assert_role_allowed(doctor_user,'DRAFT')

            lease_token=str(
                _rb.request.headers.get('X-RadBridge-Report-Lease') or
                (_rb.request.get_json(silent=True) or {}).get('lease_token') or
                _rb.request.form.get('lease_token') or
                ''
            ).strip()

            _rb.assert_lease_owner(
                db=_rb.db,
                order=order,
                report=report,
                user=doctor_user,
                lease_token=lease_token,
            )

        except _rb.ReportEditControlError as exc:
            code=getattr(exc,'code',type(exc).__name__)

            try:
                _rb.audit(
                    'REPORT_EDIT_DENIED',
                    'order',
                    order.id,
                    f'action=DRAFT; editor=OHIF; code={code}; user={doctor_user.id}'
                )
                _rb.db.session.commit()
            except Exception:
                _rb.db.session.rollback()

            return _rb.jsonify({
                'ok':False,
                'error':code,
            }), 409 if code in (
                'FINAL_REPORT_LOCKED',
                'REPORT_EDIT_LOCKED',
            ) else 403

        report = _rb.get_report(order)

        if (report.status or '').upper() == 'FINAL':
            return _rb.jsonify({
                'ok': False,
                'error': 'FINAL_REPORT_LOCKED'
            }), 409

        data = _rb.request.get_json(silent=True) or {}

        if 'base_version_no' not in data:
            return _rb.jsonify({
                'ok': False,
                'error': 'BASE_VERSION_REQUIRED'
            }), 400

        findings = str(data.get('findings') or '').strip()
        impression = str(data.get('impression') or '').strip()

        radiologist = str(
            data.get('radiologist')
            or doctor_user.full_name
            or doctor_user.username
            or ''
        ).strip()

        commit_id = str(
            data.get('commit_id')
            or uuid.uuid4()
        )

        old_findings = report.findings
        old_impression = report.impression
        old_radiologist = report.radiologist

        tmp_path = None

        try:
            # Build browser content into a DOCX source artifact
            # without committing legacy Report state.
            report.findings = findings
            report.impression = impression
            report.radiologist = radiologist

            buf = _rb.make_docx(order, report)

            fd, tmp_path = tempfile.mkstemp(
                prefix='radbridge-browser-',
                suffix='.docx'
            )

            with os.fdopen(fd, 'wb') as fh:
                fh.write(buf.getvalue())

            # Restore mutable Report fields BEFORE transactional commit.
            report.findings = old_findings
            report.impression = old_impression
            report.radiologist = old_radiologist

            result = commit_report_version(
                db=_rb.db,
                Report=_rb.Report,
                ReportVersion=_rb.ReportVersion,
                report_root=_rb.REPORT_DIR,
                order=order,
                patient=order.patient,
                user=doctor_user,
                editor_type='BROWSER',
                requested_status='DRAFT',
                source_file=tmp_path,
                base_version_no=int(data['base_version_no']),
                commit_id=commit_id,
                findings=findings,
                impression=impression,
                radiologist=radiologist,
                change_summary='OHIF Browser Editor Draft',
            )

            version = result.get('version')

            # The unified writer flushes but intentionally does not commit.
            # This HTTP route owns the transaction boundary.
            created_artifact = None

            if (
                version is not None
                and not result.get('retry', False)
            ):
                created_artifact = version.docx_path

            try:
                _rb.db.session.commit()
            except Exception:
                _rb.db.session.rollback()

                if (
                    created_artifact
                    and os.path.isfile(created_artifact)
                ):
                    try:
                        os.unlink(created_artifact)
                    except Exception:
                        pass

                raise

            payload = _rb._ohif_report_json(order, report)

            payload.update({
                'ok': True,
                'version_no': (
                    version.version_no
                    if version is not None
                    else result.get('version_no')
                ),
                'commit_id': result.get('commit_id') or commit_id,
                'editor_type': 'BROWSER',
                'status': 'DRAFT',
            })

            return _rb.jsonify(payload)

        except TransactionalReportCommitError as exc:
            _rb.db.session.rollback()

            report.findings = old_findings
            report.impression = old_impression
            report.radiologist = old_radiologist

            return _rb.jsonify({
                'ok': False,
                'error': getattr(exc, 'code', type(exc).__name__),
                'message': str(exc)
            }), 409

        except Exception as exc:
            _rb.db.session.rollback()

            report.findings = old_findings
            report.impression = old_impression
            report.radiologist = old_radiologist

            return _rb.jsonify({
                'ok': False,
                'error': type(exc).__name__,
                'message': str(exc)
            }), 400

        finally:
            if tmp_path:
                try:
                    os.unlink(tmp_path)
                except FileNotFoundError:
                    pass
    return api_ohif_report_draft


def install_0873(_rb):
    @_rb.app.post('/api/ohif/report/<int:order_id>/verify')
    @_rb.require_ohif_token
    def api_ohif_report_verify(order_id):
        order = _rb.Order.query.get_or_404(order_id)

        context_block = _rb.require_valid_ohif_case_context(order)
        if context_block:
            return context_block

        doctor_user, identity_block = \
            _rb.require_ohif_doctor_user(order.id)

        if identity_block:
            return identity_block

        try:
            report=_rb.get_report(order)
            _rb.assert_not_final(report)
            _rb.assert_role_allowed(doctor_user,'VERIFY')
            _rb.assert_no_foreign_active_lease(
                db=_rb.db,
                order_id=order.id,
                user=doctor_user,
            )

        except _rb.ReportEditControlError as exc:
            code=getattr(exc,'code',type(exc).__name__)

            try:
                _rb.audit(
                    'REPORT_EDIT_DENIED',
                    'order',
                    order.id,
                    f'action=VERIFY; editor=OHIF; code={code}; user={doctor_user.id}'
                )
                _rb.db.session.commit()
            except Exception:
                _rb.db.session.rollback()

            return _rb.jsonify({
                'ok':False,
                'error':code,
            }), 409 if code in (
                'FINAL_REPORT_LOCKED',
                'REPORT_EDIT_LOCKED',
            ) else 403

        demographic_ok, demographic_reason = \
            _rb.pacs_demographic_gate(order)

        if not demographic_ok:
            return _rb.jsonify({
                'ok': False,
                'error': 'PACS_DEMOGRAPHIC_REVIEW_REQUIRED',
                'reason': demographic_reason
            }), 409

        data = _rb.request.get_json(silent=True) or {}

        if 'base_version_no' not in data:
            return _rb.jsonify({
                'ok': False,
                'error': 'BASE_VERSION_REQUIRED'
            }), 400

        try:
            from report_commit_core import (
                validate_base_version,
            )

            from onlyoffice_report_bridge import (
                onlyoffice_verify_latest,
            )

            report = _rb.get_report(order)

            latest = _rb._rb_latest_report_version(report)

            if latest is None:
                raise ValueError('NO_REPORT_VERSION')

            validate_base_version(
                current_version_no=int(latest.version_no),
                base_version_no=int(data['base_version_no']),
            )

            before_count = (
                _rb.ReportVersion.query
                .filter_by(report_id=report.id)
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
                .filter_by(report_id=report.id)
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
                    'editor=BROWSER'
                )
            )

            _rb.db.session.commit()

            return _rb.jsonify({
                'ok': True,
                'status': 'VERIFIED',
                'version_no': version.version_no,
                'authoritative': True,
                'editor_type': 'BROWSER'
            })

        except Exception as exc:
            _rb.db.session.rollback()

            code = getattr(
                exc,
                'code',
                type(exc).__name__
            )

            status = 409 if code in (
                'REPORT_VERSION_CONFLICT',
                'REPORT_VERSION_DUPLICATE',
                'REPORT_VERIFY_CONFLICT',
            ) else 400

            return _rb.jsonify({
                'ok': False,
                'error': code,
                'message': str(exc)
            }), status
    return api_ohif_report_verify


def install_0874(_rb):
    @_rb.app.post('/api/ohif/report/<int:order_id>/finalize')
    @_rb.require_ohif_token
    def api_ohif_report_finalize(order_id):
        order = _rb.Order.query.get_or_404(order_id)

        context_block = _rb.require_valid_ohif_case_context(order)
        if context_block:
            return context_block

        doctor_user, identity_block = \
            _rb.require_ohif_doctor_user(order.id)

        if identity_block:
            return identity_block

        try:
            report=_rb.get_report(order)
            _rb.assert_not_final(report)
            _rb.assert_role_allowed(doctor_user,'FINALIZE')
            _rb.assert_no_foreign_active_lease(
                db=_rb.db,
                order_id=order.id,
                user=doctor_user,
            )

        except _rb.ReportEditControlError as exc:
            code=getattr(exc,'code',type(exc).__name__)

            try:
                _rb.audit(
                    'REPORT_EDIT_DENIED',
                    'order',
                    order.id,
                    f'action=FINALIZE; editor=OHIF; code={code}; user={doctor_user.id}'
                )
                _rb.db.session.commit()
            except Exception:
                _rb.db.session.rollback()

            return _rb.jsonify({
                'ok':False,
                'error':code,
            }), 409 if code in (
                'FINAL_REPORT_LOCKED',
                'REPORT_EDIT_LOCKED',
            ) else 403

        demographic_ok, demographic_reason = \
            _rb.pacs_demographic_gate(order)

        if not demographic_ok:
            return _rb.jsonify({
                'ok': False,
                'error': 'PACS_DEMOGRAPHIC_REVIEW_REQUIRED',
                'reason': demographic_reason
            }), 409

        data = _rb.request.get_json(silent=True) or {}

        if 'base_version_no' not in data:
            return _rb.jsonify({
                'ok': False,
                'error': 'BASE_VERSION_REQUIRED'
            }), 400

        try:
            from report_commit_core import (
                validate_base_version,
            )

            from onlyoffice_report_bridge import (
                onlyoffice_finalize_latest,
            )

            report = _rb.get_report(order)

            latest = _rb._rb_latest_report_version(report)

            if latest is None:
                return _rb.jsonify({
                    'ok': False,
                    'error': 'NO_REPORT_VERSION'
                }), 409

            if (
                (report.status or '').upper() == 'FINAL'
                or latest.finalized_at is not None
            ):
                return _rb.jsonify({
                    'ok': False,
                    'error': 'FINAL_REPORT_LOCKED'
                }), 409

            if (latest.status or '').upper() != 'VERIFIED':
                return _rb.jsonify({
                    'ok': False,
                    'error': 'LATEST_VERSION_NOT_VERIFIED',
                    'version_no': latest.version_no,
                    'status': latest.status
                }), 409

            validate_base_version(
                current_version_no=int(latest.version_no),
                base_version_no=int(data['base_version_no']),
            )

            before_count = (
                _rb.ReportVersion.query
                .filter_by(report_id=report.id)
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
                .filter_by(report_id=report.id)
                .count()
            )

            if after_count != before_count:
                _rb.db.session.rollback()
                raise RuntimeError(
                    'FINALIZE_CREATED_EXTRA_VERSION'
                )

            _rb.audit_as_user(
                doctor_user,
                'REPORT_FINALIZED',
                'order',
                order.id,
                (
                    f'version={version.version_no}; '
                    'editor=BROWSER; '
                    'content_immutable=YES'
                )
            )

            _rb.db.session.commit()

            _rb.queue_final_delivery(order)

            _rb.enqueue_event(
                'REPORT_FINALIZED',
                'order',
                order.id,
                {
                    'accession': order.accession,
                    'version_no': version.version_no,
                    'source': 'BROWSER'
                }
            )

            _rb.db.session.commit()

            return _rb.jsonify({
                'ok': True,
                'status': 'FINALIZED',
                'version_no': version.version_no,
                'authoritative': True
            })

        except Exception as exc:
            _rb.db.session.rollback()

            code = getattr(
                exc,
                'code',
                type(exc).__name__
            )

            status = 409 if code in (
                'REPORT_VERSION_CONFLICT',
                'REPORT_VERSION_DUPLICATE',
                'REPORT_FINALIZE_CONFLICT',
            ) else 400

            return _rb.jsonify({
                'ok': False,
                'error': code,
                'message': str(exc)
            }), status
    return api_ohif_report_finalize


def install_0875(_rb):
    @_rb.app.post('/api/ohif/report/<int:order_id>/return')
    @_rb.require_ohif_token
    def api_ohif_report_return(order_id):
        order = _rb.Order.query.get_or_404(order_id)

        context_block = _rb.require_valid_ohif_case_context(order)
        if context_block:
            return context_block

        doctor_user, identity_block = _rb.require_ohif_doctor_user(order.id)
        if identity_block:
            return identity_block

        from technician_queue import mutable_return
        mutable_return(_rb._reporting_support_sys.modules[_rb.__name__],order)

        data = _rb._ohif_json_body()

        u = doctor_user

        code = str(data.get('reason_code') or 'OTHER').upper()
        note = str(data.get('note') or '').strip()

        rr = _rb.CaseReturnReason.query.filter_by(
            code=code,
            active=True
        ).first()

        if not rr or len(note)<5 or len(note)>10000:
            _rb.abort(400)
        action_owner=str(data.get('action_owner') or '').strip().upper()
        if action_owner not in ('','TECHNICIAN'):
            _rb.abort(400)
        route = action_owner or rr.route_to

        _rb.db.session.add(
            _rb.CaseWorkflowEvent(
                order_id=order.id,
                event_type='RETURNED',
                owner_role=route,
                reason_code=code,
                note=note,
                created_by=(u.id if u else None)
            )
        )

        for a in _rb.CaseAssignment.query.filter_by(
            order_id=order.id,
            active=True
        ).all():
            a.active = False
            a.unassigned_at = _rb.datetime.utcnow()

        _rb.create_ris_notification(
            order,
            'RETURNED_TO_TECH' if route == 'TECHNICIAN' else 'CASE_RETURNED',
            'Case returned for correction',
            f'{code}: {note}',
            'WARNING',
            route,
            commit=False
        )

        _rb.audit_as_user(
            u,
            'CASE_RETURNED_FOR_ACTION',
            'order',
            order.id,
            f'OHIF; reason={code}; route={route}; note={note}'
        )

        _rb.db.session.commit()

        return _rb.jsonify({
            'ok': True,
            'order_id': order.id,
            'accession': order.accession,
            'status': 'RETURNED',
            'reason_code': code,
            'route_to': route
        })
    return api_ohif_report_return


def install_0886(_rb):
    @_rb.app.route('/api/ohif/report/<int:order_id>/preferences', methods=['GET','POST'])
    @_rb.require_ohif_token
    def api_ohif_reporting_preferences(order_id):
        order = _rb.Order.query.get_or_404(order_id)

        context_block = _rb.require_valid_ohif_case_context(order)
        if context_block:
            return context_block

        doctor_user, identity_block = (
            _rb.require_ohif_doctor_user(order.id)
        )

        if identity_block:
            return identity_block

        profile = _rb.get_user_profile(doctor_user)

        prefs = _rb.user_reporting_preferences(
            profile
        )
        if _rb.request.method=='POST':
            body=_rb.request.get_json(silent=True)
            if not isinstance(body,dict):
                return _rb.jsonify(ok=False,message='A JSON preference object is required.'),400
            layout=body.get('preferred_layout')
            if layout not in {'50_50','70_30','30_70','FULL_EDITOR','FULL_VIEWER','DUAL_MONITOR','CASCADE','NEW_WINDOW'}:
                return _rb.jsonify(ok=False,message='Unsupported reporting layout.'),400
            prefs=_rb.set_user_reporting_preferences(profile,prefs['preferred_editor'],layout,prefs['preferred_display'])
            _rb.audit_as_user(doctor_user,'OHIF_REPORTING_PREFERENCES_UPDATED','order',order.id,'layout='+layout)
            _rb.db.session.commit()
            return _rb.jsonify(ok=True,order_id=order.id,**prefs)


        _rb.audit_as_user(
            doctor_user,
            'OHIF_REPORTING_PREFERENCES_READ',
            'order',
            order.id,
            (
                'editor=' +
                prefs['preferred_editor'] +
                '; layout=' +
                prefs['preferred_layout'] +
                '; display=' + prefs['preferred_display']
            )
        )

        _rb.db.session.commit()

        return _rb.jsonify({
            'ok': True,
            'order_id': order.id,
            'preferred_editor': (
                prefs['preferred_editor']
            ),
            'preferred_display': prefs['preferred_display'],
            'preferred_layout': (
                prefs['preferred_layout']
            )
        })
    return api_ohif_reporting_preferences


def install_0888(_rb):
    @_rb.app.get('/api/ohif/report/<int:order_id>/onlyoffice/config')
    @_rb.require_ohif_token
    def api_ohif_onlyoffice_config(order_id):
        order = _rb.Order.query.get_or_404(order_id)

        context_block = _rb.require_valid_ohif_case_context(order)
        if context_block:
            return context_block

        doctor_user, identity_block = \
            _rb.require_ohif_doctor_user(order.id)

        if identity_block:
            return identity_block

        report = _rb.get_report(order)

        report_status = str(
            report.status or 'DRAFT'
        ).upper()

        is_final = report_status == 'FINAL'

        # RB_VERIFIED_READONLY_CONFIG_V1
        is_locked = report_status in (
            'VERIFIED',
            'FINAL',
        )

        # Locked reports must always use their committed authoritative
        # document. Never require or reconstruct an editable working copy
        # for VERIFIED or FINAL reports.
        authoritative = (
            _rb._rb_authoritative_docx_download(
                order,
                report,
            )
            if is_locked
            else None
        )

        if is_locked:
            if not authoritative:
                return _rb.jsonify({
                    'ok': False,
                    'error': (
                        'FINAL_REPORT_DOCUMENT_NOT_FOUND'
                        if is_final
                        else 'VERIFIED_REPORT_DOCUMENT_NOT_FOUND'
                    )
                }), 404

            path = authoritative['path']
        else:
            from report_template_library import initialize, TemplateError
            import sys as _report_template_sys
            try:
                template_id = _rb.request.args.get('template_id', type=int)
                if _rb.request.args.get('template_id') and (template_id is None or template_id < 0):
                    raise TemplateError('Invalid template selection.')
                # Template selection changes a draft document and requires its edit lock.
                if template_id is not None:
                    _rb.assert_role_allowed(doctor_user, 'DRAFT')
                    _rb.assert_lease_owner(db=_rb.db, order=order, report=report, user=doctor_user,
                        lease_token=str(_rb.request.headers.get('X-RadBridge-Report-Lease') or ''))
                path = initialize(_report_template_sys.modules[_rb.__name__], order, report, doctor_user, template_id)
            except (TemplateError, _rb.ReportEditControlError) as exc:
                _rb.db.session.rollback()
                return _rb.jsonify(ok=False, error=str(exc)), 409

        doc_token = _rb._onlyoffice_link_token(
            order.id,
            'document'
        )

        callback_token = _rb._onlyoffice_link_token(
            order.id,
            'callback'
        )

        document_url = (
            f'{_rb.ONLYOFFICE_RIS_INTERNAL_URL}'
            f'/api/ohif/report/{order.id}/onlyoffice/document'
            f'?token={_rb.quote(doc_token)}'
        )

        callback_url = (
            f'{_rb.ONLYOFFICE_RIS_INTERNAL_URL}'
            f'/api/ohif/report/{order.id}/onlyoffice/callback'
            f'?token={_rb.quote(callback_token)}'
        )

        st = _rb.os.stat(path)

        key = (
            f'rb-oo{_rb.ONLYOFFICE_KEY_REV}-'
            f'{order.id}-{report.id}-'
            f'{int(st.st_mtime)}-{st.st_size}'
        )

        user_name = (
            doctor_user.full_name
            or doctor_user.username
            or f'Doctor {doctor_user.id}'
        )

        if is_final:
            document_version_no = int(
                authoritative['version_no']
            )
            document_status = 'FINAL'
        elif is_locked:
            locked_version = _rb._rb_latest_report_version(
                report
            )

            if not locked_version:
                return _rb.jsonify({
                    'ok': False,
                    'error': 'VERIFIED_REPORT_VERSION_NOT_FOUND'
                }), 404

            document_version_no = int(
                locked_version.version_no
            )
            document_status = 'VERIFIED'
        else:
            document_version_no = _rb._next_report_version(
                report
            )
            document_status = 'DRAFT'

        config = {
            'document': {
                'fileType': 'docx',
                'key': key[:128],
                'title': _rb.build_report_filename(
                    order,
                    document_version_no,
                    document_status,
                    'docx'
                ),
                'url': document_url,
                'permissions': {
                    'edit': not is_locked,
                    'download': True,
                    'print': True
                }
            },
            'documentType': 'word',
            'editorConfig': {
                'callbackUrl': callback_url,
                'lang': 'en',
                'mode': (
                    'view'
                    if is_locked
                    else 'edit'
                ),
                'user': {
                    'id': str(doctor_user.id),
                    'name': user_name
                },
                'customization': {
                    # RB_ONLYOFFICE_AUTOSAVE_WORKING_COPY_V1
                    'autosave': not is_locked,
                    'forcesave': not is_locked,
                    'compactHeader': False
                }
            }
        }

        config['token'] = _rb._onlyoffice_jwt_encode(
            config
        )

        _rb.audit_as_user(
            doctor_user,
            'ONLYOFFICE_EDITOR_OPENED',
            'order',
            order.id,
            f'key={key[:128]}'
        )

        _rb.db.session.commit()

        latest_version = _rb._rb_latest_report_version(report)

        return _rb.jsonify({
            'ok': True,
            'config': config,
            'base_version_no': (
                int(latest_version.version_no)
                if latest_version
                else 0
            ),
            'report_status': (
                'FINAL'
                if is_final
                else (
                    str(
                        latest_version.status
                        or 'DRAFT'
                    ).upper()
                    if latest_version
                    else 'DRAFT'
                )
            ),
            'api_path': (
                '/onlyoffice/'
                'web-apps/apps/api/documents/api.js'
            )
        })
    return api_ohif_onlyoffice_config


def install_0892(_rb):
    @_rb.app.post('/api/ohif/report/<int:order_id>/onlyoffice/forcesave')
    @_rb.require_ohif_token
    def api_ohif_onlyoffice_forcesave(order_id):
        import time

        order = _rb.Order.query.get_or_404(order_id)

        context_block = _rb.require_valid_ohif_case_context(order)
        if context_block:
            return context_block

        doctor_user, identity_block = \
            _rb.require_ohif_doctor_user(order.id)

        if identity_block:
            return identity_block

        report = _rb.get_report(order)

        try:
            _rb.assert_not_final(report)

            _rb.assert_role_allowed(
                doctor_user,
                'DRAFT'
            )

            lease_token = str(
                _rb.request.headers.get(
                    'X-RadBridge-Report-Lease'
                ) or ''
            ).strip()

            _rb.assert_lease_owner(
                db=_rb.db,
                order=order,
                report=report,
                user=doctor_user,
                lease_token=lease_token,
            )

        except _rb.ReportEditControlError as exc:
            code = getattr(
                exc,
                'code',
                type(exc).__name__
            )

            return _rb.jsonify({
                'ok': False,
                'error': code,
            }), 409 if code in (
                'FINAL_REPORT_LOCKED',
                'REPORT_EDIT_LOCKED',
            ) else 403

        path = _rb._onlyoffice_working_path(order)

        if not path or not _rb.os.path.isfile(path):
            return _rb.jsonify({
                'ok': False,
                'error': 'ONLYOFFICE_WORKING_COPY_NOT_FOUND',
            }), 409

        # RB_ONLYOFFICE_DIRTY_FORCESAVE_V1
        forcesave_data = _rb.request.get_json(silent=True) or {}

        key = str(
            forcesave_data.get('document_key') or ''
        ).strip()

        document_dirty = bool(
            forcesave_data.get('document_dirty', False)
        )

        if not key:
            return _rb.jsonify({
                'ok': False,
                'error': 'ONLYOFFICE_DOCUMENT_KEY_REQUIRED',
            }), 400

        import uuid

        nonce = str(uuid.uuid4())

        command = {
            'c': 'forcesave',
            'key': key,
            'userdata': nonce,
        }

        try:
            token = _rb._onlyoffice_jwt_encode(command)

            r = _rb.requests.post(
                _rb.ONLYOFFICE_INTERNAL_URL
                + '/coauthoring/CommandService.ashx',
                json=command,
                headers={
                    'Authorization': f'Bearer {token}'
                },
                timeout=10,
            )

            r.raise_for_status()

            result = r.json() or {}

            onlyoffice_error = int(
                result.get('error') or 0
            )

            # A dirty browser must never convert error 4 into
            # a successful clinical save. Retry briefly, then require
            # a real callback acknowledgement.
            if onlyoffice_error == 4 and document_dirty:
                for _attempt in range(4):
                    time.sleep(0.75)

                    r = _rb.requests.post(
                        _rb.ONLYOFFICE_INTERNAL_URL
                        + '/coauthoring/CommandService.ashx',
                        json=command,
                        headers={
                            'Authorization': f'Bearer {token}'
                        },
                        timeout=10,
                    )

                    r.raise_for_status()
                    result = r.json() or {}
                    onlyoffice_error = int(
                        result.get('error') or 0
                    )

                    if onlyoffice_error != 4:
                        break

            if onlyoffice_error == 4:
                if document_dirty:
                    return _rb.jsonify({
                        'ok': False,
                        'forcesaved': False,
                        'error': (
                            'ONLYOFFICE_CHANGES_NOT_SYNCHRONIZED'
                        ),
                        'message': (
                            'The document is still synchronizing. '
                            'Wait a moment and save again.'
                        ),
                        'onlyoffice_error': 4,
                    }), 409

                return _rb.jsonify({
                    'ok': True,
                    'forcesaved': True,
                    'no_changes': True,
                    'onlyoffice_error': 4,
                })

            if onlyoffice_error != 0:
                return _rb.jsonify({
                    'ok': False,
                    'error': 'ONLYOFFICE_FORCESAVE_REJECTED',
                    'onlyoffice_error': onlyoffice_error,
                }), 409

            deadline = time.monotonic() + 12.0

            while time.monotonic() < deadline:
                time.sleep(0.25)

                if (
                    _rb._onlyoffice_read_forcesave_ack(
                        order.id
                    )
                    == nonce
                ):
                    return _rb.jsonify({
                        'ok': True,
                        'forcesaved': True,
                    })

            return _rb.jsonify({
                'ok': False,
                'error': 'ONLYOFFICE_FORCESAVE_CALLBACK_TIMEOUT',
            }), 504

        except Exception as exc:
            return _rb.jsonify({
                'ok': False,
                'error': 'ONLYOFFICE_FORCESAVE_FAILED',
                'message': str(exc),
            }), 502
    return api_ohif_onlyoffice_forcesave


def install_0893(_rb):
    @_rb.app.get('/api/ohif/report/<int:order_id>/onlyoffice/document')
    def api_ohif_onlyoffice_document(order_id):
        order = _rb.Order.query.get_or_404(order_id)

        token = str(
            _rb.request.args.get('token') or ''
        )

        if not _rb._onlyoffice_check_link_token(
            token,
            order.id,
            'document'
        ):
            return _rb.jsonify({
                'ok': False,
                'error': 'ONLYOFFICE_DOCUMENT_TOKEN_INVALID'
            }), 403

        report = _rb.get_report(order)

        report_status = str(
            report.status or 'DRAFT'
        ).upper()

        is_final = report_status == 'FINAL'
        is_locked = report_status in (
            'VERIFIED',
            'FINAL',
        )

        # VERIFIED and FINAL documents are immutable committed artifacts.
        # Serve their authoritative version and never require or recreate
        # an editable ONLYOFFICE working copy.
        if is_locked:
            authoritative = (
                _rb._rb_authoritative_docx_download(
                    order,
                    report,
                )
            )

            if not authoritative:
                return _rb.jsonify({
                    'ok': False,
                    'error': (
                        'FINAL_REPORT_DOCUMENT_NOT_FOUND'
                        if is_final
                        else 'VERIFIED_REPORT_DOCUMENT_NOT_FOUND'
                    )
                }), 404

            path = authoritative['path']
        else:
            path = _rb._onlyoffice_prepare_document(
                order,
                report
            )

        return _rb.send_file(
            path,
            as_attachment=False,
            download_name=_rb.os.path.basename(path),
            mimetype=(
                'application/vnd.openxmlformats-officedocument.'
                'wordprocessingml.document'
            )
        )
    return api_ohif_onlyoffice_document


def install_0899(_rb):
    @_rb.app.post(
        '/api/ohif/report/<int:order_id>/onlyoffice/commit-draft'
    )
    @_rb.require_ohif_token
    def api_ohif_onlyoffice_commit_draft(order_id):
        order = _rb.Order.query.get_or_404(order_id)

        context_block = _rb.require_valid_ohif_case_context(order)
        if context_block:
            return context_block

        doctor_user, identity_block = \
            _rb.require_ohif_doctor_user(order.id)

        if identity_block:
            return identity_block

        try:
            report=_rb.get_report(order)

            _rb.assert_not_final(report)

            _rb.assert_role_allowed(
                doctor_user,
                'DRAFT'
            )

            lease_token=str(
                _rb.request.headers.get('X-RadBridge-Report-Lease') or
                (_rb.request.get_json(silent=True) or {}).get('lease_token') or
                _rb.request.form.get('lease_token') or
                ''
            ).strip()

            _rb.assert_lease_owner(
                db=_rb.db,
                order=order,
                report=report,
                user=doctor_user,
                lease_token=lease_token,
            )

        except _rb.ReportEditControlError as exc:

            code=getattr(
                exc,
                'code',
                type(exc).__name__
            )

            try:
                _rb.audit(
                    'REPORT_EDIT_DENIED',
                    'order',
                    order.id,
                    f'action=DRAFT; editor=ONLYOFFICE; code={code}; user={doctor_user.id}'
                )

                _rb.db.session.commit()

            except Exception:
                _rb.db.session.rollback()

            return _rb.jsonify({
                'ok':False,
                'error':code,
            }), 409 if code in (
                'FINAL_REPORT_LOCKED',
                'REPORT_EDIT_LOCKED',
            ) else 403

        data = _rb.request.get_json(silent=True) or {}

        if 'base_version_no' not in data:
            return _rb.jsonify({
                'ok': False,
                'error': 'BASE_VERSION_REQUIRED'
            }), 400

        try:
            version = _rb._rb_commit_onlyoffice_version(
                order,
                doctor_user,
                'DRAFT',
                int(data['base_version_no'])
            )

            return _rb.jsonify({
                'ok': True,
                'status': 'DRAFT',
                'version_no': version.version_no,
                'editor_type': 'ONLYOFFICE'
            })

        except Exception as exc:
            _rb.db.session.rollback()

            code = getattr(
                exc,
                'code',
                None
            )

            if not code:
                message_code = str(exc).strip()

                if message_code == 'FINAL_REPORT_LOCKED':
                    code = message_code
                else:
                    code = type(exc).__name__

            status = 409 if code in (
                'REPORT_VERSION_CONFLICT',
                'REPORT_VERSION_DUPLICATE',
                'FINAL_REPORT_LOCKED'
                'DRAFT_VERSION_LIMIT_REACHED',
            ) else 400

            return _rb.jsonify({
                'ok': False,
                'error': code,
                'message': str(exc)
            }), status
    return api_ohif_onlyoffice_commit_draft


def install_0900(_rb):
    @_rb.app.post(
        '/api/ohif/report/<int:order_id>/onlyoffice/verify'
    )
    @_rb.require_ohif_token
    def api_ohif_onlyoffice_verify(order_id):
        order = _rb.Order.query.get_or_404(order_id)

        context_block = _rb.require_valid_ohif_case_context(order)
        if context_block:
            return context_block

        doctor_user, identity_block = \
            _rb.require_ohif_doctor_user(order.id)

        if identity_block:
            return identity_block

        try:
            report=_rb.get_report(order)

            _rb.assert_not_final(report)

            _rb.assert_role_allowed(
                doctor_user,
                'VERIFY'
            )
            _rb.assert_no_foreign_active_lease(
                db=_rb.db,
                order_id=order.id,
                user=doctor_user,
            )

        except _rb.ReportEditControlError as exc:

            code=getattr(
                exc,
                'code',
                type(exc).__name__
            )

            try:
                _rb.audit(
                    'REPORT_EDIT_DENIED',
                    'order',
                    order.id,
                    f'action=VERIFY; editor=ONLYOFFICE; code={code}; user={doctor_user.id}'
                )

                _rb.db.session.commit()

            except Exception:
                _rb.db.session.rollback()

            return _rb.jsonify({
                'ok':False,
                'error':code,
            }), 409 if code in (
                'FINAL_REPORT_LOCKED',
                'REPORT_EDIT_LOCKED',
            ) else 403

        demographic_ok, demographic_reason = \
            _rb.pacs_demographic_gate(order)

        if not demographic_ok:
            return _rb.jsonify({
                'ok': False,
                'error': 'PACS_DEMOGRAPHIC_REVIEW_REQUIRED',
                'reason': demographic_reason
            }), 409

        data = _rb.request.get_json(silent=True) or {}

        if 'base_version_no' not in data:
            return _rb.jsonify({
                'ok': False,
                'error': 'BASE_VERSION_REQUIRED'
            }), 400

        try:
            version = _rb._rb_commit_onlyoffice_version(
                order,
                doctor_user,
                'VERIFIED',
                int(data['base_version_no'])
            )

            return _rb.jsonify({
                'ok': True,
                'status': 'VERIFIED',
                'version_no': version.version_no,
                'authoritative': True,
                'editor_type': 'ONLYOFFICE'
            })

        except Exception as exc:
            _rb.db.session.rollback()

            code = getattr(
                exc,
                'code',
                type(exc).__name__
            )

            status = 409 if code in (
                'REPORT_VERSION_CONFLICT',
                'REPORT_VERSION_DUPLICATE'
            ) else 400

            return _rb.jsonify({
                'ok': False,
                'error': code,
                'message': str(exc)
            }), status
    return api_ohif_onlyoffice_verify


def install_0901(_rb):
    @_rb.app.post('/api/ohif/report/<int:order_id>/onlyoffice/finalize')
    @_rb.require_ohif_token
    def api_ohif_onlyoffice_finalize(order_id):
        order = _rb.Order.query.get_or_404(order_id)

        context_block = _rb.require_valid_ohif_case_context(order)
        if context_block:
            return context_block

        doctor_user, identity_block = _rb.require_ohif_doctor_user(order.id)
        if identity_block:
            return identity_block

        try:
            report=_rb.get_report(order)

            _rb.assert_not_final(report)

            _rb.assert_role_allowed(
                doctor_user,
                'FINALIZE'
            )
            _rb.assert_no_foreign_active_lease(
                db=_rb.db,
                order_id=order.id,
                user=doctor_user,
            )

        except _rb.ReportEditControlError as exc:

            code=getattr(
                exc,
                'code',
                type(exc).__name__
            )

            try:
                _rb.audit(
                    'REPORT_EDIT_DENIED',
                    'order',
                    order.id,
                    f'action=FINALIZE; editor=ONLYOFFICE; code={code}; user={doctor_user.id}'
                )

                _rb.db.session.commit()

            except Exception:
                _rb.db.session.rollback()

            return _rb.jsonify({
                'ok':False,
                'error':code,
            }), 409 if code in (
                'FINAL_REPORT_LOCKED',
                'REPORT_EDIT_LOCKED',
            ) else 403

        gate_ok, gate_reason = _rb.pacs_demographic_gate(order)
        if not gate_ok:
            return _rb.jsonify({
                'ok': False,
                'error': gate_reason,
            }), 409

        report = _rb.get_report(order)

        from onlyoffice_report_bridge import onlyoffice_finalize_latest

        try:
            version = onlyoffice_finalize_latest(
                db=_rb.db,
                Report=_rb.Report,
                ReportVersion=_rb.ReportVersion,
                order=order,
                user=doctor_user,
            )

            _rb.db.session.commit()

            try:
                _rb.audit(
                    'REPORT_FINALIZED',
                    'report',
                    report.id,
                    f'ONLYOFFICE version={version.version_no}'
                )
                _rb.db.session.commit()
            except Exception:
                _rb.db.session.rollback()

            return _rb.jsonify({
                'ok': True,
                'version_no': int(version.version_no),
                'status': 'FINALIZED',
            })

        except Exception as exc:
            _rb.db.session.rollback()

            code = getattr(exc, 'code', '') or type(exc).__name__

            status = 409 if code in (
                'FINAL_REPORT_LOCKED',
                'FINAL_REPORT_REQUIRES_ADDENDUM',
                'FINALIZE_CONFLICT',
                'REPORT_VERSION_CONFLICT',
                'NO_REPORT_VERSION',
            ) else 400

            return _rb.jsonify({
                'ok': False,
                'error': code,
            }), status
    return api_ohif_onlyoffice_finalize


def install_0902(_rb):
    @_rb.app.post('/api/ohif/report/<int:order_id>/onlyoffice/callback')
    def api_ohif_onlyoffice_callback(order_id):
        order = _rb.Order.query.get_or_404(order_id)

        link_token = str(
            _rb.request.args.get('token') or ''
        )

        if not _rb._onlyoffice_check_link_token(
            link_token,
            order.id,
            'callback'
        ):
            return _rb.jsonify({'error': 1}), 403

        auth = str(
            _rb.request.headers.get('Authorization') or ''
        ).strip()

        jwt_token = (
            auth[7:].strip()
            if auth.lower().startswith('bearer ')
            else ''
        )

        if not _rb._onlyoffice_jwt_valid(jwt_token):
            _rb.audit(
                'ONLYOFFICE_CALLBACK_REJECTED',
                'order',
                order.id,
                'invalid JWT'
            )
            _rb.db.session.commit()
            return _rb.jsonify({'error': 1}), 403

        data = _rb.request.get_json(silent=True) or {}
        status = int(data.get('status') or 0)

        # 1 = editing, 4 = closed without changes
        if status in (1, 4):
            return _rb.jsonify({'error': 0})

        # 2 = ready for save
        # 6 = forcesave
        if status not in (2, 6):
            return _rb.jsonify({'error': 0})

        edited_url = str(
            data.get('url') or ''
        ).strip()

        if not edited_url:
            return _rb.jsonify({'error': 1})

        # RB_ONLYOFFICE_TRUSTED_INTERNAL_DOWNLOAD_URL_V1
        #
        # ONLYOFFICE may construct callback artifact URLs using the browser-facing
        # reverse-proxy origin (for example 127.0.0.1:18096 during SSH-tunnel UAT).
        # That origin is not reachable from the RIS container.
        #
        # Never perform a server-side request to the callback-supplied host.
        # Accept only ONLYOFFICE cache artifacts, preserve their path/query, and
        # fetch them from the trusted internal Document Server endpoint.
        from urllib.parse import urlsplit

        edited_parts = urlsplit(edited_url)
        edited_path = str(edited_parts.path or '')

        if (
            not edited_path.startswith('/cache/files/')
            or '..' in edited_path.split('/')
        ):
            _rb.audit(
                'ONLYOFFICE_CALLBACK_REJECTED',
                'order',
                order.id,
                'untrusted document download path'
            )
            _rb.db.session.commit()
            return _rb.jsonify({'error': 1}), 400

        internal_edited_url = (
            _rb.ONLYOFFICE_INTERNAL_URL
            + edited_path
            + (
                '?' + edited_parts.query
                if edited_parts.query
                else ''
            )
        )

        try:
            r = _rb.requests.get(
                internal_edited_url,
                timeout=60
            )
            r.raise_for_status()

            from werkzeug.datastructures import FileStorage
            import io as _io

            fs = FileStorage(
                stream=_io.BytesIO(r.content),
                filename='onlyoffice.docx',
                content_type=(
                    'application/vnd.openxmlformats-officedocument.'
                    'wordprocessingml.document'
                )
            )

            tmppath, validation, code = \
                _rb._ohif_validate_word_upload(
                    order,
                    fs,
                    final=False
                )

            if not tmppath:
                _rb.audit(
                    'ONLYOFFICE_SAVE_BLOCKED',
                    'order',
                    order.id,
                    str(validation)
                )
                _rb.db.session.commit()
                return _rb.jsonify({'error': 1}), 409

            target = _rb._onlyoffice_working_path(order)
            _rb.shutil.copy2(tmppath, target)

            _rb.audit(
                'ONLYOFFICE_WORKING_COPY_SAVED',
                'order',
                order.id,
                (
                    f'status={status}; '
                    f'patient_safety=MATCH; '
                    f'bytes={_rb.os.path.getsize(target)}'
                )
            )

            _rb.db.session.commit()

            if status == 6:
                _rb._onlyoffice_write_forcesave_ack(
                    order.id,
                    data.get('userdata')
                )

            return _rb.jsonify({'error': 0})

        except Exception as exc:
            _rb.db.session.rollback()
            _rb.app.logger.exception(
                'ONLYOFFICE_CALLBACK_FAILED order=%s',
                order.id
            )

            return _rb.jsonify({
                'error': 1,
                'message': str(exc)
            }), 500
    return api_ohif_onlyoffice_callback
