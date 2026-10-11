"""Runtime-bound web.routes.imaging; dependencies are supplied at composition.

Legacy behavior is preserved; new policies belong in the independent domain layer.
"""

def install_0166(_rb):
    @_rb.app.route('/orders/<int:order_id>/resend-mwl',methods=['POST'])
    @_rb.require_perm('devices.manage')
    def resend_mwl(order_id):
        order=_rb.Order.query.filter_by(id=order_id).with_for_update().first_or_404()

        # RB_WORK_ORDER_GATE_V5_CANONICAL
        # Legacy regression markers: current_status == 'REGISTERED';
        # current_status == 'MWL_PENDING'. Both are blocked by resend_mwl_gate().
        # Resend is recovery only. It cannot activate a REGISTERED/PENDING case
        # or mutate a case that has already moved into acquisition/reporting.
        device=_rb.route_device(order.branch_id,order.modality) if order.branch_id else None
        decision=_rb.resend_mwl_gate(
            order_status=order.status,
            device_available=bool(device),
        )
        if not decision.allowed:
            _rb.flash(
                'MWL resend blocked: ' + _rb.blockers_text(decision.blockers),
                'warning',
            )
            return _rb.redirect(_rb.url_for('order_detail',order_id=order.id))

        if device:
            order.device_id=device.id
            order.station_ae=device.ae_title
        try:
            _rb.send_mwl(order); order.status='SCHEDULED'; _rb.flash('MWL sent successfully.','success')
        except Exception as e:
            order.status='MWL_ERROR'; _rb.flash(str(e),'danger')
        _rb.audit('MWL_RESEND','order',order.id,order.station_ae or ''); _rb.db.session.commit()
        return _rb.redirect(_rb.url_for('order_detail',order_id=order.id))
    return resend_mwl


def install_0178(_rb):
    @_rb.app.get('/orders/<int:order_id>/study-thumbnail')
    @_rb.require_perm('orders.view')
    def order_study_thumbnail(order_id):
        """Return a small PACS preview without exposing Orthanc credentials."""
        order = _rb.Order.query.get_or_404(order_id)

        if not order.pacs_study_id or int(order.pacs_image_count or 0) <= 0:
            _rb.abort(404)

        from pacs_thumbnail import study_preview, ThumbnailUnavailable

        def get_preview(instance_id):
            return _rb.requests.get(
                f'{_rb.PACS_ORTHANC_URL}/instances/{instance_id}/preview',
                auth=_rb._orthanc_auth(),
                headers={'Accept': 'image/png'},
                timeout=5,
            )

        try:
            data, content_type = study_preview(
                _rb._orthanc_study_detail(order.pacs_study_id),
                _rb._orthanc_series_detail,
                get_preview,
            )
        except ThumbnailUnavailable:
            _rb.abort(502)
        except Exception:
            _rb.app.logger.exception('Study thumbnail lookup failed for order %s', order.id)
            _rb.abort(502)

        return data, 200, {
            'Content-Type': content_type,
            'Cache-Control': 'private, max-age=60',
            'X-Content-Type-Options': 'nosniff',
        }
    return order_study_thumbnail


def install_0194(_rb):
    @_rb.app.route('/pacs')
    @_rb.app.route('/pacs/')
    @_rb.require_perm('orders.view')
    def pacs_home():
        """Compatibility entry point for legacy PACS links."""
        study = _rb.request.args.get('study', '').strip()

        if study:
            return _rb.redirect(_rb.url_for('pacs_tracking', study=study))

        return _rb.redirect(_rb.url_for('pacs_tracking'))
    return pacs_home


def install_0195(_rb):
    @_rb.app.route('/pacs/tracking')
    @_rb.require_perm('orders.view')
    def pacs_tracking():
        # Read-only page load. PACS synchronization is an explicit POST to
        # /pacs/tracking/refresh (or a background worker), never a GET side effect.
        rows=_rb.Order.query.order_by(_rb.Order.scheduled.desc()).limit(300).all()
        return _rb.render_template('pacs_tracking.html',rows=rows)
    return pacs_tracking


def install_0196(_rb):
    @_rb.app.post('/pacs/tracking/refresh')
    @_rb.require_perm('orders.view')
    def pacs_tracking_refresh():
        rows=_rb.Order.query.order_by(_rb.Order.scheduled.desc()).limit(300).all()
        eligible_ids=[]
        for order in rows:
            result=_rb.pacs_lookup_order(order)
            if (
                (order.exam_status or '').upper()=='EXAM_COMPLETED'
                and (result.get('status') or '').upper()=='IMAGES_COMPLETE'
            ):
                _rb.evaluate_case_readiness(order)
                eligible_ids.append(order.id)
        _rb.db.session.commit()

        assignment_results={}
        for order_id in eligible_ids:
            try:
                order=_rb.Order.query.get(order_id)
                _offer,status=_rb.coordinate_post_exam_assignment(
                    order,
                    created_by=_rb.current_user().id if _rb.current_user() else None,
                    trigger='PACS_REFRESH'
                )
                assignment_results[str(order_id)]=status
            except Exception as exc:
                _rb.db.session.rollback()
                assignment_results[str(order_id)]='ERROR'
                _rb.app.logger.warning(
                    'PACS refresh assignment failed order=%s: %s',
                    order_id,exc
                )

        return _rb.jsonify({
            'ok':True,
            'updated':len(rows),
            'assignment_results':assignment_results
        })
    return pacs_tracking_refresh


def install_0481(_rb):
    @_rb.app.get('/pacs/reconciliation/<study_id>/preview')
    @_rb.require_perm('pacs.reconcile')
    def pacs_reconciliation_preview(study_id):
        import sys
        from dicom_reconciliation import preview, CorrectionError
        inbox=_rb.PacsStudyInbox.query.filter_by(orthanc_study_id=study_id).first_or_404()
        order=_rb.Order.query.get_or_404(_rb.request.args.get('order_id',type=int))
        try:
            before,after,token=preview(sys.modules[_rb.__name__],inbox,order)
        except CorrectionError as exc:
            return _rb.jsonify(error=str(exc)),409
        except _rb.requests.RequestException:
            return _rb.jsonify(error='PACS unavailable; preview cannot be verified.'),503
        response=_rb.jsonify(before=before['tags'],after=after,images=before['count'],
            study_uid=before['study_uid'],token=token,order_id=order.id,
            branch=order.branch.name if order.branch else '',procedure=order.procedure)
        response.headers['Cache-Control']='no-store'
        return response
    return pacs_reconciliation_preview


