"""Runtime-bound web.routes.clinical; dependencies are supplied at composition.

Legacy behavior is preserved; new policies belong in the independent domain layer.
"""

def install_0168(_rb):
    @_rb.app.route('/nursing')
    @_rb.require_perm('nursing.worklist')
    def nursing_worklist():
        from staff_worklist_filters import default_redirect, context, apply
        redirect_default=default_redirect(_rb._reporting_support_sys.modules[_rb.__name__],'NURSING')
        if redirect_default:return redirect_default
        staff_context=context(_rb._reporting_support_sys.modules[_rb.__name__],'NURSING')
        # RB_ROLE_WORKLIST_FILTERS_V1
        q = _rb.Order.query.filter(_rb.Order.status.notin_(['FINAL', 'CANCELLED']))

        search = (_rb.request.args.get('q') or '').strip()
        date_from = (_rb.request.args.get('date_from') or '').strip()
        date_to = (_rb.request.args.get('date_to') or '').strip()
        priority = (_rb.request.args.get('priority') or '').strip().upper()

        if search:
            like = f'%{search}%'
            q = q.join(_rb.Patient).filter(_rb.db.or_(
                _rb.Patient.name.ilike(like),
                _rb.Patient.patient_id.ilike(like),
                _rb.Patient.phone.ilike(like),
                _rb.Patient.national_id.ilike(like),
                _rb.Order.accession.ilike(like),
                _rb.Order.procedure.ilike(like),
                _rb.Order.modality.ilike(like),
            ))

        if priority:
            q = q.filter(_rb.Order.priority == priority)

        if date_from:
            try:
                start_day = _rb.datetime.strptime(date_from, '%Y-%m-%d')
                q = q.filter(_rb.Order.scheduled >= start_day)
            except ValueError:
                pass

        if date_to:
            try:
                end_day = _rb.datetime.strptime(date_to, '%Y-%m-%d') + _rb.timedelta(days=1)
                q = q.filter(_rb.Order.scheduled < end_day)
            except ValueError:
                pass

        q=apply(_rb._reporting_support_sys.modules[_rb.__name__],q,'NURSING',staff_context)
        orders = (
            q.order_by(_rb.Order.scheduled.desc())
            .limit(300)
            .all()
        )

        rows = []

        for order in orders:
            defaults = (
                _rb.ProcedureConsumable.query
                .filter_by(procedure_id=order.procedure_id)
                .count()
                if order.procedure_id
                else 0
            )
            confirmed = (
                _rb.NursingConsumableEntry.query
                .filter_by(order_id=order.id, confirmed=True)
                .count()
            )
            rows.append((order, defaults, confirmed))

        image_urls = {
            order.id: _rb.clinical_image_only_url(order)
            for order in orders
        }

        attachment_counts = {
            order.id: _rb._order_attachment_count(order)
            for order in orders
        }

        return _rb.render_template(
            'nursing.html',
            rows=rows,
            image_urls=image_urls,
            attachment_counts=attachment_counts,
            saved_views=_rb._saved_views_for('NURSING'),
            saved_view_page='NURSING',
            **staff_context,
        )
    return nursing_worklist


def install_0179(_rb):
    @_rb.app.get('/technician/<int:order_id>')
    @_rb.require_perm('technician.worklist')
    def technician_case_workspace(order_id):
        order = _rb.Order.query.get_or_404(order_id)
        from technician_queue import scoped_order
        scoped_order(_rb._reporting_support_sys.modules[_rb.__name__], order)
        warehouse = _rb.default_warehouse_for_order(order)

        notes = (
            _rb.ClinicalNote.query
            .filter_by(order_id=order.id)
            .order_by(_rb.ClinicalNote.created_at.desc())
            .limit(30)
            .all()
        )
        attachments = (
            _rb.Attachment.query
            .filter_by(order_id=order.id)
            .order_by(_rb.Attachment.created_at.desc())
            .limit(30)
            .all()
        )
        usages = (
            _rb.OrderConsumableUsage.query
            .filter_by(order_id=order.id)
            .order_by(_rb.OrderConsumableUsage.created_at.desc())
            .limit(50)
            .all()
        )
        timeline = (
            _rb.AuditLog.query
            .filter_by(entity='order', entity_id=str(order.id))
            .order_by(_rb.AuditLog.created_at.desc())
            .limit(40)
            .all()
        )

        inventory_rows = []
        if warehouse:
            for item in (
                _rb.InventoryItem.query
                .filter_by(active=True)
                .order_by(_rb.InventoryItem.name.asc())
                .all()
            ):
                available = _rb.inventory_available_qty(
                    warehouse.id,
                    item.id,
                )
                if available > 0:
                    inventory_rows.append({
                        'item': item,
                        'available': available,
                    })

        return _rb.render_template(
            'technician_case.html',
            return_state=_rb.case_return_snapshot(order.id),
            image_requests=_rb.CorrectionRequest.query.filter_by(order_id=order.id,request_type='WRONG_IMAGES').order_by(_rb.CorrectionRequest.id.desc()).limit(5).all(),
            quality_rule=_rb.quality_rule_for(order),
            acquisition_minimum=_rb.technician_minimum_requirement(order,_rb.quality_rule_for(order))[0],
            acquisition_notes=_rb.technician_acquisition_notes(_rb.quality_rule_for(order)),
            image_readiness=__import__('reception_readiness').view(order,_rb.CaseReadiness.query.filter_by(order_id=order.id).first()),
            order=order,
            image_url=_rb.clinical_image_only_url(order),
            warehouse=warehouse,
            inventory_rows=inventory_rows,
            notes=notes,
            attachments=attachments,
            usages=usages,
            timeline=timeline,
            consumable_cost=_rb.order_consumable_cost(order),
        )
    return technician_case_workspace


