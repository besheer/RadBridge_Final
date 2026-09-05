"""Atomic PACS/RIS linking. The caller owns commit/rollback."""

from datetime import datetime

from pacs_resolution_policy import (
    PacsResolutionPolicyError,
    assert_exam_link_allowed,
    assert_exam_unlink_allowed,
    assert_primary_link_allowed,
    normalize,
)


def latest_report_status(db, Report, order_id):
    row = (db.session.query(Report)
           .filter(Report.order_id == order_id)
           .order_by(Report.id.desc()).first())
    return normalize(getattr(row, "status", ""))


def atomic_primary_link(*, db, Order, Report, PacsStudyInbox,
                        PacsStudyMatch, PacsResolutionEvent, order_id,
                        orthanc_study_id, study_instance_uid, image_count,
                        match_method, confidence, actor_user_id, reason,
                        pacs_patient_id="", pacs_patient_name="",
                        pacs_accession="", inbox_state="LINKED"):
    order = (db.session.query(Order).filter(Order.id == order_id)
             .with_for_update().one())
    inbox = (db.session.query(PacsStudyInbox)
             .filter(PacsStudyInbox.orthanc_study_id == orthanc_study_id)
             .with_for_update().one())
    existing = (db.session.query(PacsStudyMatch)
                .filter(PacsStudyMatch.orthanc_study_id == orthanc_study_id)
                .with_for_update().first())
    if existing is not None and existing.order_id != order.id:
        raise PacsResolutionPolicyError("PACS_STUDY_ALREADY_LINKED")

    old_study = normalize(order.pacs_study_id)
    old_uid = normalize(order.study_instance_uid)
    action = assert_primary_link_allowed(
        order_status=order.status,
        report_status=latest_report_status(db, Report, order.id),
        current_study_id=old_study,
        requested_study_id=orthanc_study_id,
    )

    current_rows = (db.session.query(PacsStudyMatch)
                    .filter(PacsStudyMatch.order_id == order.id,
                            PacsStudyMatch.is_current.is_(True))
                    .with_for_update().all())
    if action == "CHANGE":
        for current in current_rows:
            if current.orthanc_study_id == orthanc_study_id:
                continue
            current.is_current = False
            current.superseded_at = datetime.utcnow()
            current.superseded_by = actor_user_id
            current.superseded_reason = normalize(reason)[:500]
            previous = (db.session.query(PacsStudyInbox)
                        .filter(PacsStudyInbox.orthanc_study_id == current.orthanc_study_id)
                        .with_for_update().first())
            if previous is not None and previous.order_id == order.id:
                previous.state = "SUPERSEDED"

    match = existing or PacsStudyMatch(
        orthanc_study_id=orthanc_study_id, order_id=order.id)
    if existing is None:
        db.session.add(match)
    match.order_id = order.id
    match.is_current = True
    match.match_method = normalize(match_method)[:40]
    match.confidence = normalize(confidence)[:20]
    match.pacs_patient_id = normalize(pacs_patient_id)[:80]
    match.pacs_patient_name = normalize(pacs_patient_name)[:180]
    match.pacs_accession = normalize(pacs_accession)[:120]
    match.confirmed_by = actor_user_id
    match.confirmed_at = datetime.utcnow()
    match.notes = normalize(reason)[:500]

    inbox.order_id = order.id
    inbox.state = inbox_state
    inbox.match_method = match.match_method
    inbox.error_text = ""

    order.pacs_study_id = normalize(orthanc_study_id)
    order.study_instance_uid = normalize(study_instance_uid)
    order.pacs_image_count = max(0, int(image_count or 0))
    order.pacs_status = "RECEIVED"
    order.pacs_last_seen_at = datetime.utcnow()
    if action == "CHANGE":
        order.pacs_last_change_at = datetime.utcnow()

    if action == "CHANGE":
        db.session.add(PacsResolutionEvent(
            order_id=order.id, event_type="PRIMARY_LINK_CHANGED",
            old_orthanc_study_id=old_study,
            new_orthanc_study_id=order.pacs_study_id,
            old_study_instance_uid=old_uid,
            new_study_instance_uid=order.study_instance_uid,
            reason=normalize(reason)[:500], actor_user_id=actor_user_id,
        ))
    db.session.flush()
    return {"order": order, "inbox": inbox, "match": match,
            "action": action}


def atomic_exam_link(*, db, Order, Report, PacsExamLink,
                     primary_order_id, secondary_order_id,
                     orthanc_study_id, actor_user_id, reason):
    ids = sorted({int(primary_order_id), int(secondary_order_id)})
    locked = (db.session.query(Order).filter(Order.id.in_(ids))
              .order_by(Order.id).with_for_update().all())
    by_id = {row.id: row for row in locked}
    if len(by_id) != 2:
        raise PacsResolutionPolicyError("EXAM_LINK_ORDER_NOT_FOUND")
    primary, secondary = by_id[int(primary_order_id)], by_id[int(secondary_order_id)]
    if normalize(primary.pacs_study_id) != normalize(orthanc_study_id):
        raise PacsResolutionPolicyError("EXAM_LINK_PRIMARY_STUDY_MISMATCH")
    assert_exam_link_allowed(
        primary_patient_id=primary.patient_id,
        secondary_patient_id=secondary.patient_id,
        secondary_order_status=secondary.status,
        secondary_report_status=latest_report_status(db, Report, secondary.id),
        reason=reason,
    )
    row = (db.session.query(PacsExamLink)
           .filter(PacsExamLink.orthanc_study_id == orthanc_study_id,
                   PacsExamLink.order_id == secondary.id,
                   PacsExamLink.active.is_(True))
           .with_for_update().first())
    if row is not None:
        return {"link": row, "action": "IDEMPOTENT"}
    row = PacsExamLink(orthanc_study_id=orthanc_study_id,
                       order_id=secondary.id, link_role="SECONDARY",
                       active=True, reason=normalize(reason)[:500],
                       created_by=actor_user_id)
    db.session.add(row)
    db.session.flush()
    return {"link": row, "action": "CREATED"}


def atomic_remove_exam_link(*, db, Order, Report, PacsExamLink,
                            link_id, actor_user_id, reason):
    """Deactivate an exam link; the caller owns commit/rollback."""
    row = (db.session.query(PacsExamLink)
           .filter(PacsExamLink.id == int(link_id))
           .with_for_update().first())
    if row is None:
        raise PacsResolutionPolicyError("EXAM_LINK_NOT_FOUND")
    if not row.active:
        return {"link": row, "action": "IDEMPOTENT"}

    order = (db.session.query(Order)
             .filter(Order.id == row.order_id)
             .with_for_update().one())
    assert_exam_unlink_allowed(
        secondary_order_status=order.status,
        secondary_report_status=latest_report_status(db, Report, order.id),
        reason=reason,
    )
    row.active = False
    row.removed_by = actor_user_id
    row.removed_at = datetime.utcnow()
    db.session.flush()
    return {"link": row, "action": "REMOVED"}
