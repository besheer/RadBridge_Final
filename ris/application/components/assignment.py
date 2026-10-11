"""Runtime-bound application.components.assignment; dependencies are supplied at composition.

Legacy behavior is preserved; new policies belong in the independent domain layer.
"""

def install_0097(_rb):
    def assignable_doctors():
        # User.role is a relationship, so filtering must use Role.code.
        return (
            _rb.User.query.join(_rb.Role, _rb.User.role_id==_rb.Role.id)
            .filter(
                _rb.User.active.is_(True),
                _rb.Role.code.in_(['RADIOLOGIST','DOCTOR'])
            )
            .order_by(_rb.User.full_name.asc(),_rb.User.username.asc())
            .all()
        )
    return assignable_doctors


def install_0100(_rb):
    def auto_assign_order(order, assigned_by=None):
        eligible=_rb.eligible_doctors_for_order(order)
        if not eligible:
            return None

        # Lowest workload first, then higher priority weight.
        eligible.sort(key=lambda x:(x[2], -int(x[0].priority_weight or 100), x[1].id))
        profile,user,active_count=eligible[0]

        from assignment_visit_grouping import assign_visit_atomically as assign_case_atomically

        result=assign_case_atomically(
            db=_rb.db,
            Order=_rb.Order,
            User=_rb.User,
            CaseAssignment=_rb.CaseAssignment,
            Report=_rb.Report,
            AssignmentOffer=_rb.AssignmentOffer,
            order_id=order.id,
            doctor_user_id=user.id,
            assigned_by=assigned_by,
            assignment_type='AUTO',
            notes='Legacy automatic assignment',
        )
        _rb.audit('CASE_AUTO_ASSIGN','order',order.id,f'doctor={user.username} workload={active_count}')
        return result.doctor
    return auto_assign_order


def install_0101(_rb):
    def manual_assign_order(
        order,
        doctor_user_id,
        assigned_by=None,
        notes='',
        assignment_type='MANUAL',
        require_unassigned=False,
    ):
        from assignment_visit_grouping import assign_visit_atomically as assign_case_atomically

        result=assign_case_atomically(
            db=_rb.db,
            Order=_rb.Order,
            User=_rb.User,
            CaseAssignment=_rb.CaseAssignment,
            Report=_rb.Report,
            AssignmentOffer=_rb.AssignmentOffer,
            order_id=order.id,
            doctor_user_id=doctor_user_id,
            assigned_by=assigned_by,
            assignment_type=assignment_type,
            notes=notes,
            require_unassigned=require_unassigned,
        )
        _rb.audit(
            'CASE_MANUAL_ASSIGN',
            'order',
            order.id,
            (
                f'doctor={result.doctor.username}; '
                f'type={assignment_type}; '
                f'idempotent={int(result.idempotent)}'
            )
        )
        return result.doctor
    return manual_assign_order


def install_0354(_rb):
    def seed_assignment_offer_policy():
        if not _rb.AssignmentOfferPolicy.query.first():
            _rb.db.session.add(_rb.AssignmentOfferPolicy())
            _rb.db.session.commit()
    return seed_assignment_offer_policy


def install_0355(_rb):
    def assignment_offer_policy():
        return _rb.AssignmentOfferPolicy.query.filter_by(enabled=True).order_by(_rb.AssignmentOfferPolicy.id).first()
    return assignment_offer_policy


def install_0356(_rb):
    def doctor_availability(user):
        row=_rb.DoctorAvailabilityState.query.filter_by(user_id=user.id).first()
        if not row:
            row=_rb.DoctorAvailabilityState(user_id=user.id,state='AVAILABLE',last_seen_at=_rb.datetime.utcnow())
            _rb.db.session.add(row);_rb.db.session.flush()
        if row.busy_until and row.busy_until<=_rb.datetime.utcnow() and row.state=='BUSY':
            row.state='AVAILABLE';row.busy_until=None
        return row
    return doctor_availability


def install_0358(_rb):
    def assignment_timeout_for(order,policy):
        p=(order.priority or 'ROUTINE').upper()
        if p=='STAT': return max(30,int(policy.stat_timeout_seconds or 60))
        if p=='URGENT': return max(30,int(policy.urgent_timeout_seconds or 120))
        return max(30,int(policy.routine_timeout_seconds or 300))
    return assignment_timeout_for