def install_0180(_rb):
    @_rb.app.post('/technician/<int:order_id>/note')
    @_rb.require_perm('technician.worklist')
    def technician_case_note(order_id):
        order = _rb.Order.query.get_or_404(order_id)
        text = (_rb.request.form.get('text') or '').strip()

        if not text:
            _rb.flash('Technical note cannot be empty.', 'danger')
            return _rb.redirect(_rb.url_for(
                'technician_case_workspace',
                order_id=order.id,
            ))

        _rb.db.session.add(_rb.ClinicalNote(
            order_id=order.id,
            author_user_id=_rb.current_user().id,
            note_type='TECHNICAL',
            visibility='CLINICAL_TEAM',
            text=text,
        ))
        _rb.audit(
            'TECHNICIAN_NOTE_ADDED',
            'order',
            order.id,
            'Technical clinical-team note added',
        )
        _rb.db.session.commit()
        _rb.flash('Technical note saved.', 'success')

        return _rb.redirect(_rb.url_for(
            'technician_case_workspace',
            order_id=order.id,
        ))
    return technician_case_note


def install_0182(_rb):
    @_rb.app.route('/technician')
    @_rb.require_perm('technician.worklist')
    def technician_worklist():
        from technician_queue import render_worklist
        return render_worklist(_rb._reporting_support_sys.modules[_rb.__name__])
    return technician_worklist


def install_0186(_rb):
    @_rb.app.post('/technician/<int:order_id>/check-images')
    @_rb.require_perm('technician.worklist')
    def technician_check_images(order_id):
        order=_rb.Order.query.get_or_404(order_id)
        from technician_queue import scoped_order
        scoped_order(_rb._reporting_support_sys.modules[_rb.__name__],order)
        result,evidence=_rb.technician_completion_evidence(order)
        _rb.evaluate_case_readiness(order,pacs_evidence=evidence)
        _rb.audit('TECHNICIAN_IMAGE_CHECK','order',order.id,_rb.json.dumps(result,sort_keys=True))
        _rb.db.session.commit()
        if result['allowed']:
            _rb.flash(f"تم التحقق من الصور: {result['image_count']}. متطلبات الصور مستوفاة. / Images checked: {result['image_count']}. Image requirements are satisfied.",'success')
        else:
            _rb.flash({'order_id': order.id, 'details': result}, 'exam-completion-blocked')
        if result['warning']: _rb.flash(result['warning'],'warning')
        return _rb.redirect(_rb.url_for('technician_case_workspace',order_id=order.id))
    return technician_check_images


