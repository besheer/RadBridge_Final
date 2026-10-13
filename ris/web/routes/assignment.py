"""Runtime-bound web.routes.assignment; dependencies are supplied at composition.

Legacy behavior is preserved; new policies belong in the independent domain layer.
"""

def install_0197(_rb):
    @_rb.app.post('/api/doctor/presence/heartbeat')
    @_rb.login_required
    def doctor_presence_heartbeat():
        u=_rb.current_user()
        role=(u.role.code if u and u.role else '').upper()
        if role not in ('RADIOLOGIST','DOCTOR'):
            _rb.abort(403)

        row=_rb.doctor_availability(u)
        row.last_seen_at=_rb.datetime.utcnow()
        if row.state=='OFFLINE':
            row.state='AVAILABLE'

        _rb.db.session.commit()
        return _rb.jsonify({'ok':True,'online':True,'state':row.state})
    return doctor_presence_heartbeat


def install_0206(_rb):
    @_rb.app.route('/admin/assignment-visits',methods=['GET','POST'])
    @_rb.require_perm('assignment.manage')
    def admin_assignment_visits():
        from assignment_visit_grouping import create_visit
        if _rb.request.method=='POST':
            reference=_rb.Order.query.get_or_404(_rb.request.form.get('reference_id',type=int))
            ids=_rb.request.form.getlist('order_ids',type=int)
            if not ids or reference.id not in ids:
                _rb.flash('Include the reference examination and at least one case.','warning')
                return _rb.redirect(_rb.url_for('admin_assignment_visits',order_id=reference.id))
            rows=_rb.Order.query.filter(_rb.Order.id.in_(ids)).order_by(_rb.Order.id).populate_existing().with_for_update().all()
            if len(rows)!=len(set(ids)) or any(o.patient_id!=reference.patient_id or o.branch_id!=reference.branch_id or o.scheduled.date()!=reference.scheduled.date() for o in rows):
                _rb.db.session.rollback();_rb.abort(422,description='Visit grouping requires the same patient, branch and visit date.')
            existing={o.assignment_visit_id for o in rows if o.assignment_visit_id}
            # An existing visit must be moved as a whole; partial merges could silently
            # leave hidden siblings assigned under a different preference.
            if existing:
                siblings=_rb.Order.query.filter(_rb.Order.assignment_visit_id.in_(existing)).all()
                if any(o.id not in ids for o in siblings):
                    _rb.db.session.rollback();_rb.abort(422,description='Include every examination in the existing visit before merging.')
            doctor_id=_rb.request.form.get('preferred_doctor_id',type=int)
            if doctor_id and doctor_id not in {u.id for u in _rb.assignable_doctors()}:
                _rb.db.session.rollback();_rb.abort(422,description='Choose an active reporting doctor.')
            visit_id=next(iter(existing)) if len(existing)==1 else create_visit(reference.patient_id,reference.branch_id,reference.scheduled)
            visit=_rb.AssignmentVisit.query.filter_by(id=visit_id).with_for_update().first()
            if visit.patient_id!=reference.patient_id or visit.branch_id!=reference.branch_id: _rb.abort(422)
            from assignment_distribution import policy_snapshot
            special_code=(_rb.request.form.get('special_code') or '').upper()
            if special_code and special_code not in {r['code'] for r in policy_snapshot()['special_rules'] if r['enabled']}:
                _rb.db.session.rollback();_rb.abort(422,description='Choose an enabled special-case rule.')
            owners={o.assigned_doctor_id for o in rows if o.assigned_doctor_id}
            if len(owners)>1:
                _rb.db.session.rollback();_rb.abort(422,description='Examinations have different owners. Resolve ownership before grouping.')
            visit.preferred_doctor_id=doctor_id
            for o in rows:
                o.assignment_special_code=special_code
                o.assignment_visit_id=visit_id
                if o.appointment: o.appointment.assignment_visit_id=visit_id
            _rb.audit('ASSIGNMENT_VISIT_SAVE','assignment_visit',visit_id,f'order_ids={sorted(ids)};preferred_doctor={doctor_id};existing ownership unchanged')
            _rb.db.session.commit()
            _rb.flash('Visit linked. Future eligible examinations prefer the selected doctor.','success')
            return _rb.redirect(_rb.url_for('admin_assignment_visits',order_id=reference.id))
        reference=_rb.Order.query.get_or_404(_rb.request.args.get('order_id',type=int)) if _rb.request.args.get('order_id') else None
        orders=[];visit=None
        if reference:
            orders=_rb.Order.query.filter_by(patient_id=reference.patient_id,branch_id=reference.branch_id).filter(_rb.func.date(_rb.Order.scheduled)==reference.scheduled.date()).order_by(_rb.Order.scheduled,_rb.Order.id).all()
            if reference.assignment_visit_id: visit=_rb.AssignmentVisit.query.filter_by(id=reference.assignment_visit_id).first()
        return _rb.render_template('admin_assignment_visits.html',reference=reference,orders=orders,visit=visit,doctors=_rb.assignable_doctors(),special_rules=__import__('assignment_distribution').policy_snapshot()['special_rules'])
    return admin_assignment_visits


def install_0208(_rb):
    @_rb.app.post('/admin/assignment-visits/<visit_id>/complete-registration')
    @_rb.login_required
    def complete_visit_registration(visit_id):
        _rb._rb_v5462_allow_registration()
        visit=_rb.AssignmentVisit.query.filter_by(id=visit_id).first_or_404()
        if _rb.db.engine.dialect.name=='postgresql':
            _rb.db.session.execute(_rb.text('SELECT pg_advisory_xact_lock(20261003, :id)'),{'id':visit.sequence_id})
        _rb.db.session.refresh(visit);visit.registration_open=False
        _rb.audit('VISIT_REGISTRATION_COMPLETE','assignment_visit',visit.id,'Explicit registration completion')
        _rb.db.session.commit()
        anchor=_rb.Order.query.filter_by(assignment_visit_id=visit.id).order_by(_rb.Order.id).first()
        if anchor and visit.assignment_mode!='MANUAL':
            _rb.offer_next_doctor(anchor,created_by=_rb.current_user().id)
        _rb.flash('Visit registration complete. Automatic visits still require examination readiness.','success')
        return _rb.redirect(_rb.url_for('schedule_calendar',date=visit.visit_date.isoformat(),branch_id=visit.branch_id))
    return complete_visit_registration


def install_0209(_rb):
    @_rb.app.get('/admin/assignment-monitor')
    @_rb.require_perm('assignment.manage')
    def admin_assignment_monitor():
        from assignment_monitor import snapshot
        return _rb.render_template('assignment_monitor.html', coordinator=False, can_manage=True, **snapshot())
    return admin_assignment_monitor


def install_0210(_rb):
    @_rb.app.get('/coordinator/assignments')
    def coordinator_assignments():
        if not _rb.current_user():
            return _rb.redirect(_rb.url_for('login', next=_rb.request.path))
        if not (_rb.has_perm('assignment.manage') or _rb.has_perm('reports.coordinate')):
            _rb.abort(403)
        from assignment_monitor import snapshot
        return _rb.render_template('assignment_monitor.html', coordinator=True, can_manage=_rb.has_perm('assignment.manage'), **snapshot())
    return coordinator_assignments