def install_0482(_rb):
    @_rb.app.post('/pacs/reconciliation/<study_id>/correct-dicom')
    @_rb.require_perm('pacs.reconcile')
    def pacs_reconciliation_correct_dicom(study_id):
        import sys
        from dicom_reconciliation import execute,CorrectionError
        # DICOM mutation is restricted to administrators, beyond ordinary match permission.
        if not _rb.has_perm('correction.review'):_rb.abort(403)
        if _rb.request.form.get('identity_confirmed')!='1':_rb.abort(400)
        reason=(_rb.request.form.get('reason') or '').strip()
        if not 5<=len(reason)<=500 or not _rb.request.form.get('preview_token'):_rb.abort(400)
        inbox=_rb.PacsStudyInbox.query.filter_by(orthanc_study_id=study_id).first_or_404()
        order=_rb.Order.query.get_or_404(_rb.request.form.get('order_id',type=int))
        try:
            job=execute(sys.modules[_rb.__name__],inbox,order,_rb.request.form['preview_token'],reason)
            _rb.flash('DICOM corrected and verified. Original retained. Audit correction #'+str(job.id),'success')
        except (CorrectionError,_rb.requests.RequestException) as exc:
            _rb.db.session.rollback()
            _rb.flash(str(exc) if isinstance(exc,CorrectionError) else 'PACS unavailable; correction blocked.','danger')
        return _rb.redirect(_rb.url_for('pacs_reconciliation'))
    return pacs_reconciliation_correct_dicom


def install_0483(_rb):
    @_rb.app.get('/pacs/reconciliation/audit')
    @_rb.require_perm('audit.view')
    def pacs_reconciliation_audit():
        q=_rb.DicomCorrection.query.join(_rb.Order,_rb.DicomCorrection.order_id==_rb.Order.id)
        if not _rb.has_perm('*'):
            u=_rb.current_user()
            if not u.branch_id:_rb.abort(403)
            q=q.filter(_rb.Order.branch_id==u.branch_id)
        rows=q.order_by(_rb.DicomCorrection.id.desc()).limit(200).all()
        return _rb.render_template('dicom_correction_audit.html',rows=rows,json=_rb.json)
    return pacs_reconciliation_audit


def install_0484(_rb):
    @_rb.app.get('/pacs/reconciliation/example')
    @_rb.require_perm('pacs.reconcile')
    def pacs_reconciliation_example():
        from types import SimpleNamespace as Obj
        fields=['PatientID','PatientName','PatientBirthDate','PatientSex','AccessionNumber']
        before=dict(zip(fields,['CODEX-UAT-WRONG','CODEX UAT Wrong','19800101','F','UAT-WRONG']))
        after=dict(zip(fields,['CODEX-UAT-CORRECT','CODEX UAT Correct','19900101','M','UAT-CORRECT']))
        patient=Obj(patient_id='CODEX-UAT-CORRECT',name='CODEX UAT Correct')
        order=Obj(id='EXAMPLE',procedure='Synthetic X-ray',branch=Obj(name='Example branch'))
        inbox=Obj(id='EXAMPLE',match_method='EXAMPLE ONLY',orthanc_study_id='example')
        row={'inbox':inbox,'candidate':None,'ris_patient':patient,
             'preview':{'before':{'tags':before,'count':2,'study_uid':'Synthetic example'},'after':after,'order':order}}
        return _rb.render_template('pacs_reconciliation.html',exceptions=[row],eligible_exam_pairs=[],
            active_exam_links=[],can_exam_link=False,can_reconcile=False,target_options=[],search_query='',demo_mode=True)
    return pacs_reconciliation_example


def install_0485(_rb):
    @_rb.app.route('/pacs/reconciliation')
    @_rb.require_perm('orders.view')
    def pacs_reconciliation():
        exceptions=_rb.PacsStudyInbox.query.filter_by(
            state='REVIEW_REQUIRED'
        ).order_by(_rb.PacsStudyInbox.first_seen_at.desc()).all()

        rows=[]

        for inbox in exceptions:
            candidate=None

            # Candidate 1: exact RIS accession
            if inbox.accession:
                candidate=_rb.Order.query.filter_by(
                    accession=inbox.accession
                ).first()

            # Candidate 2: unique RIS Patient ID - suggestion only
            if not candidate and inbox.pacs_patient_id:
                patient=_rb.Patient.query.filter_by(
                    patient_id=inbox.pacs_patient_id
                ).first()

                if patient:
                    candidates=_rb.Order.query.filter_by(
                        patient_id=patient.id
                    ).order_by(_rb.Order.id.desc()).limit(10).all()

                    if len(candidates)==1:
                        candidate=candidates[0]

            rows.append({
                'inbox':inbox,
                'candidate':candidate,
                'ris_patient':candidate.patient if candidate else None,
            })

        # Exam Linking deliberately remains separate from the authoritative
        # primary PACS match. Only same-patient, editable secondary orders are
        # offered; the service repeats every check under row locks.
        primary_orders=(
            _rb.Order.query
            .filter(_rb.Order.pacs_study_id.isnot(None))
            .filter(_rb.Order.pacs_study_id!='')
            .order_by(_rb.Order.id.desc())
            .limit(200)
            .all()
        )

        eligible_exam_pairs=[]

        for primary in primary_orders:
            secondary_orders=(
                _rb.Order.query
                .filter(
                    _rb.Order.patient_id==primary.patient_id,
                    _rb.Order.id!=primary.id,
                    ~_rb.Order.status.in_(['FINAL','CANCELLED']),
                )
                .order_by(_rb.Order.id.desc())
                .limit(50)
                .all()
            )

            for secondary in secondary_orders:
                latest_report=(
                    _rb.Report.query
                    .filter_by(order_id=secondary.id)
                    .order_by(_rb.Report.id.desc())
                    .first()
                )

                if (
                    latest_report
                    and str(latest_report.status or '').upper()
                        in ('VERIFIED','FINAL')
                ):
                    continue

                eligible_exam_pairs.append({
                    'primary':primary,
                    'secondary':secondary,
                    'patient':primary.patient,
                })

        active_exam_links=[]

        for link in (
            _rb.PacsExamLink.query
            .filter_by(active=True)
            .order_by(_rb.PacsExamLink.created_at.desc())
            .limit(200)
            .all()
        ):
            secondary=_rb.db.session.get(_rb.Order,link.order_id)
            primary=(
                _rb.Order.query
                .filter_by(pacs_study_id=link.orthanc_study_id)
                .order_by(_rb.Order.id)
                .first()
            )

            active_exam_links.append({
                'link':link,
                'primary':primary,
                'secondary':secondary,
            })

        import sys
        from dicom_reconciliation import preview,CorrectionError
        q=(_rb.request.args.get('q') or '').strip()[:100]
        target_options=_rb.correction_search_orders(q,limit=20) if q else []
        if not _rb.has_perm('*'):
            u=_rb.current_user()
            target_options=[o for o in target_options if u.branch_id and o.branch_id==u.branch_id]
            rows=[row for row in rows if row['candidate'] and u.branch_id and row['candidate'].branch_id==u.branch_id]
        for row in rows:
            row['preview']=None
            if row['inbox'].orthanc_study_id==_rb.request.args.get('study_id') and _rb.request.args.get('order_id') and _rb.has_perm('pacs.reconcile'):
                selected=_rb.Order.query.get_or_404(_rb.request.args.get('order_id',type=int))
                try:
                    before,after,token=preview(sys.modules[_rb.__name__],row['inbox'],selected)
                    row['preview']={'before':before,'after':after,'token':token,'order':selected}
                except CorrectionError as exc:_rb.flash(str(exc),'danger')
                except _rb.requests.RequestException:_rb.flash('PACS unavailable; preview blocked.','danger')

        return _rb.render_template(
            'pacs_reconciliation.html',
            exceptions=rows,target_options=target_options,search_query=q,correction_paused=bool(_rb.DicomCorrection.query.filter(_rb.db.or_(_rb.DicomCorrection.status.in_(['PENDING','CREATED']),_rb.db.and_(_rb.DicomCorrection.status=='NEEDS_REVIEW',_rb.DicomCorrection.new_study_id==''))).first()),
            eligible_exam_pairs=eligible_exam_pairs,
            active_exam_links=active_exam_links,
            can_exam_link=_rb.has_perm('pacs.exam_link'),
            can_reconcile=_rb.has_perm('pacs.reconcile'),
        )
    return pacs_reconciliation