def install_0359(_rb):
    def assignment_candidate_users(order,policy):
        q=_rb.User.query.filter(_rb.User.active.is_(True)).order_by(_rb.User.id).with_for_update()
        external_intake=_rb.ExternalIntakeCase.query.filter_by(order_id=order.id).first()
        external_doctor_ids=None
        if external_intake:
            # Fail closed: external work is assignable only after the explicit
            # queue decision and only to this center's active doctor pool.
            if external_intake.status!='QUEUED' or not external_intake.center.assignment_enabled:
                return []
            external_doctor_ids={
                row.doctor_user_id
                for row in _rb.ExternalCenterDoctor.query.filter_by(
                    center_id=external_intake.center_id,
                    active=True
                ).all()
            }
            if not external_doctor_ids:
                return []
        candidates=[]
        for u in q.all():
            role_code=(u.role.code if u.role else '').upper()
            if role_code not in ('RADIOLOGIST','DOCTOR'):
                continue
            if external_doctor_ids is not None and u.id not in external_doctor_ids:
                continue
            prof=_rb.DoctorAssignmentProfile.query.filter_by(user_id=u.id).first()
            if prof:
                if not prof.available or not prof.auto_assign:
                    continue
                mods=[x.strip().upper() for x in (prof.modalities or '').split(',') if x.strip()]
                if mods and str(order.modality or '').upper() not in mods:
                    continue
                branches=[x.strip() for x in (prof.branches or '').split(',') if x.strip()]
                if branches and str(order.branch_id) not in branches:
                    continue
            state=_rb.doctor_availability(u)
            if state.state in ('BUSY','AWAY','OFFLINE'):
                if policy.mode=='ALL' and state.state!='BUSY':
                    pass
                else:
                    continue
            online=_rb.doctor_is_online(u)
            if policy.mode=='ONLINE_ONLY' and not online:
                continue
            from assignment_distribution import active_case_count
            active_cases=active_case_count(u.id)
            max_cases=(prof.max_active_cases if prof else 20) or 20
            if active_cases>=max_cases:
                continue
            weight=(prof.priority_weight if prof else 100) or 100
            candidates.append((u,online,active_cases,weight))
        from assignment_distribution import rank_candidates
        from assignment_visit_grouping import prefer_visit_doctor
        return prefer_visit_doctor(order, rank_candidates(candidates, order=order))
    return assignment_candidate_users


def install_0360(_rb):
    def assignment_offer_channels(policy):
        return [x.strip().upper() for x in (policy.notification_channels or '').split(',') if x.strip()]
    return assignment_offer_channels


def install_0361(_rb):
    def create_assignment_offer(order,doctor,attempt_no=1,created_by=None,strategy=None):
        policy=_rb.assignment_offer_policy()
        if not policy:
            return None

        timeout=_rb.assignment_strategy_timeout(
            order,
            strategy,
            policy
        )
        row=_rb.AssignmentOffer(
            order_id=order.id,doctor_user_id=doctor.id,attempt_no=attempt_no,
            status='PENDING',offered_at=_rb.datetime.utcnow(),
            expires_at=_rb.datetime.utcnow()+_rb.timedelta(seconds=timeout),
            created_by=created_by
        )
        _rb.db.session.add(row);_rb.db.session.flush()
        channels=[]
        # In-app is implicit. External channels use existing Communication Hub.
        for ch in _rb.assignment_offer_channels(policy):
            if ch=='INAPP':
                channels.append('INAPP')
                continue
            try:
                patient=order.patient
                recipient=''
                if ch=='EMAIL':
                    recipient=getattr(doctor,'email','') or ''
                elif ch in ('WHATSAPP','TELEGRAM'):
                    recipient=getattr(doctor,'phone','') or ''
                if not recipient:
                    continue
                body=(
                  f'RIS case offer: {order.accession} | {order.modality} | {order.procedure} | '
                  f'Priority: {order.priority}. Please open RIS to Accept / Busy / Reject before {row.expires_at}.'
                )
                msg=_rb.PatientCommunication(
                  patient_id=patient.id,order_id=order.id,channel=ch,recipient=recipient,
                  template_code='ASSIGNMENT_OFFER',subject='RIS Case Assignment Offer',
                  body=body,status='PENDING',created_by=created_by
                )
                _rb.db.session.add(msg);_rb.db.session.flush()
                ok,_=_rb.send_patient_communication(msg)
                if ok: channels.append(ch)
            except Exception:
                pass
        row.channel_summary=','.join(channels)
        _rb.db.session.add(_rb.AssignmentEscalationEvent(
          order_id=order.id,offer_id=row.id,event_type='OFFERED',
          details=f'doctor={doctor.id};attempt={attempt_no};channels={row.channel_summary}',created_by=created_by
        ))
        _rb.db.session.commit()
        return row
    return create_assignment_offer