def install_0211(_rb):
    @_rb.app.route('/admin/assignment-distribution', methods=['GET', 'POST'])
    @_rb.require_perm('assignment.manage')
    def admin_assignment_distribution():
        from assignment_distribution import policy_snapshot, SELECTION_MODES
        user = _rb.current_user()
        if not user or not user.role or user.role.code.upper() not in ('SUPER_ADMIN', 'ADMIN'):
            _rb.abort(403)
        if _rb.request.method == 'POST':
            try:
                # Serialize first creation as well as updates and reject stale forms.
                if _rb.db.engine.dialect.name == 'postgresql':
                    _rb.db.session.execute(_rb.text('SELECT pg_advisory_xact_lock(20261003, 1)'))
                row = _rb.AssignmentDistributionPolicy.query.filter_by(id=1).populate_existing().with_for_update().first()
                before = policy_snapshot()
                if int(_rb.request.form.get('version_no', '-1')) != before['version_no']:
                    raise ValueError('Settings changed in another session. Reload before saving.')
                mode = _rb.request.form.get('selection_mode', '')
                if mode not in SELECTION_MODES:
                    raise ValueError('Choose a valid distribution method.')
                def number(name, low, high):
                    value = int(_rb.request.form.get(name, ''))
                    if not low <= value <= high:
                        raise ValueError(f'{name} must be between {low} and {high}.')
                    return value
                values = dict(selection_mode=mode, max_active_cases=number('max_active_cases',1,1000),
                    urgent_percent=number('urgent_percent',1,100), stat_percent=number('stat_percent',1,100),
                    reclaim_enabled=_rb.request.form.get('reclaim_enabled')=='1')
                columns = [_rb.request.form.getlist(name) for name in ('rule_modality','rule_priority','rule_min_images','rule_minutes')]
                if len(set(map(len,columns))) != 1 or not 1 <= len(columns[0]) <= 100:
                    raise ValueError('Add 1 to 100 complete deadline rules.')
                rules=[]; seen=set()
                for modality, priority, threshold, minutes in zip(*columns):
                    modality=modality.strip().upper(); priority=priority.strip().upper()
                    threshold=int(threshold); minutes=int(minutes)
                    if (not _rb.re.fullmatch(r'[A-Z0-9]{1,8}|\*',modality)
                        or priority not in ('*','ROUTINE','URGENT','STAT')
                        or not 0 <= threshold <= 1000000 or not 1 <= minutes <= 1440):
                        raise ValueError('Invalid modality, priority, image threshold or deadline (1–1440 minutes).')
                    key=(modality,priority,threshold)
                    if key in seen:
                        raise ValueError('Duplicate deadline rule. Use a different scope or image threshold.')
                    seen.add(key)
                    rules.append(dict(modality=modality,priority=priority,min_images=threshold,minutes=minutes))
                if ('*','*',0) not in seen:
                    raise ValueError('Keep a default rule: * modality, * priority, 0 images.')
                special_rules=[]
                allowed_ids={u.id for u in _rb.assignable_doctors()}
                special_codes=set()
                for index in _rb.request.form.getlist('special_index'):
                    if not index.isdigit(): raise ValueError('Invalid special rule.')
                    code=(_rb.request.form.get('special_code_'+index) or '').strip().upper()
                    label=(_rb.request.form.get('special_label_'+index) or '').strip()
                    priority=_rb.request.form.get('special_priority_'+index,'*')
                    pattern=(_rb.request.form.get('special_pattern_'+index) or '').strip()
                    enabled=_rb.request.form.get('special_enabled_'+index)=='1'
                    doctors=_rb.request.form.getlist('special_doctors_'+index,type=int)
                    if (not _rb.re.fullmatch(r'[A-Z0-9_]{1,80}',code) or code in special_codes
                        or not label or len(label)>120 or priority not in ('*','ROUTINE','URGENT','STAT')
                        or len(pattern)>180 or not set(doctors).issubset(allowed_ids)
                        or (enabled and not doctors)):
                        raise ValueError('Special rules need a unique code, label and eligible doctors before enabling.')
                    special_codes.add(code)
                    special_rules.append(dict(code=code,label=label,priority=priority,procedure_pattern=pattern,enabled=enabled,doctor_ids=doctors))
                if len(special_rules)>50: raise ValueError('Use at most 50 special rules.')
                if row is None:
                    row=_rb.AssignmentDistributionPolicy(id=1)
                    _rb.db.session.add(row)
                for name,value in values.items(): setattr(row,name,value)
                row.rules_json=_rb.json.dumps(rules,sort_keys=True)
                row.special_rules_json=_rb.json.dumps(special_rules,sort_keys=True)
                row.version_no=before['version_no']+1
                row.updated_by=user.id
                _rb.audit('ASSIGNMENT_DISTRIBUTION_SAVE','assignment_distribution_policy',1,
                      _rb.json.dumps({'before':before,'after':dict(values,rules=rules,special_rules=special_rules,version_no=row.version_no)},sort_keys=True))
                _rb.db.session.commit()
                _rb.flash('Distribution settings saved. New assignments use these deadlines.','success')
                return _rb.redirect(_rb.url_for('admin_assignment_distribution'))
            except (ValueError, TypeError) as exc:
                _rb.db.session.rollback()
                _rb.flash(str(exc) if str(exc) and not str(exc).startswith('invalid literal') else 'Enter valid numbers for limits and deadlines.','warning')
                return _rb.render_template('admin_assignment_distribution.html',policy=policy_snapshot(),doctors=_rb.assignable_doctors()),422
        return _rb.render_template('admin_assignment_distribution.html',policy=policy_snapshot(),doctors=_rb.assignable_doctors())
    return admin_assignment_distribution


def install_0531(_rb):
    @_rb.app.route('/admin/assignment',methods=['GET','POST'])
    @_rb.require_perm('users.view')
    def admin_assignment():
        doctors=_rb.assignable_doctors()

        if _rb.request.method=='POST':
            user_id=int(_rb.request.form['user_id'])
            p=_rb.DoctorAssignmentProfile.query.filter_by(user_id=user_id).first()
            if not p:
                p=_rb.DoctorAssignmentProfile(user_id=user_id)
                _rb.db.session.add(p)

            p.modalities=_rb.request.form.get('modalities','').upper()
            p.specialties=_rb.request.form.get('specialties','')
            p.branches=_rb.request.form.get('branches','')
            p.max_active_cases=_rb.request.form.get('max_active_cases',type=int) or 20
            p.auto_assign=_rb.request.form.get('auto_assign')=='1'
            p.available=_rb.request.form.get('available')=='1'
            p.priority_weight=_rb.request.form.get('priority_weight',type=int) or 100

            _rb.db.session.commit()
            _rb.flash('Doctor assignment profile saved.','success')
            return _rb.redirect(_rb.url_for('admin_assignment'))

        profiles={p.user_id:p for p in _rb.DoctorAssignmentProfile.query.all()}
        return _rb.render_template('admin_assignment.html',doctors=doctors,profiles=profiles)
    return admin_assignment