def install_0486(_rb):
    @_rb.app.post('/pacs/exam-link')
    @_rb.require_perm('pacs.exam_link')
    def pacs_exam_link_create():
        from pacs_resolution_service import atomic_exam_link

        primary_order_id=_rb.request.form.get(
            'primary_order_id',type=int
        )
        secondary_order_id=_rb.request.form.get(
            'secondary_order_id',type=int
        )
        reason=(_rb.request.form.get('reason') or '').strip()

        if not primary_order_id or not secondary_order_id:
            _rb.flash('Primary and secondary RIS Orders are required.','danger')
            return _rb.redirect(_rb.url_for('pacs_reconciliation'))

        primary=_rb.Order.query.get_or_404(primary_order_id)

        try:
            result=atomic_exam_link(
                db=_rb.db,
                Order=_rb.Order,
                Report=_rb.Report,
                PacsExamLink=_rb.PacsExamLink,
                primary_order_id=primary_order_id,
                secondary_order_id=secondary_order_id,
                orthanc_study_id=primary.pacs_study_id,
                actor_user_id=_rb.current_user().id,
                reason=reason,
            )

            link=result['link']

            _rb.audit(
                'PACS_EXAM_LINK_CREATED',
                'order',
                secondary_order_id,
                (
                    'primary_order=%s; study=%s; action=%s; reason=%s'
                    % (
                        primary_order_id,
                        link.orthanc_study_id,
                        result['action'],
                        reason,
                    )
                )
            )

            _rb.db.session.commit()

            _rb.flash(
                'Exam Link saved successfully.'
                if result['action']=='CREATED'
                else 'Exam Link already exists.',
                'success'
            )

        except Exception as exc:
            _rb.db.session.rollback()
            code=getattr(exc,'code','') or type(exc).__name__
            _rb.flash('Exam Link blocked: %s' % code,'danger')

        return _rb.redirect(_rb.url_for('pacs_reconciliation'))
    return pacs_exam_link_create


def install_0487(_rb):
    @_rb.app.post('/pacs/exam-link/<int:link_id>/remove')
    @_rb.require_perm('pacs.exam_link')
    def pacs_exam_link_remove(link_id):
        from pacs_resolution_service import atomic_remove_exam_link

        reason=(_rb.request.form.get('reason') or '').strip()

        try:
            result=atomic_remove_exam_link(
                db=_rb.db,
                Order=_rb.Order,
                Report=_rb.Report,
                PacsExamLink=_rb.PacsExamLink,
                link_id=link_id,
                actor_user_id=_rb.current_user().id,
                reason=reason,
            )

            link=result['link']

            _rb.audit(
                'PACS_EXAM_LINK_REMOVED',
                'order',
                link.order_id,
                (
                    'study=%s; action=%s; reason=%s'
                    % (
                        link.orthanc_study_id,
                        result['action'],
                        reason,
                    )
                )
            )

            _rb.db.session.commit()
            _rb.flash('Exam Link removed successfully.','success')

        except Exception as exc:
            _rb.db.session.rollback()
            code=getattr(exc,'code','') or type(exc).__name__
            _rb.flash('Exam Link removal blocked: %s' % code,'danger')

        return _rb.redirect(_rb.url_for('pacs_reconciliation'))
    return pacs_exam_link_remove


def install_0488(_rb):
    @_rb.app.post('/pacs/reconciliation/<study_id>/match')
    @_rb.require_perm('pacs.reconcile')
    def pacs_reconciliation_match(study_id):
        from pacs_resolution_service import atomic_primary_link
        inbox=_rb.PacsStudyInbox.query.filter_by(orthanc_study_id=study_id).first_or_404()
        if inbox.state!='REVIEW_REQUIRED':
            _rb.flash('Study is not waiting for demographic review.','warning')
            return _rb.redirect(_rb.url_for('pacs_reconciliation'))
        order_id=_rb.request.form.get('order_id',type=int)
        reason=(_rb.request.form.get('reason') or '').strip()
        if not order_id or not 5<=len(reason)<=500:
            _rb.flash('RIS Order ID and documented reason are required.','danger')
            return _rb.redirect(_rb.url_for('pacs_reconciliation'))
        order=_rb.Order.query.get_or_404(order_id)
        import sys
        from dicom_reconciliation import preview,validate_token,CorrectionError
        if _rb.request.form.get('identity_confirmed')!='1':_rb.abort(400)
        try:
            before,after,_=preview(sys.modules[_rb.__name__],inbox,order)
            validate_token(sys.modules[_rb.__name__],_rb.request.form.get('preview_token',''),inbox,order,before,after)
        except CorrectionError as exc:
            _rb.flash(str(exc),'danger');return _rb.redirect(_rb.url_for('pacs_reconciliation'))
        except _rb.requests.RequestException:
            _rb.flash('PACS unavailable; match blocked.','danger');return _rb.redirect(_rb.url_for('pacs_reconciliation'))
        st=next((x for x in _rb._orthanc_recent_studies(300) if x.get('ID')==study_id),None)
        if not st: _rb.abort(404)
        tags=_rb._study_tags_extended(st)
        try:
            atomic_primary_link(
                db=_rb.db,Order=_rb.Order,Report=_rb.Report,PacsStudyInbox=_rb.PacsStudyInbox,
                PacsStudyMatch=_rb.PacsStudyMatch,PacsResolutionEvent=_rb.PacsResolutionEvent,
                order_id=order.id,orthanc_study_id=study_id,
                study_instance_uid=tags.get('study_instance_uid') or '',
                image_count=tags.get('instances') or inbox.image_count or 0,
                match_method='MANUAL_CONFIRMED',confidence='CONFIRMED',
                actor_user_id=_rb.current_user().id,reason=reason,
                pacs_patient_id=tags.get('patient_id',''),
                pacs_patient_name=tags.get('patient_name',''),
                pacs_accession=tags.get('accession',''),inbox_state='MANUALLY_MATCHED')
            _rb.evaluate_case_readiness(order)
            _rb.audit('PACS_DEMOGRAPHIC_MANUAL_RECONCILIATION','order',order.id,
                  _rb.json.dumps({'study':study_id,'reason':reason,'before':before['tags'],'target':after,'dicom_changed':False},ensure_ascii=False))
            _rb.db.session.commit()
        except Exception as exc:
            _rb.db.session.rollback()
            _rb.flash(getattr(exc,'code',str(exc)),'danger')
            return _rb.redirect(_rb.url_for('pacs_reconciliation'))
        try:
            _rb.enqueue_auto_routes_for_inbox(inbox);_rb.db.session.commit()
        except Exception as exc:
            _rb.db.session.rollback();_rb.app.logger.warning('Auto routing failed order=%s: %s',order.id,exc)
        _rb.flash('PACS exception reviewed and matched successfully.','success')
        return _rb.redirect(_rb.url_for('pacs_reconciliation'))
    return pacs_reconciliation_match