def install_0364(_rb):
    def offer_next_doctor(order,created_by=None):
        """
    RadBridge v5.33 Smart Assignment Engine.

    Readiness:
      BLOCK
      WARN
      ALLOW
      COORDINATOR

    Assignment modes:
      OFFER_ACCEPT
      DIRECT_ASSIGN
      OPEN_POOL
      HYBRID
      MANUAL_ONLY
    """

        from assignment_visit_grouping import visit_ready_for_offer
        order, visit_reason = visit_ready_for_offer(order)
        if visit_reason: return None, visit_reason

        # RB_UNIFIED_ASSIGNMENT_GUARD_V1
        order = (
            _rb.Order.query
            .filter_by(id=order.id)
            .with_for_update()
            .first()
        )

        if not order:
            return None, 'ORDER_NOT_FOUND'
        from reception_readiness import receiving
        if receiving(order):return None, 'PACS_RECEIVING'

        if order.assigned_doctor_id:
            return None, 'ALREADY_ASSIGNED'

        if _rb.CaseAssignment.query.filter_by(order_id=order.id,active=True).first():
            return None, 'ACTIVE_ASSIGNMENT_EXISTS'

        if _rb.case_return_is_open(order.id):
            return None, 'RETURNED_FOR_CORRECTION'

        pending_offer = _rb.AssignmentOffer.query.filter_by(
            order_id=order.id,
            status='PENDING'
        ).first()

        if pending_offer:
            return pending_offer, 'PENDING_OFFER_EXISTS'

        decision = _rb.assignment_readiness_decision(order)

        strategy = decision.get('strategy')
        action = decision.get('action', 'BLOCK')
        blockers = decision.get('blockers') or []
        warnings = decision.get('warnings') or []
        coordinator = decision.get('coordinator') or []

        strategy_name = strategy.name if strategy else 'LEGACY_POLICY'


        # ------------------------------------------------------
        # Readiness blocked
        # ------------------------------------------------------

        if not decision.get('allowed'):

            reasons = blockers or coordinator or ['CASE_NOT_READY']
            reason_text = ','.join(reasons)

            if action == 'COORDINATOR':

                _rb.db.session.add(
                    _rb.AssignmentEscalationEvent(
                        order_id=order.id,
                        event_type='COORDINATOR_QUEUE',
                        details=f'strategy={strategy_name}; reasons={reason_text}',
                        created_by=created_by
                    )
                )

                _rb.create_ris_notification(
                    order,
                    'ASSIGNMENT_COORDINATOR',
                    'Case requires coordinator review',
                    f'Assignment strategy routed this case to coordinator: {reason_text}',
                    'WARNING',
                    'COORDINATOR'
                )

                _rb.db.session.commit()

                return None, 'COORDINATOR'


            _rb.create_ris_notification(
                order,
                'CASE_NOT_READY',
                'Case blocked from smart assignment',
                f'Strategy {strategy_name} blocked assignment: {reason_text}',
                'WARNING',
                'TECHNICIAN'
            )

            _rb.db.session.add(
                _rb.AssignmentEscalationEvent(
                    order_id=order.id,
                    event_type='READINESS_BLOCK',
                    details=f'strategy={strategy_name}; reasons={reason_text}',
                    created_by=created_by
                )
            )

            _rb.db.session.commit()

            return None, 'CASE_NOT_READY'


        # ------------------------------------------------------
        # WARN does not block assignment
        # ------------------------------------------------------

        if warnings:

            _rb.db.session.add(
                _rb.AssignmentEscalationEvent(
                    order_id=order.id,
                    event_type='READINESS_WARNING',
                    details=(
                        f'strategy={strategy_name}; '
                        f'warnings={",".join(warnings)}'
                    ),
                    created_by=created_by
                )
            )


        policy = _rb.assignment_offer_policy()

        if not policy:
            _rb.db.session.rollback()
            return None, 'NO_POLICY'


        mode = (
            str(strategy.assignment_mode or 'OFFER_ACCEPT').upper()
            if strategy
            else 'OFFER_ACCEPT'
        )


        # ------------------------------------------------------
        # Manual only
        # ------------------------------------------------------

        if mode == 'MANUAL_ONLY':

            _rb.db.session.add(
                _rb.AssignmentEscalationEvent(
                    order_id=order.id,
                    event_type='MANUAL_ONLY',
                    details=f'strategy={strategy_name}',
                    created_by=created_by
                )
            )

            _rb.db.session.commit()

            return None, 'MANUAL_ONLY'


        # ------------------------------------------------------
        # Open Pool
        # ------------------------------------------------------

        if mode == 'OPEN_POOL':

            _rb.db.session.add(
                _rb.AssignmentEscalationEvent(
                    order_id=order.id,
                    event_type='OPEN_POOL',
                    details=f'strategy={strategy_name}',
                    created_by=created_by
                )
            )

            _rb.db.session.commit()

            return None, 'OPEN_POOL'


        # ------------------------------------------------------
        # Previous attempts
        # ------------------------------------------------------

        previous = _rb.AssignmentOffer.query.filter_by(
            order_id=order.id
        ).order_by(
            _rb.AssignmentOffer.attempt_no
        ).all()

        tried = {
            x.doctor_user_id
            for x in previous
        }

        attempt = max(
            [x.attempt_no for x in previous],
            default=0
        ) + 1


        max_attempts = _rb.assignment_strategy_max_attempts(
            strategy,
            policy
        )


        # ------------------------------------------------------
        # Maximum attempts reached
        # ------------------------------------------------------

        if attempt > max_attempts:

            fallback = (
                str(strategy.fallback_mode or 'COORDINATOR').upper()
                if strategy
                else 'COORDINATOR'
            )


            if fallback == 'OPEN_POOL':

                _rb.db.session.add(
                    _rb.AssignmentEscalationEvent(
                        order_id=order.id,
                        event_type='OPEN_POOL',
                        details=(
                            f'strategy={strategy_name}; '
                            'reason=MAX_ATTEMPTS'
                        ),
                        created_by=created_by
                    )
                )

                _rb.db.session.commit()

                return None, 'OPEN_POOL'


            if fallback == 'MANUAL_ONLY':

                _rb.db.session.add(
                    _rb.AssignmentEscalationEvent(
                        order_id=order.id,
                        event_type='MANUAL_ONLY',
                        details=(
                            f'strategy={strategy_name}; '
                            'reason=MAX_ATTEMPTS'
                        ),
                        created_by=created_by
                    )
                )

                _rb.db.session.commit()

                return None, 'MANUAL_ONLY'


            _rb.db.session.add(
                _rb.AssignmentEscalationEvent(
                    order_id=order.id,
                    event_type='ESCALATION_QUEUE',
                    details=(
                        f'strategy={strategy_name}; '
                        'reason=MAX_ATTEMPTS'
                    ),
                    created_by=created_by
                )
            )

            _rb.create_ris_notification(
                order,
                'ASSIGNMENT_ESCALATED',
                'Assignment escalated',
                'Maximum doctor offer attempts reached.',
                'WARNING',
                'COORDINATOR'
            )

            _rb.db.session.commit()

            return None, 'ESCALATED'


        # ------------------------------------------------------
        # Candidate selection
        # ------------------------------------------------------

        candidates = [
            u
            for u in _rb.assignment_candidate_users(order, policy)
            if u.id not in tried
        ]


        if strategy and strategy.require_online:

            candidates = [
                u
                for u in candidates
                if _rb.doctor_is_online(u)
            ]


        if not candidates:

            _rb.db.session.add(
                _rb.AssignmentEscalationEvent(
                    order_id=order.id,
                    event_type='NO_CANDIDATE',
                    details=(
                        f'strategy={strategy_name}; '
                        'reason=NO_ELIGIBLE_DOCTOR'
                    ),
                    created_by=created_by
                )
            )

            _rb.db.session.commit()

            return None, 'NO_CANDIDATE'


        doctor = candidates[0]


        # ------------------------------------------------------
        # DIRECT_ASSIGN
        # ------------------------------------------------------

        if mode == 'DIRECT_ASSIGN':

            row = _rb.create_assignment_offer(
                order,
                doctor,
                attempt,
                created_by,
                strategy=strategy
            )

            if not row:
                return None, 'NO_POLICY'


            from assignment_visit_grouping import assign_visit_atomically as assign_case_atomically

            now = _rb.datetime.utcnow()
            result = assign_case_atomically(
                db=_rb.db,
                Order=_rb.Order,
                User=_rb.User,
                CaseAssignment=_rb.CaseAssignment,
                Report=_rb.Report,
                AssignmentOffer=_rb.AssignmentOffer,
                order_id=order.id,
                doctor_user_id=doctor.id,
                assigned_by=created_by,
                assignment_type='AUTO_DIRECT',
                notes='Direct assignment by smart strategy',
                require_unassigned=True,
                accepted_offer_id=row.id,
                now=now,
            )

            row.status = 'ACCEPTED'
            row.responded_at = now
            row.response_note = 'Direct assignment by smart strategy'


            _rb.db.session.add(
                _rb.AssignmentEscalationEvent(
                    order_id=order.id,
                    offer_id=row.id,
                    event_type='DIRECT_ASSIGNED',
                    details=(
                        f'doctor={result.doctor.id}; '
                        f'strategy={strategy_name}'
                    ),
                    created_by=created_by
                )
            )

            _rb.db.session.commit()

            return row, 'DIRECT_ASSIGNED'


        # ------------------------------------------------------
        # OFFER_ACCEPT / HYBRID
        # ------------------------------------------------------

        offer = _rb.create_assignment_offer(
            order,
            doctor,
            attempt,
            created_by,
            strategy=strategy
        )

        if not offer:
            return None, 'NO_POLICY'


        _rb.db.session.add(
            _rb.AssignmentEscalationEvent(
                order_id=order.id,
                offer_id=offer.id,
                event_type='STRATEGY_SELECTED',
                details=(
                    f'strategy={strategy_name}; '
                    f'mode={mode}; '
                    f'attempt={attempt}'
                ),
                created_by=created_by
            )
        )

        _rb.db.session.commit()

        return offer, 'OFFERED'
    return offer_next_doctor