def install_0535(_rb):
    @_rb.app.route(
        '/admin/assignment-strategies',
        methods=['GET','POST']
    )
    @_rb.require_perm('assignment.manage')
    def admin_assignment_strategies():

        if _rb.request.method=='POST':

            sid=_rb.request.form.get(
                'strategy_id',
                type=int
            )

            row=(
                _rb.AssignmentStrategy.query.get(sid)
                if sid
                else _rb.AssignmentStrategy()
            )

            if sid and not row:
                _rb.abort(404)

            if not sid:
                _rb.db.session.add(row)

            before_snapshot=(
                _rb._strategy_snapshot(row)
                if sid
                else {}
            )

            row.name=(
                _rb.request.form.get('name')
                or 'Default Strategy'
            ).strip()

            # Protect the unique strategy name and return a friendly UI
            # message instead of a PostgreSQL IntegrityError.
            with _rb.db.session.no_autoflush:
                duplicate=_rb.AssignmentStrategy.query.filter(
                    _rb.AssignmentStrategy.name==row.name
                )

                if sid:
                    duplicate=duplicate.filter(
                        _rb.AssignmentStrategy.id!=sid
                    )

                duplicate=duplicate.first()

            if duplicate:
                _rb.db.session.rollback()

                _rb.flash(
                    f'Strategy name "{row.name}" already exists. '
                    'Edit the existing strategy or choose another name.',
                    'warning'
                )

                return _rb.redirect(
                    _rb.url_for('admin_assignment_strategies')
                )

            row.enabled=(
                _rb.request.form.get('enabled')=='1'
            )

            row.priority=(
                _rb.request.form.get(
                    'priority',
                    type=int
                )
                or 100
            )

            row.branch_id=_rb.request.form.get(
                'branch_id',
                type=int
            )

            row.modality=(
                _rb.request.form.get('modality')
                or ''
            ).strip().upper()

            row.procedure_pattern=(
                _rb.request.form.get(
                    'procedure_pattern'
                )
                or ''
            ).strip()

            row.assignment_mode=(
                _rb.request.form.get(
                    'assignment_mode'
                )
                or 'OFFER_ACCEPT'
            ).upper()

            row.fallback_mode=(
                _rb.request.form.get(
                    'fallback_mode'
                )
                or 'OPEN_POOL'
            ).upper()

            row.pacs_missing_action=_rb._strategy_action(
                _rb.request.form.get(
                    'pacs_missing_action'
                ),
                'BLOCK'
            )

            row.images_incomplete_action=_rb._strategy_action(
                _rb.request.form.get(
                    'images_incomplete_action'
                ),
                'BLOCK'
            )

            row.documents_missing_action=_rb._strategy_action(
                _rb.request.form.get(
                    'documents_missing_action'
                ),
                'WARN'
            )

            row.notes_missing_action=_rb._strategy_action(
                _rb.request.form.get(
                    'notes_missing_action'
                ),
                'WARN'
            )

            row.attachments_missing_action=_rb._strategy_action(
                _rb.request.form.get(
                    'attachments_missing_action'
                ),
                'WARN'
            )

            row.history_missing_action=_rb._strategy_action(
                _rb.request.form.get(
                    'history_missing_action'
                ),
                'IGNORE'
            )

            row.require_modality_match=(
                _rb.request.form.get(
                    'require_modality_match'
                )=='1'
            )

            row.require_branch_match=(
                _rb.request.form.get(
                    'require_branch_match'
                )=='1'
            )

            row.require_online=(
                _rb.request.form.get(
                    'require_online'
                )=='1'
            )

            row.prefer_online=(
                _rb.request.form.get(
                    'prefer_online'
                )=='1'
            )

            row.min_images=(
                _rb.request.form.get(
                    'min_images',
                    type=int
                )
                or 0
            )

            row.stable_seconds=(
                _rb.request.form.get(
                    'stable_seconds',
                    type=int
                )
                or 120
            )

            row.routine_timeout_seconds=(
                _rb.request.form.get(
                    'routine_timeout_seconds',
                    type=int
                )
                or 300
            )

            row.urgent_timeout_seconds=(
                _rb.request.form.get(
                    'urgent_timeout_seconds',
                    type=int
                )
                or 120
            )

            row.stat_timeout_seconds=(
                _rb.request.form.get(
                    'stat_timeout_seconds',
                    type=int
                )
                or 60
            )

            row.busy_snooze_minutes=(
                _rb.request.form.get(
                    'busy_snooze_minutes',
                    type=int
                )
                or 30
            )

            row.max_offer_attempts=(
                _rb.request.form.get(
                    'max_offer_attempts',
                    type=int
                )
                or 5
            )

            row.version_no=(
                int(row.version_no or 0)+1
            )

            u=_rb.current_user()
            row.updated_by=u.id if u else None

            _rb.db.session.flush()

            after_snapshot=_rb._strategy_snapshot(row)

            manual_note=(
                _rb.request.form.get('change_note')
                or ''
            ).strip()

            auto_note=_rb._strategy_change_summary(
                before_snapshot,
                after_snapshot
            )

            if len(manual_note)>500:
                _rb.db.session.rollback()
                _rb.flash('Change note must be 500 characters or fewer.','warning')
                return _rb.redirect(_rb.url_for('admin_assignment_strategies'))
            final_note=manual_note or auto_note

            _rb.db.session.add(
                _rb.AssignmentStrategyVersion(
                    strategy_id=row.id,
                    version_no=row.version_no,
                    snapshot_json=_rb.json.dumps(
                        after_snapshot,
                        ensure_ascii=False,
                        default=str
                    ),
                    changed_by=_rb.current_user().id,
                    change_note=final_note
                )
            )

            _rb.audit(
                'ASSIGNMENT_STRATEGY_SAVE',
                'assignment_strategy',
                row.id,
                f'{row.name} v{row.version_no}'
            )

            _rb.db.session.commit()

            _rb.flash(
                'Assignment strategy saved.',
                'success'
            )

            return _rb.redirect(
                _rb.url_for(
                    'admin_assignment_strategies'
                )
            )

        rows=_rb.AssignmentStrategy.query.order_by(
            _rb.AssignmentStrategy.priority,
            _rb.AssignmentStrategy.id
        ).all()

        branches=_rb.Branch.query.filter_by(
            active=True
        ).order_by(
            _rb.Branch.name
        ).all()

        return _rb.render_template(
            'admin_assignment_strategies.html',
            rows=rows,
            branches=branches
        )
    return admin_assignment_strategies


def install_0537(_rb):
    @_rb.app.post(
        '/admin/assignment-strategies/simulate'
    )
    @_rb.require_perm('assignment.manage')
    def admin_assignment_strategy_simulate():


        order_id=_rb.request.form.get(
            'order_id',
            type=int
        )

        order=_rb.Order.query.get_or_404(
            order_id
        )

        strategy=_rb.assignment_strategy_for_order(
            order
        )

        decision=_rb.assignment_readiness_decision(
            order
        )

        policy=_rb.assignment_offer_policy()

        doctor_diagnostics=_rb.assignment_candidate_diagnostics(
            order,
            policy
        )

        doctors=[]

        if (
            policy
            and decision.get('allowed')
        ):

            doctors=_rb.assignment_candidate_users(
                order,
                policy
            )

        return _rb.jsonify({
            'order':order.id,
            'accession':order.accession,
            'strategy':(
                strategy.name
                if strategy
                else 'LEGACY_POLICY'
            ),
            'mode':(
                strategy.assignment_mode
                if strategy
                else 'OFFER_ACCEPT'
            ),
            'allowed':decision.get(
                'allowed'
            ),
            'action':decision.get(
                'action'
            ),
            'blockers':decision.get(
                'blockers'
            ),
            'warnings':decision.get(
                'warnings'
            ),
            'doctor_diagnostics':doctor_diagnostics,

            'eligible_doctors':[
                {
                    'id':d.id,
                    'username':d.username,
                    'name':(
                        d.full_name
                        or d.username
                    )
                }
                for d in doctors
            ]
        })
    return admin_assignment_strategy_simulate


def install_0538(_rb):
    @_rb.app.post('/admin/assignment-strategies/<int:strategy_id>/toggle')
    @_rb.require_perm('assignment.manage')
    def admin_assignment_strategy_toggle(strategy_id):

        row=_rb.AssignmentStrategy.query.get_or_404(strategy_id)

        row.enabled=not bool(row.enabled)
        row.version_no=int(row.version_no or 0)+1
        row.updated_by=_rb.current_user().id

        _rb.db.session.add(
            _rb.AssignmentStrategyVersion(
                strategy_id=row.id,
                version_no=row.version_no,
                snapshot_json=_rb.json.dumps(
                    _rb._strategy_snapshot(row),
                    ensure_ascii=False,
                    default=str
                ),
                changed_by=_rb.current_user().id,
                change_note='Enabled/Disabled from Strategy Center'
            )
        )

        _rb.audit(
            'ASSIGNMENT_STRATEGY_TOGGLE',
            'assignment_strategy',
            row.id,
            f'enabled={row.enabled}'
        )

        _rb.db.session.commit()

        _rb.flash(
            f'Strategy {"enabled" if row.enabled else "disabled"}.',
            'success'
        )

        return _rb.redirect(
            _rb.url_for('admin_assignment_strategies')
        )
    return admin_assignment_strategy_toggle