def install_0489(_rb):
    @_rb.app.post('/pacs/reconciliation/<study_id>/quarantine')
    @_rb.require_perm('pacs.reconcile')
    def pacs_reconciliation_quarantine(study_id):
        inbox=_rb.PacsStudyInbox.query.filter_by(
            orthanc_study_id=study_id
        ).first_or_404()

        reason=(_rb.request.form.get('reason') or '').strip()

        if len(reason)<5:
            _rb.flash('Quarantine reason is required.','danger')
            return _rb.redirect(_rb.url_for('pacs_reconciliation'))

        old_state=inbox.state

        inbox.order_id=None
        inbox.state='QUARANTINED'
        inbox.match_method='MANUAL_QUARANTINE'
        inbox.error_text=(
            'Quarantined by user_id=%s; reason=%s'
            % (_rb.current_user().id,reason)
        )[:2000]

        _rb.audit(
            'PACS_DEMOGRAPHIC_QUARANTINE',
            'pacs_study_inbox',
            inbox.id,
            'study=%s old_state=%s reason=%s'
            % (study_id,old_state,reason)
        )

        _rb.db.session.commit()

        _rb.flash('PACS study moved to quarantine.','warning')
        return _rb.redirect(_rb.url_for('pacs_reconciliation'))
    return pacs_reconciliation_quarantine


def install_0490(_rb):
    @_rb.app.post('/pacs/reconciliation/auto-safe')
    @_rb.require_perm('pacs.reconcile')

    def pacs_reconciliation_auto_safe():
        from pacs_resolution_service import atomic_primary_link
        matched=0
        try:
            for st in _rb._orthanc_recent_studies(200):
                tags=_rb._study_tags_extended(st);sid=tags.get('study_id')
                if _rb.DicomCorrection.query.filter(
                    _rb.db.or_(_rb.DicomCorrection.source_study_id==sid,
                           _rb.db.and_(_rb.DicomCorrection.new_study_id==sid,_rb.DicomCorrection.status!='COMPLETED'))
                ).first() or _rb.DicomCorrection.query.filter(_rb.db.or_(_rb.DicomCorrection.status.in_(['PENDING','CREATED']),_rb.db.and_(_rb.DicomCorrection.status=='NEEDS_REVIEW',_rb.DicomCorrection.new_study_id==''))).first():
                    continue
                existing=_rb.PacsStudyMatch.query.filter_by(orthanc_study_id=sid).first()
                if existing: continue
                order,method,decision=_rb.strict_pacs_demographic_match(tags)
                if not (order and decision=='AUTO_SAFE'): continue
                inbox=_rb.PacsStudyInbox.query.filter_by(orthanc_study_id=sid).first()
                if not inbox:
                    inbox=_rb.PacsStudyInbox(
                        orthanc_study_id=sid,
                        study_instance_uid=tags.get('study_instance_uid') or None,
                        pacs_patient_id=tags.get('patient_id',''),
                        pacs_patient_name=tags.get('patient_name',''),
                        accession=tags.get('accession',''),modality=tags.get('modality',''),
                        study_description=tags.get('study_description',''),
                        source_ae=tags.get('source_ae',''),
                        image_count=int(tags.get('instances') or 0),state='NEW')
                    _rb.db.session.add(inbox);_rb.db.session.flush()
                atomic_primary_link(
                    db=_rb.db,Order=_rb.Order,Report=_rb.Report,PacsStudyInbox=_rb.PacsStudyInbox,
                    PacsStudyMatch=_rb.PacsStudyMatch,PacsResolutionEvent=_rb.PacsResolutionEvent,
                    order_id=order.id,orthanc_study_id=sid,
                    study_instance_uid=tags.get('study_instance_uid') or '',
                    image_count=tags.get('instances') or inbox.image_count or 0,
                    match_method='DEMOGRAPHICS_EXACT',confidence='AUTO_SAFE',
                    actor_user_id=_rb.current_user().id,
                    reason='Strict match: Accession + Patient ID + DOB',
                    pacs_patient_id=tags.get('patient_id',''),
                    pacs_patient_name=tags.get('patient_name',''),
                    pacs_accession=tags.get('accession',''))
                _rb.evaluate_case_readiness(order)
                _rb.audit('PACS_DEMOGRAPHIC_AUTO_MATCH','order',order.id,
                      'DEMOGRAPHICS_EXACT study=%s' % sid)
                matched+=1
            _rb.db.session.commit()
        except Exception:
            _rb.db.session.rollback();raise
        _rb.flash(f'Auto-safe matched {matched} study/studies.','success')
        return _rb.redirect(_rb.url_for('pacs_reconciliation'))
    return pacs_reconciliation_auto_safe