def install_0189(_rb):
    @_rb.app.route('/technician/<int:order_id>/status',methods=['POST'])
    @_rb.require_perm('orders.status')
    def technician_status(order_id):
        # Legacy compatibility endpoint routed through the canonical exam engine.
        order=_rb.Order.query.get_or_404(order_id)
        from technician_queue import scoped_order
        scoped_order(_rb._reporting_support_sys.modules[_rb.__name__],order)
        new=(_rb.request.form.get('status') or '').upper().strip()
        role_code=(_rb.current_user().role.code if _rb.current_user() and _rb.current_user().role else '').upper()

        if new=='ARRIVED':
            if (order.status or '').upper()!='SCHEDULED':
                _rb.flash('ARRIVED requires an active SCHEDULED Work Order.','danger')
                return _rb.redirect(_rb.url_for('technician_worklist'))
            order.status='ARRIVED'
            _rb.audit('ORDER_STATUS','order',order.id,'SCHEDULED->ARRIVED')
            _rb.db.session.commit()
            _rb.flash('Status updated.','success')
            return _rb.redirect(_rb.url_for('technician_worklist'))

        target={'IN_PROGRESS':'IN_PROGRESS','COMPLETED':'EXAM_COMPLETED'}.get(new)
        if not target:
            _rb.abort(400)

        decision,current=_rb._apply_exam_transition(order,target,role_code)
        if not decision.allowed:
            _rb.flash_exam_transition_blocked(order,decision,current,target)
            return _rb.redirect(_rb.url_for('technician_worklist'))

        if target=='EXAM_COMPLETED':
            # consume default items from stock once; prevent duplicate by a marker in audit
            marker=_rb.AuditLog.query.filter_by(action='CONSUMABLES_POSTED',entity='order',entity_id=str(order.id)).first()
            if not marker:
                for n in _rb.NursingConsumableEntry.query.filter_by(order_id=order.id,confirmed=True).all():
                    n.consumable.stock_qty=max(0,float(n.consumable.stock_qty or 0)-float(n.actual_qty or 0))
                _rb.audit('CONSUMABLES_POSTED','order',order.id,'Nursing-confirmed actual consumables deducted')

        _rb.audit('ORDER_STATUS','order',order.id,f'{current}->{target}')
        _rb.db.session.commit()
        _rb.flash('Status updated.','success')
        return _rb.redirect(_rb.url_for('technician_worklist'))
    return technician_status


def install_0192(_rb):
    @_rb.app.post('/orders/<int:order_id>/exam-status')
    @_rb.require_perm('technician.worklist')
    def order_exam_status(order_id):
        order=_rb.Order.query.get_or_404(order_id)
        from technician_queue import scoped_order
        scoped_order(_rb._reporting_support_sys.modules[_rb.__name__],order)
        target=(_rb.request.form.get('status') or '').upper().strip()
        role_code=(_rb.current_user().role.code if _rb.current_user() and _rb.current_user().role else '').upper()

        decision,current=_rb._apply_exam_transition(
            order,
            target,
            role_code,
            override=False,
        )
        if not decision.allowed:
            _rb.flash_exam_transition_blocked(order,decision,current,target)
            return _rb.redirect(_rb.request.referrer or _rb.url_for('technician_worklist'))

        _rb.audit('EXAM_STATUS_FORWARD','order',order.id,f'{current}->{target}')
        _rb.enqueue_event('EXAM_STATUS_CHANGED','order',order.id,{'from':current,'to':target,'accession':order.accession})
        _rb.db.session.commit()

        # RB_POST_EXAM_ASSIGNMENT_TRIGGER_V1
        if target=='EXAM_COMPLETED' and __import__('procedure_staff_workflow').policy(_rb._reporting_support_sys.modules[_rb.__name__],order)['require_images']:
            try:
                _rb.pacs_lookup_order(order)
                _rb.evaluate_case_readiness(order)
                _rb.db.session.commit()
                _rb.coordinate_post_exam_assignment(
                    order,
                    created_by=_rb.current_user().id if _rb.current_user() else None,
                    trigger='END_EXAM'
                )
            except Exception as exc:
                _rb.db.session.rollback()
                _rb.app.logger.warning(
                    'Post-exam assignment trigger failed order=%s: %s',
                    order.id,exc
                )

        _rb.flash(f'Case moved to {target}.','success')
        return _rb.redirect(_rb.request.referrer or _rb.url_for('technician_worklist'))
    return order_exam_status


def install_0193(_rb):
    @_rb.app.post('/orders/<int:order_id>/exam-status/override')
    @_rb.require_perm('workflow.override')
    def order_exam_status_override(order_id):
        order=_rb.Order.query.get_or_404(order_id)
        from technician_queue import scoped_order
        scoped_order(_rb._reporting_support_sys.modules[_rb.__name__],order)
        target=(_rb.request.form.get('status') or '').upper().strip()
        reason=(_rb.request.form.get('reason') or '').strip()
        if target not in _rb.EXAM_STATUS_ORDER: _rb.abort(400)
        if len(reason)<5:
            _rb.flash('Supervisor override requires a reason.','danger')
            return _rb.redirect(_rb.request.referrer or _rb.url_for('order_detail',order_id=order.id))

        role_code=(_rb.current_user().role.code if _rb.current_user() and _rb.current_user().role else '').upper()
        decision,old=_rb._apply_exam_transition(
            order,
            target,
            role_code,
            override=True,
        )
        if not decision.allowed:
            _rb.flash_exam_transition_blocked(order,decision,old,target)
            return _rb.redirect(_rb.request.referrer or _rb.url_for('order_detail',order_id=order.id))

        _rb.audit('EXAM_STATUS_OVERRIDE','order',order.id,f'{old}->{target} reason={reason}')
        _rb.enqueue_event('EXAM_STATUS_OVERRIDE','order',order.id,{'from':old,'to':target,'reason':reason,'accession':order.accession})
        _rb.db.session.commit()
        _rb.flash('Supervisor workflow override saved and audited.','warning')
        return _rb.redirect(_rb.request.referrer or _rb.url_for('order_detail',order_id=order.id))
    return order_exam_status_override