def install_0365(_rb):
    def assignment_decision_phase1(order,return_open=False):
        """Evaluate phase-1 policy without changing operational behavior."""
        from assignment_decision_engine import evaluate_assignment_decision

        readiness=__import__('reception_readiness').view(order,_rb.CaseReadiness.query.filter_by(order_id=order.id).first())
        result=evaluate_assignment_decision(
            mode=_rb.os.environ.get('RADBRIDGE_DECISION_ENGINE_MODE','DISABLED'),
            facts={
                'exam_status':order.exam_status,
                'pacs_status':order.pacs_status,
                'readiness_status':readiness.status if readiness else 'NOT_CHECKED',
                'return_open':bool(return_open),
                'already_assigned':bool(order.assigned_doctor_id),
            },
        )

        # RB_DECISION_ENGINE_PHASE1_SHADOW_V1
        # SHADOW is observational only: no offers, assignments, notifications,
        # database writes, or changes to the existing coordinator result.
        if result.mode=='SHADOW':
            _rb.app.logger.info(
                'Assignment decision shadow order=%s recommendation=%s reasons=%s',
                order.id,result.recommendation,','.join(result.reasons)
            )
        return result
    return assignment_decision_phase1


def install_0366(_rb):
    def coordinate_post_exam_assignment(order,created_by=None,trigger='POST_EXAM_READINESS'):
        # RB_UNIFIED_ASSIGNMENT_COORDINATOR_V1
        if not order:
            return None, 'ORDER_NOT_FOUND'

        order = _rb.Order.query.filter_by(id=order.id).with_for_update().first()
        if not order:
            return None, 'ORDER_NOT_FOUND'
        if order.assigned_doctor_id:
            return None, 'ALREADY_ASSIGNED'
        if _rb.CaseAssignment.query.filter_by(order_id=order.id,active=True).first():
            return None, 'ACTIVE_ASSIGNMENT_EXISTS'
        if _rb.case_return_is_open(order.id):
            return None, 'RETURNED_FOR_CORRECTION'
        if (order.exam_status or '').upper()!='EXAM_COMPLETED':
            return None, 'EXAM_NOT_COMPLETED'
        if (order.pacs_status or '').upper()!='IMAGES_COMPLETE':
            return None, 'IMAGES_NOT_COMPLETE'

        pending = _rb.AssignmentOffer.query.filter_by(order_id=order.id,status='PENDING').first()
        if pending:
            return pending, 'PENDING_OFFER_EXISTS'

        _rb.assignment_decision_phase1(order,return_open=False)

        offer,status=_rb.offer_next_doctor(order,created_by=created_by)
        _rb.app.logger.info(
            'Unified assignment coordinator order=%s trigger=%s status=%s',
            order.id,trigger,status
        )
        return offer,status
    return coordinate_post_exam_assignment


