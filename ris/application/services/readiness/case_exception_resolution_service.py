"""Safe case-exception search and resolution helpers.

The caller owns commit/rollback.  No helper in this module commits a
transaction or changes DICOM content.
"""

import json
import re
from datetime import datetime

from sqlalchemy import or_


TERMINAL_ORDER_STATUSES = {"FINAL", "CANCELLED"}
TERMINAL_REPORT_STATUSES = {"VERIFIED", "FINAL"}
ALLOWED_MATCH_FIELDS = {"DESCRIPTION", "PROTOCOL", "EITHER"}


class CaseExceptionResolutionError(ValueError):
    def __init__(self, code):
        self.code = str(code)
        super().__init__(self.code)


def normalize(value):
    return re.sub(r"[^A-Z0-9]+", " ", str(value or "").upper()).strip()


def latest_report_status(db, Report, order_id):
    row = (db.session.query(Report)
           .filter(Report.order_id == int(order_id))
           .order_by(Report.id.desc()).first())
    return normalize(getattr(row, "status", ""))


def assert_editable(order_status, report_status):
    if normalize(order_status) in TERMINAL_ORDER_STATUSES:
        raise CaseExceptionResolutionError("TERMINAL_CASE_RESOLUTION_LOCKED")
    if normalize(report_status) in TERMINAL_REPORT_STATUSES:
        raise CaseExceptionResolutionError("TERMINAL_REPORT_RESOLUTION_LOCKED")


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


def apply_series_aliases(series, aliases):
    """Return copied PACS evidence enriched with configured canonical names."""
    output = []
    for source in series or []:
        row = dict(source)
        description = str(row.get("description") or "")
        protocol = str(row.get("protocol") or "")
        matched = []
        for alias in aliases or []:
            if not bool(getattr(alias, "active", True)):
                continue
            token = normalize(getattr(alias, "alias_normalized", "") or
                              getattr(alias, "source_alias", ""))
            field = normalize(getattr(alias, "match_field", "EITHER"))
            haystacks = []
            if field in {"DESCRIPTION", "EITHER"}:
                haystacks.append(normalize(description))
            if field in {"PROTOCOL", "EITHER"}:
                haystacks.append(normalize(protocol))
            if token and any(token in value for value in haystacks):
                canonical = normalize(getattr(alias, "canonical_series", ""))
                if canonical and canonical not in matched:
                    matched.append(canonical)
        if matched:
            row["description"] = " ".join([description] + matched).strip()
            row["mapped_series"] = matched
        output.append(row)
    return output