def install_0539(_rb):
    @_rb.app.route(
        '/admin/assignment-strategies/simulate-ui',
        methods=['GET','POST']
    )
    @_rb.require_perm('assignment.manage')
    def admin_assignment_strategy_simulate_ui():

        order_id=(
            _rb.request.form.get('order_id',type=int)
            if _rb.request.method=='POST'
            else _rb.request.args.get('order_id',type=int)
        )

        if not order_id:
            _rb.flash('Order ID is required.','warning')
            return _rb.redirect(
                _rb.url_for('admin_assignment_strategies')
            )

        order=_rb.Order.query.get_or_404(order_id)

        strategy=_rb.assignment_strategy_for_order(
            order
        )

        decision=_rb.assignment_readiness_decision(
            order
        )

        policy=_rb.assignment_offer_policy()

        diagnostics=_rb.assignment_candidate_diagnostics(
            order,
            policy
        )

        eligible=[
            row
            for row in diagnostics
            if row.get('eligible')
        ]

        excluded=[
            row
            for row in diagnostics
            if not row.get('eligible')
        ]

        return _rb.render_template(
            'admin_assignment_strategy_simulator.html',

            order=order,
            strategy=strategy,
            decision=decision,

            diagnostics=diagnostics,
            eligible=eligible,
            excluded=excluded,

            eligible_count=len(eligible),
            excluded_count=len(excluded),

            policy=policy
        )
    return admin_assignment_strategy_simulate_ui


def install_0540(_rb):
    @_rb.app.post('/admin/assignment-strategies/<int:strategy_id>/clone')
    @_rb.require_perm('assignment.manage')
    def admin_assignment_strategy_clone(strategy_id):

        src=_rb.AssignmentStrategy.query.get_or_404(strategy_id)

        base_name=f'{src.name} Copy'
        name=base_name
        suffix=2

        while _rb.AssignmentStrategy.query.filter_by(name=name).first():
            name=f'{base_name} {suffix}'
            suffix+=1

        clone=_rb.AssignmentStrategy(
            name=name,
            enabled=False,
            priority=src.priority,
            branch_id=src.branch_id,
            modality=src.modality,
            procedure_pattern=src.procedure_pattern,

            assignment_mode=src.assignment_mode,
            fallback_mode=src.fallback_mode,

            pacs_missing_action=src.pacs_missing_action,
            images_incomplete_action=src.images_incomplete_action,
            documents_missing_action=src.documents_missing_action,
            notes_missing_action=src.notes_missing_action,
            attachments_missing_action=src.attachments_missing_action,
            history_missing_action=src.history_missing_action,

            require_modality_match=src.require_modality_match,
            require_branch_match=src.require_branch_match,
            require_online=src.require_online,
            prefer_online=src.prefer_online,

            min_images=src.min_images,
            min_completion_percent=src.min_completion_percent,
            stable_seconds=src.stable_seconds,

            routine_timeout_seconds=src.routine_timeout_seconds,
            urgent_timeout_seconds=src.urgent_timeout_seconds,
            stat_timeout_seconds=src.stat_timeout_seconds,

            busy_snooze_minutes=src.busy_snooze_minutes,
            max_offer_attempts=src.max_offer_attempts,

            active_from=src.active_from,
            active_to=src.active_to,

            version_no=1,
            updated_by=_rb.current_user().id
        )

        _rb.db.session.add(clone)
        _rb.db.session.flush()

        _rb.db.session.add(
            _rb.AssignmentStrategyVersion(
                strategy_id=clone.id,
                version_no=1,
                snapshot_json=_rb.json.dumps(
                    _rb._strategy_snapshot(clone),
                    ensure_ascii=False,
                    default=str
                ),
                changed_by=_rb.current_user().id,
                change_note=f'Cloned from strategy #{src.id}'
            )
        )

        _rb.audit(
            'ASSIGNMENT_STRATEGY_CLONE',
            'assignment_strategy',
            clone.id,
            f'cloned_from={src.id}'
        )

        _rb.db.session.commit()

        _rb.flash(
            f'Strategy cloned as "{clone.name}". It is disabled until reviewed.',
            'success'
        )

        return _rb.redirect(
            _rb.url_for('admin_assignment_strategies')
        )
    return admin_assignment_strategy_clone


def install_0541(_rb):
    @_rb.app.get('/admin/assignment-strategies/<int:strategy_id>/history')
    @_rb.require_perm('assignment.manage')
    def admin_assignment_strategy_history(strategy_id):

        row=_rb.AssignmentStrategy.query.get_or_404(strategy_id)

        versions=_rb.AssignmentStrategyVersion.query.filter_by(
            strategy_id=row.id
        ).order_by(
            _rb.AssignmentStrategyVersion.version_no.desc(),
            _rb.AssignmentStrategyVersion.id.desc()
        ).all()

        return _rb.render_template(
            'admin_assignment_strategy_history.html',
            strategy=row,
            versions=versions
        )
    return admin_assignment_strategy_history