def install_0367(_rb):
    def expire_assignment_offers():
        from assignment_distribution import expire_unstarted_assignments
        expire_unstarted_assignments()
        now=_rb.datetime.utcnow()
        rows=_rb.AssignmentOffer.query.filter(
          _rb.AssignmentOffer.status=='PENDING',
          _rb.AssignmentOffer.expires_at<=now
        ).order_by(_rb.AssignmentOffer.expires_at).all()
        touched=[]
        for row in rows:
            row.status='TIMEOUT';row.responded_at=now
            _rb.db.session.add(_rb.AssignmentEscalationEvent(
              order_id=row.order_id,offer_id=row.id,event_type='TIMEOUT',
              details=f'doctor={row.doctor_user_id};attempt={row.attempt_no}'
            ))
            _rb.db.session.flush()
            next_offer,_=_rb.offer_next_doctor(row.order,created_by=None)
            touched.append((row.id,next_offer.id if next_offer else None))
        _rb.db.session.commit()
        return touched
    return expire_assignment_offers


def install_0376(_rb):
    def assignment_strategy_for_order(order):
        """
    Select the highest-priority enabled AssignmentStrategy
    matching branch / modality / procedure.

    Lower priority number wins.
    A blank scope means wildcard.
    """
        rows = _rb.AssignmentStrategy.query.filter_by(
            enabled=True
        ).order_by(
            _rb.AssignmentStrategy.priority.asc(),
            _rb.AssignmentStrategy.id.asc()
        ).all()

        modality = str(order.modality or '').strip().upper()
        procedure = str(order.procedure or '').strip().upper()

        for row in rows:

            if row.branch_id and row.branch_id != order.branch_id:
                continue

            if row.modality:
                if row.modality.strip().upper() != modality:
                    continue

            if row.procedure_pattern:
                pattern = row.procedure_pattern.strip().upper()
                if pattern not in procedure:
                    continue

            return row

        return None
    return assignment_strategy_for_order