def install_0544(_rb):
    @_rb.app.route('/orders/<int:order_id>/take',methods=['POST'])
    @_rb.require_perm('pacs.open_pool.take')
    def take_case(order_id):
        order=_rb.Order.query.get_or_404(order_id)
        user=_rb.current_user()

        allowed,reason=_rb.doctor_can_take_open_case(user,order)
        if not allowed:
            _rb.flash('Case cannot be taken: '+reason.replace('_',' ')+'.','danger')
            return _rb.redirect(_rb.request.referrer or _rb.url_for('unassigned_cases'))
        try:
            _rb.manual_assign_order(
                order,
                user.id,
                assigned_by=user.id,
                notes='Doctor took case from governed open pool',
                assignment_type='OPEN_POOL',
                require_unassigned=True,
            )
            _rb.db.session.commit()
        except Exception as exc:
            _rb.db.session.rollback()
            code=getattr(exc,'code',type(exc).__name__)
            _rb.flash('Case cannot be taken: '+str(code).replace('_',' ')+'.','danger')
            return _rb.redirect(_rb.request.referrer or _rb.url_for('unassigned_cases'))
        _rb.flash('Case assigned to you.','success')
        return _rb.redirect(_rb.url_for('doctor_workspace'))
    return take_case


def install_0554(_rb):
    @_rb.app.get('/admin/dicom-connections')
    @_rb.require_perm('devices.manage')
    def dicom_connections_page():
        from dicom_connections import branch_allowed,KINDS
        branches=[b for b in _rb.Branch.query.order_by(_rb.Branch.code).all() if branch_allowed(b.id)]
        if not branches and not _rb.has_perm('*'):_rb.abort(403)
        branch_id=_rb.request.args.get('branch_id',type=int)
        if branch_id and not branch_allowed(branch_id):_rb.abort(403)
        if branch_id:branches=[b for b in branches if b.id==branch_id]
        ids=[b.id for b in branches]
        endpoints=_rb.DicomEndpoint.query.filter(_rb.DicomEndpoint.branch_id.in_(ids)).order_by(_rb.DicomEndpoint.branch_id,_rb.DicomEndpoint.kind).all()
        devices=_rb.Device.query.filter(_rb.Device.branch_id.in_(ids)).order_by(_rb.Device.branch_id,_rb.Device.name).all()
        central=None
        try:
            response=_rb.requests.get(_rb.ORTHANC+'/system',auth=_rb.AUTH,timeout=2)
            if response.ok:central={key:response.json().get(key) for key in ('DicomAet','DicomPort')}
        except _rb.requests.RequestException:pass
        return _rb.render_template('dicom_connections.html',central=central,branches=branches,endpoints=endpoints,devices=devices,kinds=KINDS)
    return dicom_connections_page


def install_0555(_rb):
    @_rb.app.route('/admin/dicom-connections/branches/<int:branch_id>',methods=['GET','POST'])
    @_rb.require_perm('devices.manage')
    def dicom_connection_edit(branch_id):
        from dicom_connections import branch_allowed,KINDS,ae_title,host,port
        if not branch_allowed(branch_id):_rb.abort(403)
        branch=_rb.Branch.query.get_or_404(branch_id)
        if _rb.request.method=='POST':
            kind=_rb.request.form.get('kind')
            if kind not in KINDS:_rb.abort(400)
            try:
                values={'ae_title':ae_title(_rb.request.form.get('ae_title')),'calling_ae':ae_title(_rb.request.form.get('calling_ae')),'host':host(_rb.request.form.get('host')),'port':port(_rb.request.form.get('port')),'active':_rb.request.form.get('active')=='1'}
                if values['active'] and (not values['host'] or not branch.active):raise ValueError('Activate the branch and configure its host before enabling this connection.')
            except ValueError as exc:
                _rb.flash(str(exc),'danger');return _rb.redirect(_rb.url_for('dicom_connection_edit',branch_id=branch_id))
            row=_rb.DicomEndpoint.query.filter_by(branch_id=branch_id,kind=kind).with_for_update().first()
            if not row:row=_rb.DicomEndpoint(branch_id=branch_id,kind=kind);_rb.db.session.add(row)
            changed=any(getattr(row,key)!=value for key,value in values.items())
            for key,value in values.items():setattr(row,key,value)
            if changed:row.echo_result='NOT_TESTED';row.echo_message='';row.echo_checked_at=None;row.echo_elapsed_ms=None
            _rb.audit('DICOM_ENDPOINT_CONFIGURED','branch',branch_id,'kind='+kind+'; connection metadata only; listener and routing unchanged')
            _rb.db.session.commit();_rb.flash('Connection saved. / تم حفظ بيانات الاتصال.','success')
            return _rb.redirect(_rb.url_for('dicom_connection_edit',branch_id=branch_id))
        return _rb.render_template('dicom_connection_edit.html',branch=branch,kinds=KINDS,endpoints={e.kind:e for e in _rb.DicomEndpoint.query.filter_by(branch_id=branch_id).all()})
    return dicom_connection_edit


def install_0556(_rb):
    @_rb.app.post('/admin/dicom-connections/<int:endpoint_id>/echo')
    @_rb.require_perm('devices.manage')
    def dicom_connection_echo(endpoint_id):
        from dicom_connections import branch_allowed,echo
        row=_rb.DicomEndpoint.query.filter_by(id=endpoint_id).with_for_update().first_or_404()
        if not branch_allowed(row.branch_id):_rb.abort(403)
        if not row.active or not row.branch.active or not row.host:_rb.abort(409,'Configure and activate the connection first.')
        result=echo(row.host,row.port,row.ae_title,row.calling_ae)
        row.echo_result=result['result'];row.echo_message=result['message'];row.echo_elapsed_ms=result['elapsed_ms'];row.echo_checked_at=_rb.datetime.utcnow()
        _rb.audit('DICOM_CECHO','dicom_endpoint',row.id,'result='+row.echo_result+'; no image transfer')
        _rb.db.session.commit();_rb.flash(row.echo_message,'success' if row.echo_result=='SUCCESS' else 'warning')
        return _rb.redirect(_rb.url_for('dicom_connections_page',branch_id=row.branch_id))
    return dicom_connection_echo


def install_0674(_rb):
    @_rb.app.route('/admin/imaging-ai',methods=['GET','POST'])
    @_rb.require_perm('users.view')
    def admin_imaging_ai():
        row=_rb.ImagingAIProvider.query.order_by(_rb.ImagingAIProvider.id).first()
        if _rb.request.method=='POST':
            if not row:
                row=_rb.ImagingAIProvider(provider_key='GENERIC_IMAGING_REST')
                _rb.db.session.add(row)
            row.enabled=_rb.request.form.get('enabled')=='1'
            row.provider_key=(_rb.request.form.get('provider_key') or 'GENERIC_IMAGING_REST').strip().upper()
            row.base_url=(_rb.request.form.get('base_url') or '').strip()
            row.model_name=(_rb.request.form.get('model_name') or '').strip()
            row.modalities=(_rb.request.form.get('modalities') or '').strip().upper()
            row.timeout_seconds=_rb.request.form.get('timeout_seconds',type=int) or 180
            row.secret_env_name=(_rb.request.form.get('secret_env_name') or 'RIS_IMAGING_AI_TOKEN').strip()
            row.updated_by=_rb.current_user().id
            _rb.db.session.commit()
            return _rb.redirect(_rb.url_for('admin_imaging_ai'))
        return _rb.render_template('admin_imaging_ai.html',row=row)
    return admin_imaging_ai