def atomic_series_alias_mapping(*, db, Order, Report, ProcedureQualityRule,
                                ReadinessSeriesAlias, ResolutionEvent,
                                CaseReadiness=None,
                                order_id, source_alias, canonical_series,
                                match_field, actor_user_id, reason):
    order = (db.session.query(Order).filter(Order.id == int(order_id))
             .with_for_update().one())
    assert_editable(order.status, latest_report_status(db, Report, order.id))
    source_alias = str(source_alias or "").strip()
    canonical_series = normalize(canonical_series)
    match_field = normalize(match_field or "EITHER")
    reason = str(reason or "").strip()
    if len(source_alias) < 2:
        raise CaseExceptionResolutionError("SERIES_ALIAS_REQUIRED")
    if len(canonical_series) < 2:
        raise CaseExceptionResolutionError("CANONICAL_SERIES_REQUIRED")
    if match_field not in ALLOWED_MATCH_FIELDS:
        raise CaseExceptionResolutionError("INVALID_SERIES_MATCH_FIELD")
    if len(reason) < 5:
        raise CaseExceptionResolutionError("RESOLUTION_REASON_REQUIRED")

    # A mapping must be grounded in evidence already captured from PACS.
    # This prevents arbitrary text from being used to clear a Series blocker.
    if CaseReadiness is not None:
        readiness = (db.session.query(CaseReadiness)
                     .filter(CaseReadiness.order_id == order.id)
                     .with_for_update().first())
        if readiness is None:
            raise CaseExceptionResolutionError("READINESS_NOT_EVALUATED")
        try:
            evidence = json.loads(readiness.series_evidence_json or "[]")
        except Exception:
            evidence = []
        wanted = normalize(source_alias)
        found = False
        for item in evidence:
            values = []
            if match_field in {"DESCRIPTION", "EITHER"}:
                values.append(item.get("description"))
            if match_field in {"PROTOCOL", "EITHER"}:
                values.append(item.get("protocol"))
            if wanted and any(normalize(value) == wanted for value in values):
                found = True
                break
        if not found:
            raise CaseExceptionResolutionError("SERIES_ALIAS_NOT_IN_PACS_EVIDENCE")

    modality = normalize(order.modality)
    procedure = normalize(order.procedure)
    rules = (db.session.query(ProcedureQualityRule)
             .filter(ProcedureQualityRule.active.is_(True),
                     ProcedureQualityRule.modality == modality)
             .with_for_update().all())
    matches = [row for row in rules
               if normalize(row.procedure_pattern) in procedure]
    if not matches:
        raise CaseExceptionResolutionError("QUALITY_RULE_NOT_FOUND")
    rule = sorted(matches, key=lambda row: len(normalize(row.procedure_pattern)),
                  reverse=True)[0]
    required = {normalize(x) for group in str(rule.required_series or "").split(",")
                for x in group.split("/") if normalize(x)}
    if canonical_series not in required:
        raise CaseExceptionResolutionError("CANONICAL_SERIES_NOT_REQUIRED_BY_RULE")

    alias_normalized = normalize(source_alias)
    row = (db.session.query(ReadinessSeriesAlias)
           .filter(ReadinessSeriesAlias.rule_id == rule.id,
                   ReadinessSeriesAlias.alias_normalized == alias_normalized,
                   ReadinessSeriesAlias.match_field == match_field)
           .with_for_update().first())
    action = "UPDATED" if row is not None else "CREATED"
    old_value = getattr(row, "canonical_series", "") if row else ""
    if row is None:
        row = ReadinessSeriesAlias(rule_id=rule.id,
                                   source_alias=source_alias[:255],
                                   alias_normalized=alias_normalized[:255],
                                   match_field=match_field)
        db.session.add(row)
    row.source_alias = source_alias[:255]
    row.canonical_series = canonical_series[:120]
    row.active = True
    row.created_by = actor_user_id
    row.reason = reason[:500]
    row.created_at = datetime.utcnow()
    db.session.add(ResolutionEvent(
        order_id=order.id, action="SERIES_ALIAS_MAPPING",
        blocker="MISSING_SERIES", old_value=str(old_value or "")[:500],
        new_value=f"{source_alias} => {canonical_series}"[:500],
        reason=reason[:500], actor_user_id=actor_user_id,
    ))
    db.session.flush()
    return {"alias": row, "rule": rule, "action": action}


def atomic_add_clinical_history(*, db, Order, Report, ClinicalNote,
                                ResolutionEvent, order_id, text_value,
                                actor_user_id, reason):
    order = (db.session.query(Order).filter(Order.id == int(order_id))
             .with_for_update().one())
    assert_editable(order.status, latest_report_status(db, Report, order.id))
    text_value = str(text_value or "").strip()
    reason = str(reason or "").strip()
    if len(text_value) < 3:
        raise CaseExceptionResolutionError("CLINICAL_HISTORY_REQUIRED")
    if len(reason) < 5:
        raise CaseExceptionResolutionError("RESOLUTION_REASON_REQUIRED")
    note = ClinicalNote(order_id=order.id, author_user_id=actor_user_id,
                        note_type="HISTORY", visibility="CLINICAL_TEAM",
                        text=text_value)
    db.session.add(note)
    db.session.add(ResolutionEvent(
        order_id=order.id, action="CLINICAL_HISTORY_ADDED",
        blocker="MISSING_HISTORY", old_value="MISSING",
        new_value="PRESENT", reason=reason[:500],
        actor_user_id=actor_user_id,
    ))
    db.session.flush()
    return note