def install_0434(_rb):
    @_rb.app.route('/orders/<int:order_id>/clinical-notes',methods=['GET','POST'])
    @_rb.require_perm('orders.view')
    def order_clinical_notes(order_id):
        order=_rb.Order.query.get_or_404(order_id)
        if _rb.request.method=='POST':
            txt=(_rb.request.form.get('text') or '').strip()
            if not txt:
                _rb.flash('Clinical note cannot be empty.','danger')
                return _rb.redirect(_rb.url_for('order_clinical_notes',order_id=order.id))
            row=_rb.ClinicalNote(order_id=order.id,author_user_id=_rb.current_user().id,note_type=(_rb.request.form.get('note_type') or 'GENERAL').upper(),visibility=(_rb.request.form.get('visibility') or 'CLINICAL_TEAM').upper(),text=txt)
            _rb.db.session.add(row);_rb.db.session.commit()
            return _rb.redirect(_rb.url_for('order_clinical_notes',order_id=order.id))
        return _rb.render_template('order_clinical_notes.html',order=order,notes=_rb.ClinicalNote.query.filter_by(order_id=order.id).order_by(_rb.ClinicalNote.created_at.desc()).all())
    return order_clinical_notes


def install_0453(_rb):
    @_rb.app.post('/chat/<int:thread_id>/add-to-clinical-note/<int:message_id>')
    @_rb.require_perm('orders.view')
    def chat_message_to_clinical_note(thread_id,message_id):
        thread=_rb.ChatThread.query.get_or_404(thread_id);msg=_rb.ChatMessage.query.get_or_404(message_id)
        if thread.thread_type!='CASE' or not thread.order_id:_rb.abort(400)
        _rb.db.session.add(_rb.ClinicalNote(order_id=thread.order_id,author_user_id=_rb.current_user().id,note_type='GENERAL',visibility='CLINICAL_TEAM',text=msg.body));_rb.audit('CHAT_TO_CLINICAL_NOTE','order',thread.order_id,f'message={msg.id}');_rb.db.session.commit();return _rb.redirect(_rb.url_for('chat_thread',thread_id=thread.id))
    return chat_message_to_clinical_note


def install_0528(_rb):
    @_rb.app.route('/admin/diagnostics')
    @_rb.require_perm('users.view')
    def admin_diagnostics():
        checks=[]

        try:
            _rb.db.session.execute(_rb.text('SELECT 1'))
            checks.append(('Database','OK','PostgreSQL connection successful'))
        except Exception as exc:
            checks.append(('Database','ERROR',str(exc)))

        checks.append(('PACS','OK' if _rb.orthanc_ok() else 'ERROR',
                       'Orthanc responded' if _rb.orthanc_ok() else 'Orthanc is not reachable from RIS'))

        checks.append(('Report Storage','OK' if _rb.os.path.isdir(_rb.REPORT_DIR) and _rb.os.access(_rb.REPORT_DIR,_rb.os.W_OK) else 'ERROR',_rb.REPORT_DIR))
        checks.append(('Attachment Storage','OK' if _rb.os.path.isdir(_rb.ATTACHMENT_DIR) and _rb.os.access(_rb.ATTACHMENT_DIR,_rb.os.W_OK) else 'ERROR',_rb.ATTACHMENT_DIR))

        agent_path=_rb.os.path.join(_rb.os.path.dirname(_rb.__file__),'downloads','RIS-Reporting-Agent-Auto-v2.zip')
        checks.append(('Word Reporting Agent','OK' if _rb.os.path.exists(agent_path) else 'WARNING',
                       'Bundled' if _rb.os.path.exists(agent_path) else 'Agent package is missing; DOCX download/upload still works'))

        critical_routes=[
            '/api/reporting/health','/doctor','/reports/<int:order_id>',
            '/reports/<int:order_id>/word','/reports/<int:order_id>/upload',
            '/reporting-agent/download','/appointments','/analytics'
        ]
        rules={r.rule for r in _rb.app.url_map.iter_rules()}
        for route in critical_routes:
            checks.append((f'Route {route}','OK' if route in rules else 'ERROR',
                           'Registered' if route in rules else 'Missing'))

        return _rb.render_template('diagnostics.html',checks=checks,version=_rb.APP_VERSION)
    return admin_diagnostics

