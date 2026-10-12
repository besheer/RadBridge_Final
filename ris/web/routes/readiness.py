"""Runtime-bound web.routes.readiness; dependencies are supplied at composition.

Legacy behavior is preserved; new policies belong in the independent domain layer.
"""

def install_0695(_rb):
    @_rb.app.get('/operations/case-readiness')
    @_rb.require_perm('orders.view')
    def case_readiness_dashboard():
        q=_rb.Order.query.order_by(_rb.Order.id.desc()).limit(300).all()
        rows=[(o,_rb.CaseReadiness.query.filter_by(order_id=o.id).first(),_rb.case_delay_snapshot(o)) for o in q]
        return _rb.render_template('case_readiness_dashboard.html',rows=rows)
    return case_readiness_dashboard


def install_0697(_rb):
    @_rb.app.get('/operations/case-exceptions')
    @_rb.require_perm('orders.view')
    def case_exception_resolver():
        from case_exception_resolution_service import search_ris_orders

        q=(_rb.request.args.get('q') or '').strip()
        order_id=_rb.request.args.get('order_id',type=int)
        status_filter=(_rb.request.args.get('status') or 'BLOCKED').strip().upper()
        modality_filter=(_rb.request.args.get('modality') or '').strip().upper()
        branch_filter=_rb.request.args.get('branch_id',type=int)
        blocker_filter=(_rb.request.args.get('blocker') or '').strip().upper()
        scope_filter=(_rb.request.args.get('scope') or 'EDITABLE').strip().upper()
        page=max(1,_rb.request.args.get('page',1,type=int))
        per_page=25
        results=search_ris_orders(Order=_rb.Order,Patient=_rb.Patient,query=q,limit=50)
        queue_query=(_rb.db.session.query(_rb.CaseReadiness,_rb.Order)
                     .join(_rb.Order,_rb.Order.id==_rb.CaseReadiness.order_id))
        if status_filter in ('BLOCKED','WARNING','READY','NOT_CHECKED'):
            queue_query=queue_query.filter(_rb.CaseReadiness.status==status_filter)
        if modality_filter:
            queue_query=queue_query.filter(_rb.func.upper(_rb.Order.modality)==modality_filter)
        if branch_filter:
            queue_query=queue_query.filter(_rb.Order.branch_id==branch_filter)
        blocker_columns={
            'MISSING_PACS':_rb.CaseReadiness.missing_pacs,
            'INCOMPLETE_IMAGES':_rb.CaseReadiness.incomplete_images,
            'MISSING_SERIES':_rb.CaseReadiness.missing_series,
            'MISSING_HISTORY':_rb.CaseReadiness.missing_history,
            'MISSING_ATTACHMENTS':_rb.CaseReadiness.missing_attachments,
            'MISSING_DOCUMENTS':_rb.CaseReadiness.missing_documents,
            'MISSING_NOTES':_rb.CaseReadiness.missing_notes,
        }
        if blocker_filter in blocker_columns:
            queue_query=queue_query.filter(blocker_columns[blocker_filter].is_(True))
        if scope_filter=='EDITABLE':
            queue_query=(queue_query.outerjoin(_rb.Report,_rb.Report.order_id==_rb.Order.id)
                         .filter(_rb.func.upper(_rb.func.coalesce(_rb.Order.status,''))
                                 .notin_(('FINAL','CANCELLED')),
                                 _rb.func.upper(_rb.func.coalesce(_rb.Report.status,'UNREPORTED'))
                                 .notin_(('VERIFIED','FINAL'))))
        queue_total=queue_query.count()
        queue_rows=(queue_query.order_by(_rb.CaseReadiness.checked_at.desc(),_rb.Order.id.desc())
                    .offset((page-1)*per_page).limit(per_page).all())
        queue=[]
        for readiness_row,order_row in queue_rows:
            try: queue_details=_rb.json.loads(readiness_row.details_json or '{}')
            except Exception: queue_details={}
            queue.append({'order':order_row,'readiness':readiness_row,
                          'blockers':queue_details.get('blockers',[])})
        queue_pages=max(1,(queue_total+per_page-1)//per_page)
        branches=_rb.Branch.query.filter_by(active=True).order_by(_rb.Branch.name).all()
        modalities=[row[0] for row in _rb.db.session.query(_rb.Order.modality).distinct()
                    .order_by(_rb.Order.modality).all() if row[0]]
        selected=_rb.Order.query.get_or_404(order_id) if order_id else None
        readiness=None;rule=None;series=[];details={};aliases=[];events=[];report=None;overrides=[]
        if selected:
            readiness=__import__('reception_readiness').view(selected,_rb.CaseReadiness.query.filter_by(order_id=selected.id).first())
            rule=_rb.quality_rule_for(selected)
            report=_rb.Report.query.filter_by(order_id=selected.id).order_by(_rb.Report.id.desc()).first()
            if readiness:
                try: series=_rb.json.loads(readiness.series_evidence_json or '[]')
                except Exception: series=[]
                try: details=_rb.json.loads(readiness.details_json or '{}')
                except Exception: details={}
            if rule:
                aliases=(_rb.ReadinessSeriesAlias.query.filter_by(rule_id=rule.id)
                         .order_by(_rb.ReadinessSeriesAlias.id.desc()).all())
            events=(_rb.CaseExceptionResolutionEvent.query.filter_by(order_id=selected.id)
                    .order_by(_rb.CaseExceptionResolutionEvent.created_at.desc()).limit(30).all())
            overrides=(_rb.CaseReadinessOverride.query.filter_by(order_id=selected.id,active=True)
                       .order_by(_rb.CaseReadinessOverride.id.desc()).all())
        selected_editable=bool(
            selected
            and str(selected.status or '').upper() not in ('FINAL','CANCELLED')
            and str(getattr(report,'status','') or '').upper() not in ('VERIFIED','FINAL')
        )
        can_reconcile=_rb.has_perm('pacs.reconcile') and selected_editable
        can_add_history=selected_editable and any(_rb.has_perm(permission) for permission in (
            'orders.create','nursing.worklist','reports.coordinate','pacs.reconcile'))
        can_refresh=selected_editable and any(_rb.has_perm(permission) for permission in (
            'orders.status','nursing.worklist','reports.coordinate','assignment.manage',
            'pacs.reconcile'))
        can_override=selected_editable and _rb.has_perm('pacs.reconcile') and _rb.has_perm('workflow.override')
        return _rb.render_template(
            'case_exception_resolver.html',q=q,results=results,selected=selected,
            readiness=readiness,rule=rule,series=series,details=details,
            aliases=aliases,events=events,report=report,overrides=overrides,
            can_resolve=can_reconcile,can_reconcile=can_reconcile,
            can_map_series=can_reconcile and bool(rule) and bool(series),
            can_add_history=can_add_history,can_refresh=can_refresh,
            can_override=can_override,
            can_manage_quality_rules=_rb.has_perm('users.view'),
            can_view_resolution_history=_rb.has_perm('audit.view') or _rb.has_perm('pacs.reconcile'),
            focus_mode=bool(selected),
            selected_editable=selected_editable,queue=queue,
            queue_total=queue_total,queue_page=page,queue_pages=queue_pages,
            branches=branches,modalities=modalities,status_filter=status_filter,
            modality_filter=modality_filter,branch_filter=branch_filter,
            blocker_filter=blocker_filter,scope_filter=scope_filter,
        )
    return case_exception_resolver


def install_0698(_rb):
    @_rb.app.post('/orders/<int:order_id>/exceptions/series-map')
    @_rb.require_perm('pacs.reconcile')
    def case_exception_series_map(order_id):
        from case_exception_resolution_service import (
            CaseExceptionResolutionError,
            atomic_series_alias_mapping,
        )
        try:
            result=atomic_series_alias_mapping(
                db=_rb.db,Order=_rb.Order,Report=_rb.Report,
                ProcedureQualityRule=_rb.ProcedureQualityRule,
                ReadinessSeriesAlias=_rb.ReadinessSeriesAlias,
                CaseReadiness=_rb.CaseReadiness,
                ResolutionEvent=_rb.CaseExceptionResolutionEvent,
                order_id=order_id,source_alias=_rb.request.form.get('source_alias'),
                canonical_series=_rb.request.form.get('canonical_series'),
                match_field=_rb.request.form.get('match_field'),
                actor_user_id=_rb.current_user().id,reason=_rb.request.form.get('reason'),
            )
            order=_rb.Order.query.get(order_id)
            readiness=_rb.evaluate_case_readiness(order)
            _rb.audit('CASE_EXCEPTION_SERIES_MAPPED','order',order_id,
                  f"rule={result['rule'].id}; alias={_rb.request.form.get('source_alias')}; canonical={_rb.request.form.get('canonical_series')}; status={readiness.status}")
            _rb.db.session.commit()
            _rb.flash('Series mapping saved and readiness recalculated.','success')
        except (CaseExceptionResolutionError,Exception) as exc:
            _rb.db.session.rollback()
            code=getattr(exc,'code',type(exc).__name__)
            _rb.flash(f'Series mapping was not saved: {code}','danger')
        return _rb.redirect(_rb.url_for('case_exception_resolver',order_id=order_id))
    return case_exception_series_map


def install_0699(_rb):
    @_rb.app.post('/orders/<int:order_id>/exceptions/series-map/<int:alias_id>/deactivate')
    @_rb.require_perm('pacs.reconcile')
    def case_exception_series_map_deactivate(order_id,alias_id):
        from case_exception_resolution_service import atomic_deactivate_series_alias
        try:
            atomic_deactivate_series_alias(
                db=_rb.db,Order=_rb.Order,Report=_rb.Report,
                ReadinessSeriesAlias=_rb.ReadinessSeriesAlias,
                ResolutionEvent=_rb.CaseExceptionResolutionEvent,
                order_id=order_id,alias_id=alias_id,
                actor_user_id=_rb.current_user().id,reason=_rb.request.form.get('reason'))
            readiness=_rb.evaluate_case_readiness(_rb.Order.query.get(order_id))
            _rb.audit('CASE_EXCEPTION_SERIES_ALIAS_DEACTIVATED','order',order_id,
                  f'alias={alias_id}; status={readiness.status}')
            _rb.db.session.commit();_rb.flash('Series mapping disabled and readiness recalculated.','success')
        except Exception as exc:
            _rb.db.session.rollback();_rb.flash(f'Series mapping was not disabled: {getattr(exc,"code",type(exc).__name__)}','danger')
        return _rb.redirect(_rb.url_for('case_exception_resolver',order_id=order_id))
    return case_exception_series_map_deactivate


def install_0703(_rb):
    @_rb.app.post('/orders/<int:order_id>/exceptions/history')
    @_rb.require_perm('orders.view')
    def case_exception_history_add(order_id):
        if not _rb.case_exception_history_allowed():
            _rb.abort(403)
        from case_exception_resolution_service import (
            CaseExceptionResolutionError,
            atomic_add_clinical_history,
        )
        try:
            atomic_add_clinical_history(
                db=_rb.db,Order=_rb.Order,Report=_rb.Report,ClinicalNote=_rb.ClinicalNote,
                ResolutionEvent=_rb.CaseExceptionResolutionEvent,
                order_id=order_id,text_value=_rb.request.form.get('history_text'),
                actor_user_id=_rb.current_user().id,reason=_rb.request.form.get('reason'),
            )
            order=_rb.Order.query.get(order_id)
            readiness=_rb.evaluate_case_readiness(order)
            _rb.audit('CASE_EXCEPTION_HISTORY_ADDED','order',order_id,
                  f'status={readiness.status}')
            _rb.db.session.commit()
            _rb.flash('Clinical history added and readiness recalculated.','success')
        except (CaseExceptionResolutionError,Exception) as exc:
            _rb.db.session.rollback()
            code=getattr(exc,'code',type(exc).__name__)
            _rb.flash(f'Clinical history was not saved: {code}','danger')
        return _rb.redirect(_rb.url_for('case_exception_resolver',order_id=order_id))
    return case_exception_history_add


def install_0704(_rb):
    @_rb.app.post('/orders/<int:order_id>/exceptions/image-minimum')
    @_rb.require_perm('pacs.reconcile')
    def case_exception_image_minimum(order_id):
        if not _rb.case_exception_override_allowed():
            _rb.abort(403)
        from case_exception_resolution_service import atomic_image_minimum_override
        try:
            atomic_image_minimum_override(
                db=_rb.db,Order=_rb.Order,Report=_rb.Report,
                CaseReadiness=_rb.CaseReadiness,
                CaseReadinessOverride=_rb.CaseReadinessOverride,
                ResolutionEvent=_rb.CaseExceptionResolutionEvent,
                order_id=order_id,
                approved_minimum=_rb.request.form.get('approved_minimum'),
                actor_user_id=_rb.current_user().id,reason=_rb.request.form.get('reason'),
            )
            order=_rb.Order.query.get(order_id)
            readiness=_rb.evaluate_case_readiness(order)
            _rb.audit('CASE_EXCEPTION_IMAGE_MINIMUM_OVERRIDE','order',order_id,
                  f'approved_minimum={_rb.request.form.get("approved_minimum")}; status={readiness.status}')
            _rb.db.session.commit()
            _rb.flash('Case-specific image minimum saved and readiness recalculated.','success')
        except Exception as exc:
            _rb.db.session.rollback()
            code=getattr(exc,'code',type(exc).__name__)
            _rb.flash(f'Image minimum override was not saved: {code}','danger')
        return _rb.redirect(_rb.url_for('case_exception_resolver',order_id=order_id))
    return case_exception_image_minimum


def install_0705(_rb):
    @_rb.app.post('/orders/<int:order_id>/exceptions/image-minimum/<int:override_id>/deactivate')
    @_rb.require_perm('pacs.reconcile')
    def case_exception_image_minimum_deactivate(order_id,override_id):
        if not _rb.case_exception_override_allowed():
            _rb.abort(403)
        from case_exception_resolution_service import atomic_deactivate_readiness_override
        try:
            atomic_deactivate_readiness_override(
                db=_rb.db,Order=_rb.Order,Report=_rb.Report,
                CaseReadinessOverride=_rb.CaseReadinessOverride,
                ResolutionEvent=_rb.CaseExceptionResolutionEvent,
                order_id=order_id,override_id=override_id,
                actor_user_id=_rb.current_user().id,reason=_rb.request.form.get('reason'))
            readiness=_rb.evaluate_case_readiness(_rb.Order.query.get(order_id))
            _rb.audit('CASE_EXCEPTION_OVERRIDE_DEACTIVATED','order',order_id,
                  f'override={override_id}; status={readiness.status}')
            _rb.db.session.commit();_rb.flash('Readiness override disabled and recalculated.','success')
        except Exception as exc:
            _rb.db.session.rollback();_rb.flash(f'Readiness override was not disabled: {getattr(exc,"code",type(exc).__name__)}','danger')
        return _rb.redirect(_rb.url_for('case_exception_resolver',order_id=order_id))
    return case_exception_image_minimum_deactivate


def install_0706(_rb):
    @_rb.app.post('/orders/<int:order_id>/exceptions/refresh')
    @_rb.require_perm('orders.view')
    def case_exception_refresh(order_id):
        if not _rb.case_exception_refresh_allowed():
            _rb.abort(403)
        order=_rb.Order.query.get_or_404(order_id)
        report=_rb.Report.query.filter_by(order_id=order.id).order_by(_rb.Report.id.desc()).first()
        if str(order.status or '').upper() in ('FINAL','CANCELLED') or str(getattr(report,'status','') or '').upper() in ('VERIFIED','FINAL'):
            _rb.abort(409)
        before=_rb.CaseReadiness.query.filter_by(order_id=order.id).first()
        old_status=str(getattr(before,'status','NOT_CHECKED'))
        row=_rb.evaluate_case_readiness(order)
        _rb.db.session.add(_rb.CaseExceptionResolutionEvent(
            order_id=order.id,action='READINESS_REFRESH',blocker='',
            old_value=old_status,new_value=row.status,
            reason='Authorized resolver refresh',actor_user_id=_rb.current_user().id,
        ))
        _rb.audit('CASE_EXCEPTION_READINESS_REFRESH','order',order.id,
              f'{old_status}->{row.status}')
        _rb.db.session.commit()
        _rb.flash('Readiness refreshed from current RIS and PACS evidence.','success')
        return _rb.redirect(_rb.url_for('case_exception_resolver',order_id=order.id))
    return case_exception_refresh


def install_0707(_rb):
    @_rb.app.post('/orders/<int:order_id>/readiness/check')
    @_rb.require_perm('orders.view')
    def case_readiness_check(order_id):
        o=_rb.Order.query.get_or_404(order_id);r=_rb.evaluate_case_readiness(o)
        if r.incomplete_images: _rb.create_ris_notification(o,'INCOMPLETE_IMAGES','Incomplete PACS images',f'{r.image_count}/{r.expected_min_images} images','WARNING','TECHNICIAN')
        if r.missing_history: _rb.create_ris_notification(o,'MISSING_HISTORY','Clinical history missing','Complete history before auto assignment','WARNING','RECEPTION')
        if r.missing_attachments: _rb.create_ris_notification(o,'MISSING_ATTACHMENTS','Required attachment missing','Complete required documents','WARNING','RECEPTION')
        return _rb.redirect(_rb.request.referrer or _rb.url_for('case_readiness_dashboard'))
    return case_readiness_check


def install_0708(_rb):
    @_rb.app.route('/admin/procedure-quality-rules',methods=['GET','POST'])
    @_rb.require_perm('users.view')
    def admin_procedure_quality_rules():
        if _rb.request.method=='POST':
            if not (_rb.has_perm('*') or _rb.has_perm('users.manage')): _rb.abort(403)
            modality=(_rb.request.form.get('modality') or '').strip().upper()
            pattern=(_rb.request.form.get('procedure_pattern') or '').strip().upper()
            minimum=_rb.request.form.get('min_images',type=int)
            warning=_rb.request.form.get('warning_images',type=int)
            if not modality or not pattern or minimum is None or warning is None or min(minimum,warning)<0:
                _rb.flash('Enter a modality, procedure pattern and non-negative image thresholds.','danger')
                return _rb.redirect(_rb.url_for('admin_procedure_quality_rules'))
            rule_id=_rb.request.form.get('rule_id',type=int)
            r=_rb.ProcedureQualityRule.query.get_or_404(rule_id) if rule_id else _rb.ProcedureQualityRule()
            before={k:getattr(r,k,None) for k in ('modality','procedure_pattern','min_images','warning_images','required_series','active')}
            r.modality=modality;r.procedure_pattern=pattern;r.min_images=minimum;r.warning_images=warning
            r.required_series=(_rb.request.form.get('required_series') or '').strip()
            for field in ('require_history','require_attachments','require_pacs_study','block_auto_assign','active'):
                setattr(r,field,_rb.request.form.get(field)=='1')
            _rb.db.session.add(r);_rb.db.session.flush()
            note=_rb.StudioTemplate.query.filter_by(template_type='TECH_ACQUISITION',name=str(r.id)).first()
            if not note:
                note=_rb.StudioTemplate(template_type='TECH_ACQUISITION',name=str(r.id),status='PUBLISHED',scope='GLOBAL')
                _rb.db.session.add(note)
            old_notes=note.notes or ''
            note.notes=(_rb.request.form.get('acquisition_notes') or '').strip()[:5000]
            after={k:getattr(r,k,None) for k in before}
            _rb.audit('PROCEDURE_QUALITY_POLICY_UPDATE','procedure_quality_rule',r.id,
                  _rb.json.dumps({'before':before,'after':after,'notes_before':old_notes,'notes_after':note.notes},sort_keys=True))
            _rb.db.session.commit()
            _rb.flash('Procedure image policy saved.','success')
            return _rb.redirect(_rb.url_for('admin_procedure_quality_rules'))
        rows=_rb.ProcedureQualityRule.query.order_by(_rb.ProcedureQualityRule.modality,_rb.ProcedureQualityRule.procedure_pattern).all()
        selected=_rb.ProcedureQualityRule.query.get(_rb.request.args.get('rule_id',type=int)) if _rb.request.args.get('rule_id',type=int) else None
        return _rb.render_template('admin_procedure_quality_rules.html',rows=rows,selected=selected,
                               acquisition_notes=_rb.technician_acquisition_notes(selected),can_edit=_rb.has_perm('*') or _rb.has_perm('users.manage'))
    return admin_procedure_quality_rules


def install_0721(_rb):
    @_rb.app.get('/operations/tat')
    @_rb.require_perm('orders.view')
    def tat_dashboard():
        orders=_rb.Order.query.order_by(_rb.Order.id.desc()).limit(500).all()
        rows=[(o,_rb.case_delay_snapshot(o)) for o in orders]
        return _rb.render_template('tat_dashboard.html',rows=rows)
    return tat_dashboard

