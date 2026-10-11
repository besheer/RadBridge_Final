"""Safe case-exception search and resolution helpers.

The caller owns commit/rollback.  No helper in this module commits a
transaction or changes DICOM content.
"""

import json
import re
from datetime import datetime

from sqlalchemy import or_


from domain.readiness_resolution import (
    TERMINAL_ORDER_STATUSES, TERMINAL_REPORT_STATUSES, ALLOWED_MATCH_FIELDS,
    CaseExceptionResolutionError, normalize, assert_editable, apply_series_aliases,
)
from application.services.readiness import resolution_workflow as _resolution
from infrastructure.adapters.readiness.resolution_repository import SqlAlchemyReadinessResolutionRepository

def _repository(db,Order,Report,**models):
    return SqlAlchemyReadinessResolutionRepository(db.session,Order,Report,**models)

def latest_report_status(db, Report, order_id):
    row = (db.session.query(Report)
           .filter(Report.order_id == int(order_id))
           .order_by(Report.id.desc()).first())
    return normalize(getattr(row, "status", ""))




def search_ris_orders(*, Order, Patient, query, limit=50):
    """Search RIS Orders without changing state."""
    query = str(query or "").strip()
    if not query:
        return []
    limit = max(1, min(int(limit or 50), 100))
    like = f"%{query}%"
    filters = [
        Order.accession.ilike(like),
        Order.procedure.ilike(like),
        Order.study_instance_uid.ilike(like),
        Patient.name.ilike(like),
        Patient.patient_id.ilike(like),
        Patient.phone.ilike(like),
        Patient.national_id.ilike(like),
    ]
    if query.isdigit():
        filters.append(Order.id == int(query))
    rows = (Order.query.join(Patient)
            .filter(or_(*filters))
            .order_by(Order.id.desc()).limit(limit).all())
    needle = normalize(query)

    def score(order):
        values = [
            (getattr(order, "accession", ""), 100),
            (getattr(order.patient, "patient_id", ""), 95),
            (getattr(order, "study_instance_uid", ""), 95),
            (str(getattr(order, "id", "")), 90),
            (getattr(order.patient, "name", ""), 80),
            (getattr(order, "procedure", ""), 60),
        ]
        best = 0
        for value, weight in values:
            current = normalize(value)
            if current == needle:
                best = max(best, weight)
            elif needle and needle in current:
                best = max(best, weight - 20)
        return best

    return sorted(rows, key=lambda row: (-score(row), -row.id))




def atomic_series_alias_mapping(*, db, Order, Report, ProcedureQualityRule,
                                ReadinessSeriesAlias, ResolutionEvent,
                                CaseReadiness=None,
                                order_id, source_alias, canonical_series,
                                match_field, actor_user_id, reason):
    return _resolution.atomic_series_alias_mapping(repository=_repository(db,Order,Report,ProcedureQualityRule=ProcedureQualityRule,ReadinessSeriesAlias=ReadinessSeriesAlias,ResolutionEvent=ResolutionEvent,CaseReadiness=CaseReadiness),clock=datetime.utcnow,
        order_id=order_id,source_alias=source_alias,canonical_series=canonical_series,match_field=match_field,actor_user_id=actor_user_id,reason=reason)


def atomic_add_clinical_history(*, db, Order, Report, ClinicalNote,
                                ResolutionEvent, order_id, text_value,
                                actor_user_id, reason):
    return _resolution.atomic_add_clinical_history(repository=_repository(db,Order,Report,ClinicalNote=ClinicalNote,ResolutionEvent=ResolutionEvent),clock=datetime.utcnow,
        order_id=order_id,text_value=text_value,actor_user_id=actor_user_id,reason=reason)


def atomic_image_minimum_override(*, db, Order, Report, CaseReadiness,
                                  CaseReadinessOverride, ResolutionEvent,
                                  order_id, approved_minimum,
                                  actor_user_id, reason):
    return _resolution.atomic_image_minimum_override(repository=_repository(db,Order,Report,CaseReadiness=CaseReadiness,CaseReadinessOverride=CaseReadinessOverride,ResolutionEvent=ResolutionEvent),clock=datetime.utcnow,
        order_id=order_id,approved_minimum=approved_minimum,actor_user_id=actor_user_id,reason=reason)


def atomic_deactivate_series_alias(*, db, Order, Report,
                                   ReadinessSeriesAlias, ResolutionEvent,
                                   order_id, alias_id, actor_user_id, reason):
    return _resolution.atomic_deactivate_series_alias(repository=_repository(db,Order,Report,ReadinessSeriesAlias=ReadinessSeriesAlias,ResolutionEvent=ResolutionEvent),clock=datetime.utcnow,
        order_id=order_id,alias_id=alias_id,actor_user_id=actor_user_id,reason=reason)


def atomic_deactivate_readiness_override(*, db, Order, Report,
                                         CaseReadinessOverride,
                                         ResolutionEvent, order_id,
                                         override_id, actor_user_id, reason):
    return _resolution.atomic_deactivate_readiness_override(repository=_repository(db,Order,Report,CaseReadinessOverride=CaseReadinessOverride,ResolutionEvent=ResolutionEvent),clock=datetime.utcnow,
        order_id=order_id,override_id=override_id,actor_user_id=actor_user_id,reason=reason)

