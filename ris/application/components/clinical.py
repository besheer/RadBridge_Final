"""Runtime-bound application.components.clinical; dependencies are supplied at composition.

Legacy behavior is preserved; new policies belong in the independent domain layer.
"""

def install_0012(_rb):
    def exam_status_rank(value):
        value=_rb.normalize_state(value)
        try:
            return _rb.EXAM_STATUS_ORDER.index(value)
        except ValueError:
            return -1
    return exam_status_rank


def install_0085(_rb):
    def clinical_image_only_url(order):
        """OHIF study viewer without reporting identity or RIS report context."""
        uid = _rb.ohif_study_uid(order)

        if not uid:
            return None

        from urllib.parse import quote

        return (
            f'{_rb.OHIF_PUBLIC_URL}/viewer'
            f'?StudyInstanceUIDs={quote(uid, safe="")}'
        )
    return clinical_image_only_url


def install_0184(_rb):
    def technician_minimum_requirement(order,rule):
        minimum=(rule.min_images or 0) if rule else 0
        approved=_rb.CaseReadinessOverride.query.filter_by(order_id=order.id,blocker='INCOMPLETE_IMAGES',active=True).first()
        if approved:
            try: minimum=max(0,int(approved.override_value))
            except (ValueError,TypeError): pass
        return max(1,minimum),approved
    return technician_minimum_requirement


def install_0185(_rb):
    def technician_completion_evidence(order):
        import procedure_staff_workflow as staff
        mod=_rb._reporting_support_sys.modules[_rb.__name__]
        configured=staff.policy(mod,order)
        extra=staff.requirements(mod,order,configured)
        if configured.get('configured') and not configured.get('require_images') and not order.pacs_study_id and not (order.pacs_image_count or 0) and (order.pacs_status or '').upper()!='RECEIVING':
            return dict(allowed=extra['allowed'],reason=extra['reason'],warning='',image_count=0,min_images=0,images_required=False,policy_version=configured.get('version'),blockers=extra['blockers']), (0,{},'',[])
        from technician_image_policy import completion_image_policy
        from case_exception_resolution_service import apply_series_aliases
        rule=_rb.quality_rule_for(order)
        evidence=_rb.pacs_readiness_evidence(order)
        # Recheck the current acquisition first, so replacing conflicting images
        # can clear their previous metadata blocker in this same audited check.
        if evidence[1] and not evidence[2] and evidence[0]>0:
            _rb.evaluate_case_readiness(order,pacs_evidence=evidence)
        matched,_match_reason=_rb.pacs_demographic_gate(order)
        count,meta,error,series=evidence
        minimum,approved=_rb.technician_minimum_requirement(order,rule)
        aliases=_rb.ReadinessSeriesAlias.query.filter_by(rule_id=rule.id,active=True).all() if rule else []
        result=completion_image_policy(matched=matched,pacs_present=bool(meta),error=error,
            image_count=count,policy_defined=bool(rule),min_images=minimum,
            required_series=rule.required_series if rule else '',series=apply_series_aliases(series,aliases))
        from exam_type_policy import evidence_exam_match
        type_check=evidence_exam_match(order,evidence,rule)
        result['exam_type']=type_check
        if not type_check['allowed']:
            result['allowed']=False
            result['reason']+='; Exam metadata requires review: '+type_check['status']
        elif type_check['status']=='REVIEW_REQUIRED':
            result['warning']+=' Exam region could not be confirmed from DICOM metadata; review the procedure policy.'
        result['rule_id']=rule.id if rule else None
        result['minimum_override_id']=approved.id if approved else None
        if not extra['allowed']:
            result['allowed']=False
            result['reason']+='; '+extra['reason']
            result['completion_blockers']=extra['blockers']
        return result,evidence
    return technician_completion_evidence