def install_0814(_rb):
    @_rb.app.get('/pacs/unregistered')
    @_rb.require_perm('pacs.intake.view')
    def pacs_unregistered_cases():
        rows=_rb.PacsStudyInbox.query.order_by(_rb.PacsStudyInbox.last_seen_at.desc()).limit(500).all()
        return _rb.render_template('pacs_unregistered.html',rows=rows)
    return pacs_unregistered_cases


def install_0815(_rb):
    @_rb.app.post('/pacs/unregistered/run')
    @_rb.require_perm('pacs.intake.manage')
    def pacs_unregistered_run():
        result=_rb.pacs_auto_intake_once(300)
        _rb.flash(f"PACS intake: seen {result['seen']}, linked {result['linked']}, review required {result['review_required']}, errors {result['errors']}. No new RIS order is created by this scan.",'success')
        return _rb.redirect(_rb.url_for('pacs_unregistered_cases'))
    return pacs_unregistered_run


def install_0816(_rb):
    @_rb.app.route('/admin/pacs/destinations',methods=['GET','POST'])
    @_rb.require_perm('pacs.destinations.manage')
    def pacs_destinations():
        if _rb.request.method=='POST':
            row=_rb.DicomDestination(
              key=_rb.re.sub(r'[^a-z0-9_-]','-',(_rb.request.form.get('key') or '').strip().lower()),
              name=(_rb.request.form.get('name') or '').strip(),
              ae_title=(_rb.request.form.get('ae_title') or '').strip().upper(),
              host=(_rb.request.form.get('host') or '').strip(),
              port=_rb.request.form.get('port',type=int) or 104,
              destination_type=(_rb.request.form.get('destination_type') or 'PACS').upper(),
              branch_id=_rb.request.form.get('branch_id',type=int),
              allow_manual_send=_rb.request.form.get('allow_manual_send')=='1',active=True)
            if not row.key or not row.name or not row.ae_title or not row.host:_rb.abort(400)
            if _rb.DiscoveredDicomNode.query.filter_by(ae_title=row.ae_title,status='APPROVED').first():
                _rb.abort(409,description='An approved incoming node already uses this AE Title')
            _rb.db.session.add(row);_rb.db.session.flush()
            try:_rb.sync_destination_to_orthanc(row)
            except Exception as exc:_rb.flash('Saved, but Orthanc sync failed: '+str(exc),'warning')
            _rb.audit('DICOM_DESTINATION_CREATE','dicom_destination',row.id,row.name);_rb.db.session.commit()
            return _rb.redirect(_rb.url_for('pacs_destinations'))
        return _rb.render_template('pacs_destinations.html',
          rows=_rb.DicomDestination.query.order_by(_rb.DicomDestination.name).all(),
          branches=_rb.Branch.query.filter_by(active=True).order_by(_rb.Branch.name).all())
    return pacs_destinations


def install_0817(_rb):
    @_rb.app.route('/admin/pacs/routing',methods=['GET','POST'])
    @_rb.require_perm('pacs.archive.manage')
    def pacs_routing_rules():
        if _rb.request.method=='POST':
            row=_rb.PacsRoutingRule(name=(_rb.request.form.get('name') or '').strip(),
              destination_id=_rb.request.form.get('destination_id',type=int),
              branch_id=_rb.request.form.get('branch_id',type=int),
              modality=(_rb.request.form.get('modality') or '').strip().upper(),
              source_ae=(_rb.request.form.get('source_ae') or '').strip().upper(),active=True)
            _rb.db.session.add(row);_rb.db.session.commit()
            return _rb.redirect(_rb.url_for('pacs_routing_rules'))
        return _rb.render_template('pacs_routing_rules.html',
          rows=_rb.PacsRoutingRule.query.order_by(_rb.PacsRoutingRule.id.desc()).all(),
          destinations=_rb.DicomDestination.query.filter_by(active=True).order_by(_rb.DicomDestination.name).all(),
          branches=_rb.Branch.query.filter_by(active=True).order_by(_rb.Branch.name).all())
    return pacs_routing_rules


def install_0818(_rb):
    @_rb.app.get('/pacs/actions/<int:order_id>')
    @_rb.require_perm('pacs.transfer')
    def pacs_case_actions(order_id):
        order=_rb.Order.query.get_or_404(order_id)
        jobs=_rb.PacsTransferJob.query.filter_by(order_id=order.id).order_by(_rb.PacsTransferJob.id.desc()).limit(50).all()
        dq=_rb.DicomDestination.query.filter_by(active=True,allow_manual_send=True)
        if _rb.current_user().role and _rb.current_user().role.code in ('TECHNICIAN','SERVICE') and _rb.current_user().branch_id:
            dq=dq.filter(_rb.or_(_rb.DicomDestination.branch_id.is_(None),_rb.DicomDestination.branch_id==_rb.current_user().branch_id))
        return _rb.render_template('pacs_case_actions.html',order=order,
          destinations=dq.order_by(_rb.DicomDestination.destination_type,_rb.DicomDestination.name).all(),jobs=jobs)
    return pacs_case_actions


def install_0819(_rb):
    @_rb.app.post('/pacs/actions/<int:order_id>/send')
    @_rb.require_perm('pacs.transfer')
    def pacs_case_send(order_id):
        order=_rb.Order.query.get_or_404(order_id)
        dest=_rb.DicomDestination.query.get_or_404(_rb.request.form.get('destination_id',type=int))
        if not order.pacs_study_id:
            _rb.pacs_lookup_order(order);_rb.db.session.flush()
        if not order.pacs_study_id:
            _rb.flash('No PACS study is linked to this order.','danger');return _rb.redirect(_rb.url_for('pacs_case_actions',order_id=order.id))
        if not dest.active or not dest.allow_manual_send:_rb.abort(403)
        if _rb.current_user().role and _rb.current_user().role.code in ('TECHNICIAN','SERVICE') and dest.branch_id and dest.branch_id!=_rb.current_user().branch_id:_rb.abort(403)
        job=_rb.enqueue_transfer(order,order.pacs_study_id,dest,'RESEND' if _rb.request.form.get('resend')=='1' else 'MANUAL',_rb.current_user().id)
        _rb.audit('PACS_TRANSFER_QUEUE','order',order.id,f'job={job.id}; destination={dest.name}; ae={dest.ae_title}')
        _rb.db.session.commit()
        _rb.flash('Transfer queued.','success');return _rb.redirect(_rb.url_for('pacs_case_actions',order_id=order.id))
    return pacs_case_send


