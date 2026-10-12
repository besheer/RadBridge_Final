"""Readiness resolutions over supplied persistence and clock dependencies.

Caller owns commit/rollback. No operation changes DICOM data or clinical reports.
"""
import json
from domain.readiness_resolution import (
    CaseExceptionResolutionError, normalize, assert_editable, ALLOWED_MATCH_FIELDS,
)

def atomic_series_alias_mapping(*, repository, clock, order_id, source_alias, canonical_series, match_field, actor_user_id, reason):
    order = (repository.lock_order(order_id))
    assert_editable(order.status, normalize(repository.latest_report_status(order.id)))
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
    if repository.has_readiness:
        readiness = (repository.lock_readiness(order.id))
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
    rules = (repository.lock_quality_rules(modality))
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
    row = (repository.lock_alias_key(rule.id, alias_normalized, match_field))
    action = "UPDATED" if row is not None else "CREATED"
    old_value = getattr(row, "canonical_series", "") if row else ""
    if row is None:
        row = repository.create_alias(rule_id=rule.id,
                                   source_alias=source_alias[:255],
                                   alias_normalized=alias_normalized[:255],
                                   match_field=match_field)
        repository.add(row)
    row.source_alias = source_alias[:255]
    row.canonical_series = canonical_series[:120]
    row.active = True
    row.created_by = actor_user_id
    row.reason = reason[:500]
    row.created_at = clock()
    repository.add(repository.create_event(
        order_id=order.id, action="SERIES_ALIAS_MAPPING",
        blocker="MISSING_SERIES", old_value=str(old_value or "")[:500],
        new_value=f"{source_alias} => {canonical_series}"[:500],
        reason=reason[:500], actor_user_id=actor_user_id,
    ))
    repository.flush()
    return {"alias": row, "rule": rule, "action": action}


def atomic_add_clinical_history(*, repository, clock, order_id, text_value, actor_user_id, reason):
    order = (repository.lock_order(order_id))
    assert_editable(order.status, normalize(repository.latest_report_status(order.id)))
    text_value = str(text_value or "").strip()
    reason = str(reason or "").strip()
    if len(text_value) < 3:
        raise CaseExceptionResolutionError("CLINICAL_HISTORY_REQUIRED")
    if len(reason) < 5:
        raise CaseExceptionResolutionError("RESOLUTION_REASON_REQUIRED")
    note = repository.create_note(order_id=order.id, author_user_id=actor_user_id,
                        note_type="HISTORY", visibility="CLINICAL_TEAM",
                        text=text_value)
    repository.add(note)
    repository.add(repository.create_event(
        order_id=order.id, action="CLINICAL_HISTORY_ADDED",
        blocker="MISSING_HISTORY", old_value="MISSING",
        new_value="PRESENT", reason=reason[:500],
        actor_user_id=actor_user_id,
    ))
    repository.flush()
    return note


def atomic_image_minimum_override(*, repository, clock, order_id, approved_minimum, actor_user_id, reason):
    order = (repository.lock_order(order_id))
    assert_editable(order.status, normalize(repository.latest_report_status(order.id)))
    readiness = (repository.lock_readiness(order.id))
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

    previous = (repository.lock_active_override(order.id))
    if previous:
        previous.active = False
        previous.deactivated_at = clock()
        repository.flush()
    row = repository.create_override(
        order_id=order.id, blocker="INCOMPLETE_IMAGES",
        override_value=str(approved_minimum), active=True,
        reason=reason[:500], actor_user_id=actor_user_id,
    )
    repository.add(row)
    repository.add(repository.create_event(
        order_id=order.id, action="IMAGE_MINIMUM_OVERRIDE",
        blocker="INCOMPLETE_IMAGES", old_value=str(rule_minimum),
        new_value=str(approved_minimum), reason=reason[:500],
        actor_user_id=actor_user_id,
    ))
    repository.flush()
    return row


def atomic_deactivate_series_alias(*, repository, clock, order_id, alias_id, actor_user_id, reason):
    order = (repository.lock_order(order_id))
    assert_editable(order.status, normalize(repository.latest_report_status(order.id)))
    reason = str(reason or "").strip()
    if len(reason) < 5:
        raise CaseExceptionResolutionError("RESOLUTION_REASON_REQUIRED")
    row = (repository.lock_alias_id(alias_id))
    if not row.active:
        return {"alias": row, "action": "IDEMPOTENT"}
    row.active = False
    repository.add(repository.create_event(
        order_id=order.id, action="SERIES_ALIAS_DEACTIVATED",
        blocker="MISSING_SERIES", old_value=str(row.source_alias)[:500],
        new_value="INACTIVE", reason=reason[:500],
        actor_user_id=actor_user_id,
    ))
    repository.flush()
    return {"alias": row, "action": "DEACTIVATED"}


def atomic_deactivate_readiness_override(*, repository, clock, order_id, override_id, actor_user_id, reason):
    order = (repository.lock_order(order_id))
    assert_editable(order.status, normalize(repository.latest_report_status(order.id)))
    reason = str(reason or "").strip()
    if len(reason) < 5:
        raise CaseExceptionResolutionError("RESOLUTION_REASON_REQUIRED")
    row = (repository.lock_override_id(order.id, override_id))
    if not row.active:
        return {"override": row, "action": "IDEMPOTENT"}
    row.active = False
    row.deactivated_at = clock()
    repository.add(repository.create_event(
        order_id=order.id, action="READINESS_OVERRIDE_DEACTIVATED",
        blocker=str(row.blocker or "")[:80],
        old_value=str(row.override_value or "")[:500], new_value="INACTIVE",
        reason=reason[:500], actor_user_id=actor_user_id,
    ))
    repository.flush()
    return {"override": row, "action": "DEACTIVATED"}

