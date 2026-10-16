"""Safe case-exception search and resolution helpers.

The caller owns commit/rollback.  No helper in this module commits a
transaction or changes DICOM content.
"""

import json
import re
from datetime import datetime

from application.services.readiness import order_search as _order_search
from infrastructure.adapters.readiness.search_repository import SqlAlchemyReadinessSearchRepository


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
    return _order_search.search_ris_orders(
        repository=SqlAlchemyReadinessSearchRepository(Order.query.session, Order, Patient),
        query=query, limit=limit)




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