def install_0542(_rb):
    @_rb.app.post('/admin/assignment-strategies/<int:strategy_id>/rollback/<int:version_id>')
    @_rb.require_perm('assignment.manage')
    def admin_assignment_strategy_rollback(strategy_id,version_id):

        row=_rb.AssignmentStrategy.query.get_or_404(strategy_id)

        version=_rb.AssignmentStrategyVersion.query.filter_by(
            id=version_id,
            strategy_id=row.id
        ).first_or_404()

        try:
            snap=_rb.json.loads(version.snapshot_json or '{}')
        except Exception:
            snap={}

        allowed_fields=(
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

        for field in allowed_fields:
            if field in snap:
                setattr(row,field,snap[field])

        row.version_no=int(row.version_no or 0)+1
        row.updated_by=_rb.current_user().id

        _rb.db.session.flush()

        _rb.db.session.add(
            _rb.AssignmentStrategyVersion(
                strategy_id=row.id,
                version_no=row.version_no,
                snapshot_json=_rb.json.dumps(
                    _rb._strategy_snapshot(row),
                    ensure_ascii=False,
                    default=str
                ),
                changed_by=_rb.current_user().id,
                change_note=f'Rollback to version {version.version_no}'
            )
        )

        _rb.audit(
            'ASSIGNMENT_STRATEGY_ROLLBACK',
            'assignment_strategy',
            row.id,
            f'rollback_to={version.version_no}; new_version={row.version_no}'
        )

        _rb.db.session.commit()

        _rb.flash(
            f'Strategy rolled back to version {version.version_no}. '
            f'Current version is now {row.version_no}.',
            'success'
        )

        return _rb.redirect(
            _rb.url_for(
                'admin_assignment_strategy_history',
                strategy_id=row.id
            )
        )
    return admin_assignment_strategy_rollback


def install_0543(_rb):
    @_rb.app.route('/orders/<int:order_id>/assign',methods=['GET','POST'])
    @_rb.require_perm('assignment.manage')
    def assign_case(order_id):
        order=_rb.Order.query.get_or_404(order_id)
        import sys
        from coordinator_bulk_assignment import actor, in_scope
        module=sys.modules[_rb.__name__]
        user=actor(module)
        if not in_scope(module,user,order):
            _rb.abort(403)
        if _rb.request.method == 'GET':
            # Review links must never perform assignment; use the scoped preview workflow.
            return _rb.redirect(_rb.url_for('coordinator_manual_assignment', view='all', q=order.accession))
        doctor_user_id=_rb.request.form.get('doctor_user_id',type=int)
        mode=_rb.request.form.get('mode','manual')

        readiness_decision=_rb.assignment_readiness_decision(order)
        if not readiness_decision['allowed']:
            reasons=(readiness_decision.get('blockers') or
                     readiness_decision.get('coordinator') or
                     ['CASE_NOT_READY'])
            _rb.flash(
                'Assignment blocked: '+
                ', '.join(str(x).replace('_',' ') for x in reasons)+
                '. Resolve the readiness items first.',
                'warning'
            )
            return _rb.redirect(_rb.request.referrer or _rb.url_for('unassigned_cases'))

        if mode=='auto':
            offer,status=_rb.offer_next_doctor(order,created_by=_rb.current_user().id if _rb.current_user() else None)
            if offer:
                _rb.flash(f'Assignment offer sent to {offer.doctor.full_name or offer.doctor.username}.','success')
            elif status=='CASE_NOT_READY':
                _rb.flash('Assignment blocked by readiness rules. Review PACS/images/documents/notes.','warning')
            elif status=='NO_CANDIDATE':
                _rb.flash('No eligible doctor matches the current assignment rules.','warning')
            else:
                _rb.flash(f'Assignment offer not started: {status}.','warning')
        else:
            if not doctor_user_id:
                _rb.flash('Choose a doctor first.','danger')
                return _rb.redirect(_rb.request.referrer or _rb.url_for('doctor_workspace'))
            try:
                doctor=_rb.manual_assign_order(
                    order,
                    doctor_user_id,
                    assigned_by=_rb.current_user().id if _rb.current_user() else None,
                    notes=_rb.request.form.get('notes','')
                )
                _rb.db.session.commit()
            except Exception as exc:
                _rb.db.session.rollback()
                code=getattr(exc,'code',type(exc).__name__)
                _rb.flash('Assignment failed: '+str(code).replace('_',' ')+'.','danger')
                return _rb.redirect(_rb.request.referrer or _rb.url_for('doctor_workspace'))
            _rb.flash(f'Case assigned to {doctor.full_name or doctor.username}.','success')

        return _rb.redirect(_rb.request.referrer or _rb.url_for('doctor_workspace'))
    return assign_case


def install_0685(_rb):
    @_rb.app.route('/admin/assignment-offers',methods=['GET','POST'])
    @_rb.require_perm('users.view')
    def admin_assignment_offers():
        row=_rb.assignment_offer_policy()
        if _rb.request.method=='POST':
            if not row:
                row=_rb.AssignmentOfferPolicy();_rb.db.session.add(row)
            row.enabled=_rb.request.form.get('enabled')=='1'
            row.mode=(_rb.request.form.get('mode') or 'ONLINE_PREFERRED').upper()
            row.routine_timeout_seconds=_rb.request.form.get('routine_timeout_seconds',type=int) or 300
            row.urgent_timeout_seconds=_rb.request.form.get('urgent_timeout_seconds',type=int) or 120
            row.stat_timeout_seconds=_rb.request.form.get('stat_timeout_seconds',type=int) or 60
            row.busy_snooze_minutes=_rb.request.form.get('busy_snooze_minutes',type=int) or 30
            row.max_offer_attempts=_rb.request.form.get('max_offer_attempts',type=int) or 5
            row.notification_channels=(_rb.request.form.get('notification_channels') or 'INAPP').upper()
            row.updated_by=_rb.current_user().id
            _rb.db.session.commit()
            return _rb.redirect(_rb.url_for('admin_assignment_offers'))
        return _rb.render_template('admin_assignment_offers.html',row=row)
    return admin_assignment_offers


def install_0688(_rb):
    @_rb.app.get('/assignment/open-pool')
    @_rb.login_required
    def open_pool_cases():

        rows=[]

        for order in _rb.Order.query.filter(
            _rb.Order.assigned_doctor_id.is_(None)
        ).order_by(
            _rb.Order.id.desc()
        ).limit(300).all():

            if not _rb.order_is_open_pool(order):
                continue

            if not _rb._open_pool_visible_to_doctor(
                order,
                _rb.current_user()
            ):
                continue

            decision=_rb.assignment_readiness_decision(order)

            if not decision.get('allowed'):
                continue

            rows.append(
                (
                    order,
                    decision
                )
            )

        return _rb.render_template(
            'open_pool_cases.html',
            rows=rows
        )
    return open_pool_cases


def install_0689(_rb):
    @_rb.app.post('/orders/<int:order_id>/assign-to-me')
    @_rb.login_required
    def assign_case_to_me(order_id):

        order=_rb.Order.query.get_or_404(order_id)

        if order.assigned_doctor_id:
            _rb.flash('Case is already assigned.','warning')
            return _rb.redirect(
                _rb.url_for('open_pool_cases')
            )

        if not _rb.order_is_open_pool(order):
            _rb.abort(403)

        if not _rb._open_pool_visible_to_doctor(
            order,
            _rb.current_user()
        ):
            _rb.abort(403)

        decision=_rb.assignment_readiness_decision(
            order
        )

        if not decision.get('allowed'):
            _rb.flash(
                'Case is no longer eligible for assignment.',
                'warning'
            )
            return _rb.redirect(
                _rb.url_for('open_pool_cases')
            )

        try:
            doctor=_rb.manual_assign_order(
                order,
                _rb.current_user().id,
                assigned_by=_rb.current_user().id,
                notes='Doctor assigned case from Open Pool',
                assignment_type='OPEN_POOL',
                require_unassigned=True,
            )
        except Exception as exc:
            _rb.db.session.rollback()
            code=getattr(exc,'code',type(exc).__name__)
            _rb.flash('Case cannot be taken: '+str(code).replace('_',' ')+'.','warning')
            return _rb.redirect(_rb.url_for('open_pool_cases'))

        _rb.db.session.add(
            _rb.AssignmentEscalationEvent(
                order_id=order.id,
                event_type='OPEN_POOL_TAKEN',
                details=f'doctor={doctor.id}',
                created_by=_rb.current_user().id
            )
        )

        _rb.audit(
            'OPEN_POOL_ASSIGN_TO_ME',
            'order',
            order.id,
            f'doctor={doctor.id}'
        )

        _rb.db.session.commit()

        _rb.flash(
            'Case assigned to you.',
            'success'
        )

        return _rb.redirect(
            _rb.url_for(
                'order_detail',
                order_id=order.id
            )
        )
    return assign_case_to_me


def install_0690(_rb):
    @_rb.app.get('/assignment/offers')
    @_rb.login_required
    def my_assignment_offers():
        _rb.expire_assignment_offers()
        rows=_rb.AssignmentOffer.query.filter_by(doctor_user_id=_rb.current_user().id).order_by(_rb.AssignmentOffer.offered_at.desc()).limit(100).all()
        state=_rb.doctor_availability(_rb.current_user())
        return _rb.render_template('my_assignment_offers.html',rows=rows,state=state)
    return my_assignment_offers


def install_0691(_rb):
    @_rb.app.post('/assignment/availability')
    @_rb.login_required
    def assignment_availability_update():
        state=(_rb.request.form.get('state') or 'AVAILABLE').upper()
        if state not in ('AVAILABLE','BUSY','AWAY','OFFLINE'): _rb.abort(400)
        row=_rb.doctor_availability(_rb.current_user())
        row.state=state;row.last_seen_at=_rb.datetime.utcnow()
        if state=='BUSY':
            mins=_rb.request.form.get('busy_minutes',type=int) or 30
            row.busy_until=_rb.datetime.utcnow()+_rb.timedelta(minutes=max(5,mins))
        elif state!='BUSY':
            row.busy_until=None
        _rb.db.session.commit()
        return _rb.redirect(_rb.request.referrer or _rb.url_for('my_assignment_offers'))
    return assignment_availability_update


def install_0692(_rb):
    @_rb.app.post('/assignment/offers/<int:offer_id>/respond')
    @_rb.login_required
    def assignment_offer_respond(offer_id):
        workspace=_rb.request.headers.get('X-RadBridge-Workspace')=='doctor'
        if workspace and (not _rb.has_perm('reports.view') or not _rb.doctor_workspace_user(_rb.current_user())):
            _rb.abort(403)
        if workspace and (_rb.request.form.get('action') or '').upper() not in ('ACCEPT','BUSY','REJECT'):
            return _rb.jsonify(ok=False,error='INVALID_ACTION'),400
        if workspace:
            owned_offer=_rb.AssignmentOffer.query.get_or_404(offer_id)
            if owned_offer.doctor_user_id!=_rb.current_user().id:
                _rb.abort(403)
        _rb.expire_assignment_offers()
        row=_rb.AssignmentOffer.query.get_or_404(offer_id)
        if row.doctor_user_id!=_rb.current_user().id and not _rb.has_perm('*'):
            _rb.abort(403)
        if row.status!='PENDING':
            if workspace:
                return _rb.jsonify(ok=False,error='OFFER_NO_LONGER_PENDING'),409
            _rb.flash('Offer is no longer pending.','warning')
            return _rb.redirect(_rb.url_for('my_assignment_offers'))
        action=(_rb.request.form.get('action') or '').upper()
        note=(_rb.request.form.get('note') or '').strip()
        now=_rb.datetime.utcnow()
        if now>row.expires_at:
            row.status='TIMEOUT';row.responded_at=now;_rb.db.session.commit()
            _rb.offer_next_doctor(row.order,created_by=_rb.current_user().id)
            if workspace:
                return _rb.jsonify(ok=False,error='OFFER_EXPIRED'),409
            return _rb.redirect(_rb.url_for('my_assignment_offers'))
        if action=='ACCEPT':
            from case_assignment_service import accept_offer_atomically

            try:
                result,row=accept_offer_atomically(
                    db=_rb.db,
                    Order=_rb.Order,
                    User=_rb.User,
                    CaseAssignment=_rb.CaseAssignment,
                    Report=_rb.Report,
                    AssignmentOffer=_rb.AssignmentOffer,
                    offer_id=row.id,
                    actor_user_id=_rb.current_user().id,
                    note=note,
                    now=now,
                )
            except Exception as exc:
                _rb.db.session.rollback()
                code=getattr(exc,'code',type(exc).__name__)
                if workspace:
                    return _rb.jsonify(ok=False,error='ACCEPT_BLOCKED'),409
                _rb.flash('Offer cannot be accepted: '+str(code).replace('_',' ')+'.','warning')
                return _rb.redirect(_rb.url_for('my_assignment_offers'))

            _rb.db.session.add(
                _rb.AssignmentEscalationEvent(
                    order_id=row.order_id,
                    offer_id=row.id,
                    event_type='ACCEPTED',
                    details=f'doctor={result.doctor.id}',
                    created_by=_rb.current_user().id
                )
            )
        elif action in ('BUSY','REJECT'):
            row.status='BUSY' if action=='BUSY' else 'REJECTED'
            row.responded_at=now;row.response_note=note
            if action=='BUSY':
                st=_rb.doctor_availability(row.doctor)
                policy=_rb.assignment_offer_policy()
                strategy=_rb.assignment_strategy_for_order(row.order)

                busy_minutes=int(
                    strategy.busy_snooze_minutes
                    if strategy and strategy.busy_snooze_minutes
                    else policy.busy_snooze_minutes or 30
                )

                st.state='BUSY'
                st.busy_until=now+_rb.timedelta(minutes=busy_minutes)
            _rb.db.session.add(_rb.AssignmentEscalationEvent(order_id=row.order_id,offer_id=row.id,event_type=row.status,
                details=f'doctor={row.doctor_user_id};note={note}',created_by=_rb.current_user().id))
            _rb.db.session.flush()
            _rb.offer_next_doctor(row.order,created_by=_rb.current_user().id)
        else:
            _rb.abort(400)
        _rb.db.session.commit()

        if workspace:
            return _rb.jsonify(ok=True,action=action,order_id=row.order_id,
                open_url=_rb.url_for('doctor_workspace_open',order_id=row.order_id) if action=='ACCEPT' else None)

        # RB_ASSIGNMENT_ACCEPT_TO_OHIF_V1
        # Open the integrated image/reporting workspace only after the
        # atomic acceptance and audit transaction has committed.
        if action=='ACCEPT':
            viewer_url=(
                _rb.ohif_url_for_order(row.order)
                or _rb.case_pacs_url(row.order)
            )

            if viewer_url:
                return _rb.redirect(viewer_url)

        return _rb.redirect(_rb.url_for('my_assignment_offers'))
    return assignment_offer_respond


def install_0693(_rb):
    @_rb.app.post('/orders/<int:order_id>/assignment-offer/start')
    @_rb.require_perm('assignment.manage')
    def assignment_offer_start(order_id):
        order=_rb.Order.query.get_or_404(order_id)
        pending=_rb.AssignmentOffer.query.filter_by(order_id=order.id,status='PENDING').first()
        if pending:
            _rb.flash('A pending offer already exists.','warning')
            return _rb.redirect(_rb.request.referrer or _rb.url_for('admin_assignment'))
        offer,status=_rb.offer_next_doctor(order,created_by=_rb.current_user().id)
        _rb.flash('Assignment offer started.' if offer else f'Assignment offer not started: {status}',
              'success' if offer else 'warning')
        return _rb.redirect(_rb.request.referrer or _rb.url_for('admin_assignment'))
    return assignment_offer_start


def install_0694(_rb):
    @_rb.app.post('/assignment/offers/expire-now')
    @_rb.require_perm('assignment.manage')
    def assignment_offers_expire_now():
        touched=_rb.expire_assignment_offers()
        _rb.flash(f'Expired {len(touched)} offer(s).','success')
        return _rb.redirect(_rb.request.referrer or _rb.url_for('admin_assignment_offers'))
    return assignment_offers_expire_now


def install_0720(_rb):
    @_rb.app.route(
        '/admin/tat-policies',
        methods=['GET','POST']
    )
    @_rb.require_perm('assignment.manage')
    def admin_tat_policies():

        priorities = (
            'STAT',
            'URGENT',
            'ROUTINE',
        )

        if _rb.request.method == 'POST':

            action = (
                _rb.request.form.get('action')
                or 'SAVE'
            ).strip().upper()

            row_id = _rb.request.form.get(
                'policy_id',
                type=int
            )

            row = (
                _rb.db.session.get(
                    _rb.TATPolicy,
                    row_id
                )
                if row_id
                else None
            )

            if action == 'DISABLE':

                if not row:
                    _rb.abort(404)

                row.active = False

                _rb.audit(
                    'TAT_POLICY_DISABLED',
                    'tat_policy',
                    row.id,
                    (
                        f'priority={row.priority};'
                        f'modality={row.modality}'
                    )
                )

                _rb.db.session.commit()

                _rb.flash(
                    'SLA / TAT policy disabled.',
                    'success'
                )

                return _rb.redirect(
                    _rb.url_for(
                        'admin_tat_policies'
                    )
                )

            priority = (
                _rb.request.form.get('priority')
                or ''
            ).strip().upper()

            modality = (
                _rb.request.form.get('modality')
                or '*'
            ).strip().upper()

            if not modality:
                modality = '*'

            if priority not in priorities:
                _rb.flash(
                    'Invalid priority.',
                    'danger'
                )
                return _rb.redirect(
                    _rb.url_for(
                        'admin_tat_policies'
                    )
                )

            def required_nonnegative_int(name):
                value = _rb.request.form.get(
                    name,
                    type=int
                )

                if value is None or value < 0:
                    raise ValueError(name)

                return value

            try:
                ready_to_assign_min = (
                    required_nonnegative_int(
                        'ready_to_assign_min'
                    )
                )

                assign_to_accept_min = (
                    required_nonnegative_int(
                        'assign_to_accept_min'
                    )
                )

                accept_to_final_min = (
                    required_nonnegative_int(
                        'accept_to_final_min'
                    )
                )

                total_tat_min = (
                    required_nonnegative_int(
                        'total_tat_min'
                    )
                )

            except ValueError:
                _rb.flash(
                    'All SLA values must be zero or positive minutes.',
                    'danger'
                )
                return _rb.redirect(
                    _rb.url_for(
                        'admin_tat_policies'
                    )
                )

            active = (
                _rb.request.form.get('active')
                == '1'
            )

            duplicate_query = (
                _rb.TATPolicy.query
                .filter_by(
                    priority=priority,
                    modality=modality,
                    active=True,
                )
            )

            if row:
                duplicate_query = (
                    duplicate_query
                    .filter(
                        _rb.TATPolicy.id != row.id
                    )
                )

            duplicate = (
                duplicate_query
                .order_by(
                    _rb.TATPolicy.id.asc()
                )
                .first()
            )

            if active and duplicate:
                _rb.flash(
                    (
                        'An active SLA / TAT policy already exists '
                        f'for {priority} + {modality}.'
                    ),
                    'danger'
                )

                return _rb.redirect(
                    _rb.url_for(
                        'admin_tat_policies'
                    )
                )

            created = row is None

            if row is None:
                row = _rb.TATPolicy()
                _rb.db.session.add(row)

            row.priority = priority
            row.modality = modality

            row.ready_to_assign_min = (
                ready_to_assign_min
            )

            row.assign_to_accept_min = (
                assign_to_accept_min
            )

            row.accept_to_final_min = (
                accept_to_final_min
            )

            row.total_tat_min = (
                total_tat_min
            )

            row.active = active

            _rb.db.session.flush()

            _rb.audit(
                (
                    'TAT_POLICY_CREATED'
                    if created
                    else 'TAT_POLICY_UPDATED'
                ),
                'tat_policy',
                row.id,
                (
                    f'priority={row.priority};'
                    f'modality={row.modality};'
                    f'ready_to_assign_min={row.ready_to_assign_min};'
                    f'assign_to_accept_min={row.assign_to_accept_min};'
                    f'accept_to_final_min={row.accept_to_final_min};'
                    f'total_tat_min={row.total_tat_min};'
                    f'active={row.active}'
                )
            )

            _rb.db.session.commit()

            _rb.flash(
                (
                    'SLA / TAT policy created.'
                    if created
                    else 'SLA / TAT policy updated.'
                ),
                'success'
            )

            return _rb.redirect(
                _rb.url_for(
                    'admin_tat_policies'
                )
            )

        rows = (
            _rb.TATPolicy.query
            .order_by(
                _rb.TATPolicy.priority,
                _rb.TATPolicy.modality,
                _rb.TATPolicy.id
            )
            .all()
        )

        modalities = sorted({
            str(x[0]).strip().upper()
            for x in (
                _rb.db.session.query(
                    _rb.Order.modality
                )
                .filter(
                    _rb.Order.modality.isnot(None)
                )
                .distinct()
                .all()
            )
            if x[0]
        })

        return _rb.render_template(
            'admin_tat_policies.html',
            rows=rows,
            priorities=priorities,
            modalities=modalities,
        )
    return admin_tat_policies


def install_0741(_rb):
    @_rb.app.get('/operations/assignment-dashboard')
    @_rb.require_perm('orders.view')
    def assignment_dashboard():
        all_rows=_rb.assignment_report_rows()
        stats={
          'ready_unassigned':sum(1 for x in all_rows if x['process_state']=='READY_UNASSIGNED'),
          'pending_offers':sum(1 for x in all_rows if x['process_state']=='PENDING_OFFER'),
          'assigned':sum(1 for x in all_rows if x['process_state']=='ASSIGNED'),
          'returned':sum(1 for x in all_rows if x['return_open']),
          'blocked':sum(1 for x in all_rows if x['process_state']=='BLOCKED'),
          'overdue':sum(1 for x in all_rows if x['tat']['overdue']),
          'finalized':sum(1 for x in all_rows if x['process_state']=='FINALIZED')
        }

        state=(_rb.request.args.get('state') or 'ALL').strip().upper()
        owner=(_rb.request.args.get('owner') or 'ALL').strip().upper()

        allowed_states={
          'ALL','READY_UNASSIGNED','PENDING_OFFER','ASSIGNED',
          'RETURNED','BLOCKED','WAITING_READINESS','FINALIZED','OVERDUE'
        }
        if state not in allowed_states:
            state='ALL'

        rows=all_rows
        if state=='OVERDUE':
            rows=[x for x in rows if x['tat']['overdue']]
        elif state!='ALL':
            rows=[x for x in rows if x['process_state']==state]

        owners=sorted({
            str(x['process_owner'] or '').upper()
            for x in all_rows if x['process_owner']
        })
        if owner!='ALL':
            rows=[
                x for x in rows
                if str(x['process_owner'] or '').upper()==owner
            ]

        return _rb.render_template(
            'assignment_dashboard.html',
            rows=rows[:200],
            stats=stats,
            selected_state=state,
            selected_owner=owner,
            owners=owners
        )
    return assignment_dashboard


def install_0847(_rb):
    @_rb.app.route('/admin/external-intake',methods=['GET','POST'])
    @_rb.require_perm('assignment.manage')
    def admin_external_intake():
        setting=_rb.external_reporting_setting()
        if _rb.request.method=='POST':
            action=(_rb.request.form.get('action') or '').upper()
            if action=='MASTER':
                setting.enabled=_rb.request.form.get('enabled')=='1'
                setting.updated_by=_rb.current_user().id
                _rb.audit('EXTERNAL_REPORTING_MASTER','external_reporting_setting',setting.id,
                      f'enabled={setting.enabled}')
            elif action=='CENTER':
                code=_rb.re.sub(r'[^A-Z0-9_-]','',(_rb.request.form.get('code') or '').upper())[:40]
                ae=(_rb.request.form.get('ae_title') or '').strip().upper()[:80]
                name=(_rb.request.form.get('name') or '').strip()[:160]
                if not code or not ae or not name: _rb.abort(400)
                center=_rb.ExternalReportingCenter.query.filter_by(code=code).first()
                if not center:
                    center=_rb.ExternalReportingCenter(code=code,name=name,ae_title=ae,created_by=_rb.current_user().id)
                    _rb.db.session.add(center)
                center.name=name;center.ae_title=ae
                center.receiving_enabled=_rb.request.form.get('receiving_enabled')=='1'
                center.assignment_enabled=_rb.request.form.get('assignment_enabled')=='1'
                center.auto_queue=False # Phase one remains explicit-admin queue only.
                center.required_documents=_rb.request.form.get('required_documents')=='1'
                center.billing_enabled=_rb.request.form.get('billing_enabled')=='1'
                center.billing_contract_id=_rb.request.form.get('billing_contract_id',type=int) or None
                try:
                    center.default_report_fee=max(0.0,float(_rb.request.form.get('default_report_fee') or 0))
                except (TypeError,ValueError):
                    _rb.abort(400)
                if center.billing_enabled:
                    contract=_rb.Contract.query.filter_by(id=center.billing_contract_id,active=True).first()
                    if not contract: _rb.abort(400)
                center.default_priority=(_rb.request.form.get('default_priority') or 'ROUTINE').upper()
                center.active=_rb.request.form.get('active')=='1'
                _rb.db.session.flush()
                wanted={int(x) for x in _rb.request.form.getlist('doctor_ids') if x.isdigit()}
                existing={x.doctor_user_id:x for x in _rb.ExternalCenterDoctor.query.filter_by(center_id=center.id).all()}
                for doctor_id,item in existing.items(): item.active=doctor_id in wanted
                for doctor_id in wanted-existing.keys():
                    _rb.db.session.add(_rb.ExternalCenterDoctor(center_id=center.id,doctor_user_id=doctor_id,active=True))
                _rb.audit('EXTERNAL_CENTER_SAVE','external_reporting_center',center.id,
                      f'code={code};receiving={center.receiving_enabled};assignment={center.assignment_enabled};'
                      f'billing={center.billing_enabled};contract={center.billing_contract_id};'
                      f'fee={center.default_report_fee};pool={sorted(wanted)}')
            elif action=='SYNC':
                count=_rb.capture_external_pacs_studies()
                _rb.audit('EXTERNAL_INTAKE_SYNC','external_intake_case','',f'created={count}')
            else:
                _rb.abort(400)
            _rb.db.session.commit()
            return _rb.redirect(_rb.url_for('admin_external_intake'))
        doctors=_rb.User.query.join(_rb.Role).filter(_rb.User.active.is_(True),_rb.Role.code.in_(['RADIOLOGIST','DOCTOR'])).all()
        centers=_rb.ExternalReportingCenter.query.order_by(_rb.ExternalReportingCenter.name).all()
        pools={c.id:{x.doctor_user_id for x in _rb.ExternalCenterDoctor.query.filter_by(center_id=c.id,active=True)} for c in centers}
        rows=_rb.ExternalIntakeCase.query.order_by(_rb.ExternalIntakeCase.created_at.desc()).limit(500).all()
        demographic_checks={}
        for row in rows:
            try: demographic_checks[row.id]=_rb.json.loads(row.demographic_checks_json or '[]')
            except Exception: demographic_checks[row.id]=[]
        return _rb.render_template('admin_external_intake.html',setting=setting,centers=centers,
                               doctors=doctors,pools=pools,rows=rows,
                               demographic_checks=demographic_checks,
                               contracts=_rb.Contract.query.filter_by(active=True).order_by(_rb.Contract.name).all(),
                               intake_attachments={row.id:_rb.Attachment.query.filter_by(
                                   external_intake_id=row.id).order_by(_rb.Attachment.created_at.desc()).all()
                                   for row in rows})
    return admin_external_intake


def install_0848(_rb):
    @_rb.app.post('/admin/external-intake/<int:intake_id>/attachments')
    @_rb.require_perm('assignment.manage')
    def admin_external_intake_attachment_upload(intake_id):
        row=_rb.ExternalIntakeCase.query.get_or_404(intake_id)
        if row.status not in ('RECEIVED','HOLD'): _rb.abort(409)
        files=[item for item in _rb.request.files.getlist('files') if item and item.filename]
        if not files:
            _rb.flash('Choose one or more referral or approval documents.','danger')
            return _rb.redirect(_rb.url_for('admin_external_intake'))
        category=(_rb.request.form.get('category') or 'REFERRAL').strip().upper()
        if category not in ('REFERRAL','APPROVAL','CLINICAL','IDENTITY','OTHER'): _rb.abort(400)
        notes=(_rb.request.form.get('notes') or '').strip()[:500]
        folder=_rb.os.path.join(_rb.ATTACHMENT_DIR,'external-intake',str(row.id))
        _rb.os.makedirs(folder,exist_ok=True)
        allowed_exts=('.pdf','.jpg','.jpeg','.png','.doc','.docx','.odt','.dcm','.dicom','.zip')
        saved=0
        for uploaded in files:
            ext=_rb.os.path.splitext(uploaded.filename)[1].lower()
            if ext not in allowed_exts:
                continue
            stored_name=_rb.generated_attachment_filename(row.id,category,uploaded.filename)
            path=_rb.os.path.join(folder,stored_name)
            uploaded.save(path)
            _rb.db.session.add(_rb.Attachment(
                external_intake_id=row.id,category=category,
                original_name=uploaded.filename[:255],stored_path=path,
                mime_type=(uploaded.mimetype or '')[:120],notes=notes,
                uploaded_by=_rb.current_user().id
            ))
            saved+=1
        if saved<1:
            _rb.flash('No supported documents were uploaded.','danger')
            return _rb.redirect(_rb.url_for('admin_external_intake'))
        _rb.audit('EXTERNAL_INTAKE_ATTACHMENT_UPLOAD','external_intake_case',row.id,
              f'category={category};count={saved}')
        _rb.db.session.commit()
        _rb.flash(f'{saved} external intake document(s) uploaded.','success')
        return _rb.redirect(_rb.url_for('admin_external_intake'))
    return admin_external_intake_attachment_upload


def install_0849(_rb):
    @_rb.app.post('/admin/external-intake/<int:intake_id>/decision')
    @_rb.require_perm('assignment.manage')
    def admin_external_intake_decision(intake_id):
        row=_rb.ExternalIntakeCase.query.get_or_404(intake_id)
        action=(_rb.request.form.get('action') or '').upper()
        note=(_rb.request.form.get('note') or '').strip()[:500]
        if action=='VERIFY':
            row.expected_patient_id=(_rb.request.form.get('expected_patient_id') or '').strip()[:80]
            row.expected_patient_name=(_rb.request.form.get('expected_patient_name') or '').strip()[:180]
            row.expected_dob=_rb.normalize_date(_rb.request.form.get('expected_dob'))
            row.expected_sex=(_rb.request.form.get('expected_sex') or '').strip().upper()[:1]
            row.expected_accession=(_rb.request.form.get('expected_accession') or '').strip()[:120]
            if not (row.expected_patient_id and row.expected_patient_name and
                    row.expected_dob and row.expected_accession):
                _rb.abort(400)
            result=_rb.external_intake_demographic_verification(
                row,persist=True,actor_user_id=_rb.current_user().id
            )
            _rb.audit('EXTERNAL_DEMOGRAPHICS_VERIFY','external_intake_case',row.id,
                  f"status={result['status']};score={result['score']};facts={result['facts_sha256']}")
            _rb.db.session.commit()
            _rb.flash('Demographic verification: '+result['status'],
                  'success' if result['status']=='MATCHED' else 'warning')
            return _rb.redirect(_rb.url_for('admin_external_intake'))
        if action=='APPROVE_REVIEW':
            result=_rb.external_intake_demographic_verification(row,persist=True,
                                                            actor_user_id=_rb.current_user().id)
            if result['status']!='REVIEW_REQUIRED': _rb.abort(409)
            if result['source_error']: _rb.abort(409)
            if not note: _rb.abort(400)
            row.demographic_override_approved=True
            row.demographic_override_reason=note
            row.demographic_override_by=_rb.current_user().id
            row.demographic_override_at=_rb.datetime.utcnow()
            row.demographic_override_facts_sha256=result['facts_sha256']
            _rb.audit('EXTERNAL_DEMOGRAPHICS_APPROVE_REVIEW','external_intake_case',row.id,
                  f"reason={note};facts={result['facts_sha256']}")
            _rb.db.session.commit()
            _rb.flash('Demographic review approved for the current DICOM facts.','success')
            return _rb.redirect(_rb.url_for('admin_external_intake'))
        if action=='QUEUE':
            _,status=_rb.queue_external_intake(row,_rb.current_user().id)
            _rb.flash('External case queued.' if status in ('OFFERED','DIRECT_ASSIGNED') else f'Queue result: {status}',
                  'success' if status in ('OFFERED','DIRECT_ASSIGNED') else 'warning')
            return _rb.redirect(_rb.url_for('admin_external_intake'))
        if row.status not in ('RECEIVED','HOLD'): _rb.abort(409)
        if action not in ('HOLD','REJECT'): _rb.abort(400)
        row.status='HOLD' if action=='HOLD' else 'REJECTED'
        row.review_note=note;row.reviewed_by=_rb.current_user().id;row.reviewed_at=_rb.datetime.utcnow()
        _rb.audit('EXTERNAL_INTAKE_'+action,'external_intake_case',row.id,note)
        _rb.db.session.commit()
        return _rb.redirect(_rb.url_for('admin_external_intake'))
    return admin_external_intake_decision


def install_0856(_rb):
    @_rb.app.get('/api/assignment/offers/pending')
    @_rb.login_required
    def api_assignment_offer_pending():
        _rb.expire_assignment_offers()

        row = _rb.AssignmentOffer.query.filter_by(
            doctor_user_id=_rb.current_user().id,
            status='PENDING'
        ).order_by(
            _rb.AssignmentOffer.offered_at.desc()
        ).first()

        if not row:
            return _rb.jsonify({'pending': False})

        o = row.order

        return _rb.jsonify({
            'pending': True,
            'offer_id': row.id,
            **_rb.assignment_visit_summary(o),
            'accession': o.accession,
            'modality': o.modality,
            'procedure': o.procedure,
            'priority': o.priority,
            'images': int(o.pacs_image_count or 0),
            'expires_at': row.expires_at.isoformat() + 'Z' if row.expires_at else None,
            'viewer_url': _rb.case_pacs_url(o),
            'respond_url': _rb.url_for(
                'assignment_offer_respond',
                offer_id=row.id
            )
        })
    return api_assignment_offer_pending