def install_0377(_rb):
    def assignment_strategy_timeout(order, strategy, policy=None):
        priority = str(order.priority or 'ROUTINE').upper()

        if strategy:
            if priority == 'STAT':
                return int(strategy.stat_timeout_seconds or 60)

            if priority == 'URGENT':
                return int(strategy.urgent_timeout_seconds or 120)

            return int(strategy.routine_timeout_seconds or 300)

        if policy:
            return _rb.assignment_timeout_for(order, policy)

        return 300
    return assignment_strategy_timeout


def install_0378(_rb):
    def assignment_strategy_max_attempts(strategy, policy=None):
        if strategy and strategy.max_offer_attempts:
            return int(strategy.max_offer_attempts)

        if policy and policy.max_offer_attempts:
            return int(policy.max_offer_attempts)

        return 5
    return assignment_strategy_max_attempts


def install_0379(_rb):
    def assignment_readiness_decision(order,refresh_stale=True):
        '''
    Evaluate case readiness using the matching AssignmentStrategy.

    Returns:
      allowed       bool
      action        ALLOW / WARN / BLOCK / COORDINATOR
      blockers      list
      warnings      list
      strategy      AssignmentStrategy or None
      readiness     CaseReadiness
    '''

        row=_rb.CaseReadiness.query.filter_by(order_id=order.id).first()
        from reception_readiness import receiving, view
        if receiving(order):
            blockers=['PACS_RECEIVING']
            # Preserve independently detected identity/exam safety reasons as well.
            if row:
                from exam_type_policy import cached_exam_gate
                type_ok,type_reason=cached_exam_gate(order,row)
                if not type_ok:blockers.append(type_reason)
            return {'allowed':False,'action':'BLOCK','blockers':blockers,
                    'warnings':[],'coordinator':[],'strategy':None,'readiness':view(order,row)}

        if refresh_stale and (not row or not row.checked_at or (
            _rb.datetime.utcnow()-row.checked_at
        ).total_seconds()>300):
            row=_rb.evaluate_case_readiness(order)

        if not row:
            return {
                'allowed':False,'action':'BLOCK','blockers':['READINESS_NOT_CHECKED'],
                'warnings':[],'coordinator':[],'strategy':None,'readiness':None
            }

        from exam_type_policy import cached_exam_gate
        type_ok,type_reason=cached_exam_gate(order,row)
        if not type_ok:
            return {'allowed':False,'action':'BLOCK','blockers':[type_reason],
                'warnings':[],'coordinator':[],'strategy':None,'readiness':row}

        strategy=_rb.assignment_strategy_for_order(order)

        # Backward-compatible behavior until an admin strategy exists.
        if not strategy:
            return {
                'allowed': row.status=='READY',
                'action': 'ALLOW' if row.status=='READY' else 'BLOCK',
                'blockers': [] if row.status=='READY' else ['LEGACY_READINESS'],
                'warnings': [],
                'strategy': None,
                'readiness': row
            }

        blockers=[]
        warnings=[]
        coordinator=[]

        def apply(rule_action, reason):
            action=str(rule_action or 'WARN').upper()

            if action=='BLOCK':
                blockers.append(reason)

            elif action=='WARN':
                warnings.append(reason)

            elif action=='COORDINATOR':
                coordinator.append(reason)

            # ALLOW / IGNORE intentionally do nothing.

        if row.missing_pacs:
            apply(strategy.pacs_missing_action,'MISSING_PACS')

        if row.incomplete_images:
            apply(strategy.images_incomplete_action,'INCOMPLETE_IMAGES')

        # R8_PHASE3_REQUIRED_SERIES_STRATEGY_V1
        # Missing required acquisitions follow the configured image
        # completeness action. This preserves existing strategy policy
        # while ensuring required Series are never silently ignored.
        if getattr(row,'missing_series',False):
            apply(
                strategy.images_incomplete_action,
                'MISSING_REQUIRED_SERIES'
            )

        if getattr(row,'missing_documents',False):
            apply(strategy.documents_missing_action,'MISSING_DOCUMENTS')

        if getattr(row,'missing_notes',False):
            apply(strategy.notes_missing_action,'MISSING_NOTES')

        if row.missing_attachments:
            apply(strategy.attachments_missing_action,'MISSING_ATTACHMENTS')

        if row.missing_history:
            apply(strategy.history_missing_action,'MISSING_HISTORY')

        if int(order.pacs_image_count or 0) < int(strategy.min_images or 0):
            apply(
                strategy.images_incomplete_action,
                'MIN_IMAGES_NOT_MET'
            )

        if blockers:
            action='BLOCK'
            allowed=False

        elif coordinator:
            action='COORDINATOR'
            allowed=False

        elif warnings:
            action='WARN'
            allowed=True

        else:
            action='ALLOW'
            allowed=True

        return {
            'allowed':allowed,
            'action':action,
            'blockers':blockers,
            'warnings':warnings,
            'coordinator':coordinator,
            'strategy':strategy,
            'readiness':row
        }
    return assignment_readiness_decision


