"""Runtime-bound application.components.readiness; dependencies are supplied at composition.

Legacy behavior is preserved; new policies belong in the independent domain layer.
"""

def install_0369(_rb):
    def quality_rule_for(order):
        mod=str(order.modality or '').upper()
        proc=str(order.procedure or '').upper()
        rows=_rb.ProcedureQualityRule.query.filter_by(active=True,modality=mod).all()
        exact=[r for r in rows if r.procedure_pattern.upper() in proc]
        return sorted(exact,key=lambda r:len(r.procedure_pattern),reverse=True)[0] if exact else None
    return quality_rule_for


def install_0373(_rb):
    def pacs_readiness_evidence(order):
        meta,error=_rb.pacs_study_lookup(order)
        if not meta: return 0,meta,error,[]
        try:
            import requests,os
            base=(_rb.app.config.get('ORTHANC_URL') or os.environ.get('ORTHANC_URL') or '').rstrip('/')
            auth=(os.environ.get('ORTHANC_USER',''),os.environ.get('ORTHANC_PASSWORD','')) if os.environ.get('ORTHANC_USER') else None
            sid=meta.get('orthanc_study_id')
            r=requests.get(f'{base}/studies/{sid}',auth=auth,timeout=20);r.raise_for_status()
            study=r.json()
            total=0
            series=[]
            for series_id in study.get('Series',[]):
                sr=requests.get(f'{base}/series/{series_id}',auth=auth,timeout=20);sr.raise_for_status()
                payload=sr.json(); instances=len(payload.get('Instances',[])); total+=instances
                tags=payload.get('MainDicomTags') or {}
                series.append({'series_id':series_id,'description':tags.get('SeriesDescription',''),
                  'protocol':tags.get('ProtocolName',''),'modality':tags.get('Modality',''),
                  'body_part':tags.get('BodyPartExamined',''),
                  'instance_count':instances})
            return total,meta,'',series
        except Exception as e:
            return 0,meta,str(e)[:500],[]
    return pacs_readiness_evidence


def install_0374(_rb):
    def evaluate_case_readiness(order,pacs_evidence=None):
        from case_readiness_service import evaluate_readiness
        from case_exception_resolution_service import apply_series_aliases
        rule=_rb.quality_rule_for(order)
        count,pacs,error,series=pacs_evidence if pacs_evidence is not None else _rb.pacs_readiness_evidence(order)
        has_history=_rb._order_history_present(order)
        attachments=_rb._order_attachment_count(order)
        missing_pacs=not bool(pacs)
        min_images=(rule.min_images if rule else 0) or 0
        warn_images=(rule.warning_images if rule else 0) or 0
        min_override=_rb.CaseReadinessOverride.query.filter_by(
            order_id=order.id,blocker='INCOMPLETE_IMAGES',active=True).first()
        rule_min_images=min_images
        if min_override:
            try: min_images=max(0,int(min_override.override_value))
            except Exception: min_images=rule_min_images
        aliases=(_rb.ReadinessSeriesAlias.query.filter_by(rule_id=rule.id,active=True).all()
                 if rule else [])
        mapped_series=apply_series_aliases(series,aliases)
        result=evaluate_readiness(image_count=count,min_images=min_images,warning_images=warn_images,
          require_pacs=bool(rule.require_pacs_study) if rule else True,pacs_present=bool(pacs),
          require_history=bool(rule.require_history) if rule else False,history_present=has_history,
          require_attachments=bool(rule.require_attachments) if rule else False,attachment_count=attachments,
          required_series=(rule.required_series if rule else ''),series=mapped_series)
        from reception_readiness import receiving
        result['details']['pacs_status']=str(order.pacs_status or '')
        if receiving(order):
            result['status']='BLOCKED';result['score']=0
            result['flags']['incomplete_images']=True
            result['details']['blockers']=sorted(set(result['details'].get('blockers',[])+['PACS_RECEIVING']))
        from exam_type_policy import evidence_exam_match
        type_check=evidence_exam_match(order,(count,pacs,error,series),rule)
        result['details']['exam_type']=type_check
        if not type_check['allowed']:
            result['status']='BLOCKED'
            result['score']=0
        # Bind readiness evidence to the independent exam-type safety check too.
        import hashlib
        result['facts_sha256']=hashlib.sha256((result['facts_sha256']+_rb.json.dumps(type_check,sort_keys=True)+str(order.pacs_status or '')).encode()).hexdigest()
        flags=result['flags']
        row=_rb.CaseReadiness.query.filter_by(order_id=order.id).first() or _rb.CaseReadiness(order_id=order.id)
        row.status=result['status'];row.score=result['score'];row.image_count=count;row.expected_min_images=min_images
        row.missing_history=flags['missing_history'];row.missing_attachments=flags['missing_attachments']
        row.missing_pacs=flags['missing_pacs'];row.incomplete_images=flags['incomplete_images']
        row.missing_series=flags['missing_series'];row.checked_at=_rb.datetime.utcnow();row.series_checked_at=row.checked_at
        result['details'].update({'pacs_error':error,'rule_id':rule.id if rule else None,
          'history':has_history,'attachments':attachments,
          'rule_min_images':rule_min_images,
          'minimum_override_id':min_override.id if min_override else None})
        row.details_json=_rb.json.dumps(result['details'],ensure_ascii=False)
        row.series_evidence_json=_rb.json.dumps(mapped_series,ensure_ascii=False);row.facts_sha256=result['facts_sha256']
        _rb.db.session.add(row);_rb.db.session.flush()
        return row
    return evaluate_case_readiness


def install_0381(_rb):
    def resolve_tat_policy(priority, modality=None):
        """Resolve active TAT policy by priority + modality, then wildcard."""
        priority_key = str(priority or 'ROUTINE').strip().upper()
        modality_key = str(modality or '').strip().upper()

        if modality_key:
            exact = (
                _rb.TATPolicy.query
                .filter_by(
                    priority=priority_key,
                    modality=modality_key,
                    active=True,
                )
                .order_by(_rb.TATPolicy.id.asc())
                .first()
            )
            if exact:
                return exact

        return (
            _rb.TATPolicy.query
            .filter_by(
                priority=priority_key,
                modality='*',
                active=True,
            )
            .order_by(_rb.TATPolicy.id.asc())
            .first()
        )
    return resolve_tat_policy


def install_0700(_rb):
    def case_exception_history_allowed():
        return any(_rb.has_perm(permission) for permission in (
            'orders.create','nursing.worklist','reports.coordinate','pacs.reconcile'))
    return case_exception_history_allowed


def install_0701(_rb):
    def case_exception_refresh_allowed():
        return any(_rb.has_perm(permission) for permission in (
            'orders.status','nursing.worklist','reports.coordinate','assignment.manage',
            'pacs.reconcile'))
    return case_exception_refresh_allowed


def install_0702(_rb):
    def case_exception_override_allowed():
        return _rb.has_perm('pacs.reconcile') and _rb.has_perm('workflow.override')
    return case_exception_override_allowed


def install_0717(_rb):
    def format_sla_minutes(minutes):
        if minutes is None:
            return '—'

        minutes=abs(int(minutes))
        days,rem=divmod(minutes,1440)
        hours,mins=divmod(rem,60)

        parts=[]

        if days:
            parts.append(f'{days}d')

        if hours:
            parts.append(f'{hours}h')

        parts.append(f'{mins}m')

        return ' '.join(parts)
    return format_sla_minutes