def install_0820(_rb):
    @_rb.app.post('/pacs/transfers/<int:job_id>/retry')
    @_rb.require_perm('pacs.transfer')
    def pacs_transfer_retry(job_id):
        job=_rb.PacsTransferJob.query.get_or_404(job_id)
        if job.status not in ('FAILED','CANCELLED','SUCCESS'):_rb.abort(400)
        job.status='PENDING';job.last_error='';job.completed_at=None;job.cancelled_at=None;job.progress_sent=0
        _rb.audit('PACS_TRANSFER_RETRY','pacs_transfer_job',job.id,f'destination={job.destination.name}')
        _rb.db.session.commit();_rb.flash('Transfer queued for retry.','success')
        return _rb.redirect(_rb.request.referrer or (_rb.url_for('pacs_case_actions',order_id=job.order_id) if job.order_id else _rb.url_for('pacs_archive_dashboard')))
    return pacs_transfer_retry


def install_0821(_rb):
    @_rb.app.post('/pacs/transfers/<int:job_id>/cancel')
    @_rb.require_perm('pacs.transfer')
    def pacs_transfer_cancel(job_id):
        job=_rb.PacsTransferJob.query.get_or_404(job_id)
        if job.status not in ('PENDING','FAILED'):_rb.abort(400)
        job.status='CANCELLED';job.cancelled_at=_rb.datetime.utcnow()
        _rb.audit('PACS_TRANSFER_CANCEL','pacs_transfer_job',job.id,f'destination={job.destination.name}')
        _rb.db.session.commit();_rb.flash('Transfer cancelled.','warning')
        return _rb.redirect(_rb.request.referrer or (_rb.url_for('pacs_case_actions',order_id=job.order_id) if job.order_id else _rb.url_for('pacs_archive_dashboard')))
    return pacs_transfer_cancel


def install_0822(_rb):
    @_rb.app.post('/pacs/destinations/<int:destination_id>/echo')
    @_rb.require_perm('pacs.transfer')
    def pacs_destination_echo(destination_id):
        dest=_rb.DicomDestination.query.get_or_404(destination_id)
        if _rb.current_user().role and _rb.current_user().role.code in ('TECHNICIAN','SERVICE') and dest.branch_id and dest.branch_id!=_rb.current_user().branch_id:_rb.abort(403)
        try:
            _rb.test_dicom_destination(dest);_rb.audit('DICOM_ECHO_OK','dicom_destination',dest.id,f'{dest.ae_title}@{dest.host}:{dest.port}');_rb.db.session.commit()
            _rb.flash(f'C-ECHO OK: {dest.name}','success')
        except Exception as exc:
            _rb.db.session.rollback();_rb.flash(f'C-ECHO failed: {str(exc)[:300]}','danger')
        return _rb.redirect(_rb.request.referrer or _rb.url_for('pacs_case_actions',order_id=_rb.request.args.get('order_id',type=int)))
    return pacs_destination_echo


def install_0823(_rb):
    @_rb.app.post('/pacs/transfers/process')
    @_rb.require_perm('pacs.transfer')
    def pacs_transfer_process():
        n=_rb.process_pacs_transfer_jobs(50);_rb.flash(f'Processed {n} successful transfer(s).','success')
        return _rb.redirect(_rb.request.referrer or _rb.url_for('workflow_command_center'))
    return pacs_transfer_process


def install_0824(_rb):
    @_rb.app.get('/pacs/archive')
    @_rb.require_perm('pacs.archive.manage')
    def pacs_archive_dashboard():
        jobs=_rb.PacsTransferJob.query.order_by(_rb.PacsTransferJob.id.desc()).limit(500).all()
        archives=_rb.DicomDestination.query.filter(_rb.DicomDestination.destination_type.in_(['ARCHIVE','BACKUP'])).all()
        return _rb.render_template('pacs_archive.html',jobs=jobs,archives=archives)
    return pacs_archive_dashboard


def install_0835(_rb):
    @_rb.app.get('/admin/pacs/discovery')
    @_rb.require_perm('pacs.discovery.view')
    def pacs_discovery():
        rows=_rb.DiscoveredDicomNode.query.filter(_rb.DiscoveredDicomNode.status!='DISMISSED').order_by(
            _rb.DiscoveredDicomNode.last_seen_at.desc()).limit(500).all()
        branches=_rb.Branch.query.filter_by(active=True).order_by(_rb.Branch.name).all()
        ingress_ready=_rb.dicom_ingress_policy_ready()
        managed_ids=set()
        legacy_nodes={}
        try:
            response=_rb.requests.get(f'{_rb.PACS_ORTHANC_URL}/modalities?expand',
                                  auth=_rb._orthanc_auth(),timeout=10)
            response.raise_for_status()
            keys=response.json()
            if not isinstance(keys,dict):raise ValueError('Invalid Orthanc modalities')
            managed_ids={row.id for row in rows if _rb.modality_key(row.id) in keys}
            legacy_nodes={row.id:keys[row.ae_title] for row in rows
                          if row.status=='APPROVED' and row.ae_title in keys and
                          row.id not in managed_ids and
                          keys[row.ae_title].get('AET')==row.ae_title}
        except (_rb.requests.RequestException,ValueError,TypeError,AttributeError):
            ingress_ready=False
        return _rb.render_template('pacs_discovery.html',rows=rows,branches=branches,
                               ingress_ready=ingress_ready,managed_ids=managed_ids,
                               legacy_nodes=legacy_nodes)
    return pacs_discovery


def install_0850(_rb):
    @_rb.app.post('/admin/pacs/discovery/<int:node_id>/approve')
    @_rb.require_perm('pacs.discovery.manage')
    def pacs_discovery_approve(node_id):
        row=_rb.DiscoveredDicomNode.query.get_or_404(node_id)
        try:
            payload=_rb.node_payload(
                _rb.request.form.get('ae_title') or row.ae_title,
                _rb.request.form.get('host') or row.host,
                _rb.request.form.get('port') or row.port,
                allow_find=_rb.request.form.get('allow_find')=='1',
                allow_store=_rb.request.form.get('allow_store')=='1')
        except ValueError as exc:
            _rb.abort(400,description=str(exc))
        _rb._apply_discovered_node_policy(row,payload)
        _rb.flash('Incoming DICOM permissions applied and verified in Orthanc.','success')
        return _rb.redirect(_rb.url_for('pacs_discovery'))
    return pacs_discovery_approve