def install_0380(_rb):
    def readiness_allows_auto_assign(order):
        '''
    Compatibility wrapper for old callers.
    '''
        return _rb.assignment_readiness_decision(order)['allowed']
    return readiness_allows_auto_assign


def install_0536(_rb):
    def assignment_candidate_diagnostics(order,policy):

        rows=[]

        doctors=_rb.User.query.join(
            _rb.Role,
            _rb.User.role_id==_rb.Role.id
        ).filter(
            _rb.db.func.upper(_rb.Role.code).in_(
                ['RADIOLOGIST','DOCTOR']
            ),
            _rb.User.active==True
        ).order_by(
            _rb.User.id
        ).all()

        for u in doctors:

            reasons=[]

            profile=_rb.DoctorAssignmentProfile.query.filter_by(
                user_id=u.id
            ).first()

            state=_rb.doctor_availability(u)
            online=_rb.doctor_is_online(u)

            active_cases=_rb.CaseAssignment.query.filter_by(
                doctor_user_id=u.id,
                active=True
            ).count()

            max_cases=(
                int(profile.max_active_cases or 20)
                if profile
                else 20
            )

            modality_match=True
            branch_match=True

            if not profile:
                reasons.append('NO_PROFILE')

            else:

                if not profile.auto_assign:
                    reasons.append('AUTO_ASSIGN_DISABLED')

                if not profile.available:
                    reasons.append('PROFILE_UNAVAILABLE')

                modalities=[
                    x.strip().upper()
                    for x in (profile.modalities or '').split(',')
                    if x.strip()
                ]

                if (
                    modalities
                    and str(order.modality or '').upper()
                    not in modalities
                ):
                    modality_match=False
                    reasons.append('MODALITY_MISMATCH')

                branches=[
                    x.strip()
                    for x in (profile.branches or '').split(',')
                    if x.strip()
                ]

                if (
                    branches
                    and str(order.branch_id or '')
                    not in branches
                ):
                    branch_match=False
                    reasons.append('BRANCH_MISMATCH')

            if state.state=='BUSY':
                reasons.append('BUSY')

            elif state.state in ('AWAY','OFFLINE'):

                if policy and policy.mode!='ALL':
                    reasons.append(
                        'AVAILABILITY_'+state.state
                    )

            if (
                policy
                and policy.mode=='ONLINE_ONLY'
                and not online
            ):
                reasons.append('OFFLINE')

            if active_cases>=max_cases:
                reasons.append(
                    'MAX_ACTIVE_CASES_REACHED'
                )

            rows.append({
                'id':u.id,
                'username':u.username,
                'name':u.full_name or u.username,
                'eligible':len(reasons)==0,
                'reasons':reasons,
                'online':bool(online),
                'availability_state':state.state,
                'active_cases':active_cases,
                'max_active_cases':max_cases,
                'modality_match':modality_match,
                'branch_match':branch_match,
                'profile_exists':bool(profile),
                'auto_assign':(
                    bool(profile.auto_assign)
                    if profile
                    else False
                ),
                'available':(
                    bool(profile.available)
                    if profile
                    else False
                )
            })

        return rows
    return assignment_candidate_diagnostics