def atomic_image_minimum_override(*, db, Order, Report, CaseReadiness,
                                  CaseReadinessOverride, ResolutionEvent,
                                  order_id, approved_minimum,
                                  actor_user_id, reason):
    order = (db.session.query(Order).filter(Order.id == int(order_id))
             .with_for_update().one())
    assert_editable(order.status, latest_report_status(db, Report, order.id))
    readiness = (db.session.query(CaseReadiness)
                 .filter(CaseReadiness.order_id == order.id)
                 .with_for_update().first())
    if readiness is None:
        raise CaseExceptionResolutionError("READINESS_NOT_EVALUATED")
    try:
        approved_minimum = int(approved_minimum)
    except Exception:
        raise CaseExceptionResolutionError("INVALID_APPROVED_MINIMUM")
    current_images = max(0, int(readiness.image_count or 0))
    rule_minimum = max(0, int(readiness.expected_min_images or 0))
    reason = str(reason or "").strip()
    if current_images < 1:
        raise CaseExceptionResolutionError("PACS_IMAGES_REQUIRED")
    if approved_minimum < 1 or approved_minimum > current_images:
        raise CaseExceptionResolutionError("APPROVED_MINIMUM_MUST_NOT_EXCEED_CURRENT_IMAGES")
    if len(reason) < 10:
        raise CaseExceptionResolutionError("DETAILED_OVERRIDE_REASON_REQUIRED")

    previous = (db.session.query(CaseReadinessOverride)
                .filter(CaseReadinessOverride.order_id == order.id,
                        CaseReadinessOverride.blocker == "INCOMPLETE_IMAGES",
                        CaseReadinessOverride.active.is_(True))
                .with_for_update().first())
    if previous:
        previous.active = False
        previous.deactivated_at = datetime.utcnow()
        db.session.flush()
    row = CaseReadinessOverride(
        order_id=order.id, blocker="INCOMPLETE_IMAGES",
        override_value=str(approved_minimum), active=True,
        reason=reason[:500], actor_user_id=actor_user_id,
    )
    db.session.add(row)
    db.session.add(ResolutionEvent(
        order_id=order.id, action="IMAGE_MINIMUM_OVERRIDE",
        blocker="INCOMPLETE_IMAGES", old_value=str(rule_minimum),
        new_value=str(approved_minimum), reason=reason[:500],
        actor_user_id=actor_user_id,
    ))
    db.session.flush()
    return row


def atomic_deactivate_series_alias(*, db, Order, Report,
                                   ReadinessSeriesAlias, ResolutionEvent,
                                   order_id, alias_id, actor_user_id, reason):
    order = (db.session.query(Order).filter(Order.id == int(order_id))
             .with_for_update().one())
    assert_editable(order.status, latest_report_status(db, Report, order.id))
    reason = str(reason or "").strip()
    if len(reason) < 5:
        raise CaseExceptionResolutionError("RESOLUTION_REASON_REQUIRED")
    row = (db.session.query(ReadinessSeriesAlias)
           .filter(ReadinessSeriesAlias.id == int(alias_id))
           .with_for_update().one())
    if not row.active:
        return {"alias": row, "action": "IDEMPOTENT"}
    row.active = False
    db.session.add(ResolutionEvent(
        order_id=order.id, action="SERIES_ALIAS_DEACTIVATED",
        blocker="MISSING_SERIES", old_value=str(row.source_alias)[:500],
        new_value="INACTIVE", reason=reason[:500],
        actor_user_id=actor_user_id,
    ))
    db.session.flush()
    return {"alias": row, "action": "DEACTIVATED"}


def atomic_deactivate_readiness_override(*, db, Order, Report,
                                         CaseReadinessOverride,
                                         ResolutionEvent, order_id,
                                         override_id, actor_user_id, reason):
    order = (db.session.query(Order).filter(Order.id == int(order_id))
             .with_for_update().one())
    assert_editable(order.status, latest_report_status(db, Report, order.id))
    reason = str(reason or "").strip()
    if len(reason) < 5:
        raise CaseExceptionResolutionError("RESOLUTION_REASON_REQUIRED")
    row = (db.session.query(CaseReadinessOverride)
           .filter(CaseReadinessOverride.id == int(override_id),
                   CaseReadinessOverride.order_id == order.id)
           .with_for_update().one())
    if not row.active:
        return {"override": row, "action": "IDEMPOTENT"}
    row.active = False
    row.deactivated_at = datetime.utcnow()
    db.session.add(ResolutionEvent(
        order_id=order.id, action="READINESS_OVERRIDE_DEACTIVATED",
        blocker=str(row.blocker or "")[:80],
        old_value=str(row.override_value or "")[:500], new_value="INACTIVE",
        reason=reason[:500], actor_user_id=actor_user_id,
    ))
    db.session.flush()
    return {"override": row, "action": "DEACTIVATED"}