def install_0851(_rb):
    @_rb.app.post('/admin/pacs/discovery/<int:node_id>/block')
    @_rb.require_perm('pacs.discovery.manage')
    def pacs_discovery_block(node_id):
        row=_rb.DiscoveredDicomNode.query.get_or_404(node_id)
        _rb._apply_discovered_node_policy(row,None)
        _rb.flash('Orthanc registration removed and incoming access disabled.','warning')
        return _rb.redirect(_rb.url_for('pacs_discovery'))
    return pacs_discovery_block


def install_0852(_rb):
    @_rb.app.post('/admin/pacs/discovery/<int:node_id>/legacy-endpoint')
    @_rb.require_perm('pacs.discovery.manage')
    def pacs_discovery_legacy_endpoint(node_id):
        """Edit only the endpoint of an existing legacy Orthanc registration.

    This leaves every DICOM permission as it was; it does not claim to block
    C-STORE while the Live Orthanc default still accepts unknown senders.
    """
        row=_rb.DiscoveredDicomNode.query.get_or_404(node_id)
        if row.status!='APPROVED':_rb.abort(409,description='Node is not approved')
        key=row.ae_title
        if not _rb.re.fullmatch(r'[A-Z0-9_ -]{1,16}',key):_rb.abort(409)
        response=_rb.requests.get(f'{_rb.PACS_ORTHANC_URL}/modalities?expand',
                              auth=_rb._orthanc_auth(),timeout=10)
        response.raise_for_status()
        modalities=response.json()
        if not isinstance(modalities,dict) or key not in modalities or \
           modalities[key].get('AET')!=key or _rb.modality_key(row.id) in modalities or \
           sum(node.get('AET')==key for node in modalities.values())!=1:
            _rb.abort(409,description='Legacy Orthanc identity changed')
        previous=modalities[key]
        if _rb.request.form.get('expected_host')!=previous.get('Host') or \
           _rb.request.form.get('expected_port')!=str(previous.get('Port')):
            _rb.abort(409,description='Orthanc endpoint changed; refresh and review')
        try:
            proposed=_rb.legacy_endpoint_payload(
                previous,_rb.request.form.get('host'),_rb.request.form.get('port'))
        except ValueError as exc:
            _rb.abort(400,description=str(exc))
        if proposed==previous:
            _rb.flash('Orthanc endpoint is already set to these values.','info')
            return _rb.redirect(_rb.url_for('pacs_discovery'))
        url=f'{_rb.PACS_ORTHANC_URL}/modalities/{key}'
        try:
            response=_rb.requests.put(url,auth=_rb._orthanc_auth(),json=proposed,timeout=10)
            response.raise_for_status()
            after=_rb.requests.get(url+'/configuration',auth=_rb._orthanc_auth(),timeout=10)
            after.raise_for_status()
            if not _rb.legacy_endpoint_matches(previous,after.json(),proposed):
                raise RuntimeError('Orthanc did not retain the exact endpoint and permissions')
            row.port=proposed['Port']
            _rb.audit('DICOM_LEGACY_ENDPOINT_EDIT','discovered_dicom_node',row.id,
                  f'{key}:{previous["Host"]}:{previous["Port"]} -> '
                  f'{proposed["Host"]}:{proposed["Port"]};permissions_unchanged=true')
            _rb.db.session.commit()
        except Exception:
            _rb.db.session.rollback()
            try:
                restore=_rb.requests.put(url,auth=_rb._orthanc_auth(),json=previous,timeout=10)
                restore.raise_for_status()
                actual=_rb.requests.get(url+'/configuration',auth=_rb._orthanc_auth(),timeout=10)
                actual.raise_for_status()
                if actual.json()!=previous:raise RuntimeError('Orthanc rollback mismatch')
            except Exception as restore_error:
                _rb.app.logger.critical('Legacy DICOM node %s rollback failed: %s',
                                    node_id,restore_error)
                _rb.abort(503,description='Orthanc rollback failed; manual review required')
            raise
        _rb.flash('Legacy Orthanc endpoint updated; Worklist and Store permissions preserved.','success')
        return _rb.redirect(_rb.url_for('pacs_discovery'))
    return pacs_discovery_legacy_endpoint


def install_0853(_rb):
    @_rb.app.post('/admin/pacs/discovery/<int:node_id>/dismiss')
    @_rb.require_perm('pacs.discovery.manage')
    def pacs_discovery_dismiss(node_id):
        row=_rb.DiscoveredDicomNode.query.get_or_404(node_id)
        if row.status not in ('PENDING','BLOCKED'):
            _rb.abort(409,description='Disable approved access before removing the record')
        if _rb._managed_dicom_modality(row.id) is not None:
            _rb.abort(409,description='Managed Orthanc registration still exists')
        # A legacy Orthanc registration with the same AE Title is independent.
        # Removing a review record must never change any DICOM access or study.
        row.status='DISMISSED'
        _rb.audit('DICOM_DISCOVERY_DISMISS','discovered_dicom_node',row.id,
              f'{row.ae_title}@{row.host}')
        _rb.db.session.commit()
        _rb.flash('Node removed from review. Orthanc and studies were not changed.','success')
        return _rb.redirect(_rb.url_for('pacs_discovery'))
    return pacs_discovery_dismiss


def install_0854(_rb):
    @_rb.app.post('/admin/pacs/discovery/manual')
    @_rb.require_perm('pacs.discovery.manage')
    def pacs_discovery_manual():
        ae=(_rb.request.form.get('ae_title') or '').strip().upper()
        host=(_rb.request.form.get('host') or '').strip()
        port=_rb.request.form.get('port',type=int) or 0
        node_type=(_rb.request.form.get('node_type') or 'VIEWER').upper()
        try:
            # Validate identity without authorizing either operation yet.
            _rb.node_payload(ae,host,port,allow_find=True)
        except ValueError as exc:
            _rb.abort(400,description=str(exc))
        if node_type not in ('VIEWER','MODALITY','UNKNOWN'):_rb.abort(400)
        row=_rb.DiscoveredDicomNode.query.filter_by(ae_title=ae,host=host).first()
        if not row:
            row=_rb.DiscoveredDicomNode(ae_title=ae,host=host,port=port,node_type=node_type,status='PENDING')
            _rb.db.session.add(row);_rb.db.session.flush()
        else:
            if row.status=='APPROVED':
                _rb.abort(409,description='Edit approved nodes through Orthanc access controls')
            if row.status=='DISMISSED':
                row.status='PENDING'
            row.port=port or row.port;row.node_type=node_type;row.last_seen_at=_rb.datetime.utcnow()
        _rb.db.session.commit()
        return _rb.redirect(_rb.url_for('pacs_discovery'))
    return pacs_discovery_manual