def install_0546(_rb):
    def unassigned_case_snapshot(order,readiness,policies,now=None):
        """Build a read-only queue row without refreshing PACS or changing data."""
        from reception_readiness import view,receiving
        readiness=view(order,readiness)
        now=now or _rb.datetime.utcnow()
        priority=str(order.priority or 'ROUTINE').upper()
        modality=str(order.modality or '').upper()
        policy=next((p for p in policies if str(p.priority or '').upper()==priority
                     and str(p.modality or '*').upper()==modality),None)
        if not policy:
            policy=next((p for p in policies if str(p.priority or '').upper()==priority
                         and str(p.modality or '*').upper()=='*'),None)
        started=getattr(order,'created_at',None) or getattr(order,'scheduled',None)
        waiting_minutes=max(0,int((now-started).total_seconds()/60)) if started else 0
        target=int(policy.ready_to_assign_min or 0) if policy else 0
        percent=round((waiting_minutes/target)*100,1) if target else 0
        if not target:
            sla_status='NOT_CONFIGURED'
        elif waiting_minutes>target:
            sla_status='OVERDUE'
        elif percent>=80:
            sla_status='NEAR_SLA'
        else:
            sla_status='ON_TIME'
        wait_hours,wait_minutes=divmod(waiting_minutes,60)
        waiting_label=(f'{wait_hours}h {wait_minutes}m' if wait_hours
                       else f'{wait_minutes}m')

        flags=[]
        if readiness:
            flag_fields=(
                ('missing_pacs','MISSING_PACS','PACS study missing','PACS غير موجود'),
                ('incomplete_images','MISSING_IMAGES','Missing Images','صور ناقصة'),
                ('missing_series','MISSING_SERIES','Required Series Missing','سلاسل مطلوبة ناقصة'),
                ('missing_documents','MISSING_DOCUMENTS','Missing Documents','مستندات ناقصة'),
                ('missing_attachments','MISSING_ATTACHMENTS','Missing Attachments','مرفقات ناقصة'),
                ('missing_notes','NOTES_REQUIRED','Notes Required','ملاحظات مطلوبة'),
                ('missing_history','HISTORY_REQUIRED','History Required','تاريخ مرضي مطلوب'),
            )
            for field,code,label,label_ar in flag_fields:
                if bool(getattr(readiness,field,False)):
                    flags.append({'code':code,'label':label,'label_ar':label_ar})

        if receiving(order):flags.append({'code':'PACS_RECEIVING','label':'Images still receiving — assignment blocked','label_ar':'جارٍ استقبال الصور — الإسناد متوقف'})

        readiness_status=str(getattr(readiness,'status','NOT_CHECKED') or 'NOT_CHECKED').upper()
        decision=_rb.assignment_readiness_decision(order,refresh_stale=False)
        assignable=bool(decision['allowed'])
        if not flags and readiness_status not in ('READY','WARNING'):
            flags.append({
                'code':'READINESS_'+readiness_status,
                'label':readiness_status.replace('_',' ').title(),
                'label_ar':'الجاهزية: '+readiness_status.replace('_',' '),
            })
        return {
            'order':order,'readiness':readiness,'readiness_status':readiness_status,
            'assignable':assignable,'flags':flags,'waiting_minutes':waiting_minutes,
            'waiting_label':waiting_label,
            'sla':{'status':sla_status,'target_minutes':target,'percent':percent},
            'specialty':getattr(getattr(order,'proc',None),'category','') or '',
            'decision':decision,
        }
    return unassigned_case_snapshot


def install_0855(_rb):
    def assignment_visit_summary(order):
        from assignment_visit_grouping import group_members
        members=group_members(order)
        return {'visit_id':order.assignment_visit_id or '', 'visit_exam_count':len(members),
                'linked_visit':len(members)>1,
                'special_code':order.assignment_special_code or '',
                'visit_examinations':[{'order_id':o.id,'modality':o.modality,'procedure':o.procedure} for o in members]}
    return assignment_visit_summary

