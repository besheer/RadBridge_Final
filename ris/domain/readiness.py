"""Pure case-readiness policy helpers.  This module never touches the DB."""

import hashlib
import json
import re


def _norm(value):
    return re.sub(r"[^A-Z0-9]+", " ", str(value or "").upper()).strip()


def required_series_groups(value):
    groups = []
    for item in str(value or "").split(","):
        alternatives = [_norm(x) for x in item.split("/") if _norm(x)]
        if alternatives:
            groups.append(alternatives)
    return groups


def evaluate_required_series(required, series):
    evidence = []
    searchable = []
    for row in series or []:
        item = {
            "series_id": str(row.get("series_id") or ""),
            "description": str(row.get("description") or ""),
            "protocol": str(row.get("protocol") or ""),
            "modality": str(row.get("modality") or ""),
            "instance_count": int(row.get("instance_count") or 0),
        }
        evidence.append(item)
        searchable.append(_norm(" ".join([
            item["description"], item["protocol"], item["modality"]
        ])))

    missing = []
    for alternatives in required_series_groups(required):
        if not any(any(token in text for text in searchable) for token in alternatives):
            missing.append("/".join(alternatives))
    return evidence, missing


def evaluate_readiness(*, image_count, min_images, warning_images,
                       require_pacs, pacs_present, require_history,
                       history_present, require_attachments,
                       attachment_count, required_series, series):
    image_count = max(0, int(image_count or 0))
    min_images = max(0, int(min_images or 0))
    warning_images = max(0, int(warning_images or 0))
    evidence, missing_series = evaluate_required_series(required_series, series)
    flags = {
        "missing_pacs": bool(require_pacs and not pacs_present),
        "missing_history": bool(require_history and not history_present),
        "missing_attachments": bool(require_attachments and int(attachment_count or 0) < 1),
        "incomplete_images": bool(min_images and image_count < min_images),
        "missing_series": bool(missing_series),
    }
    blockers = [name.upper() for name, active in flags.items() if active]
    status = "BLOCKED" if blockers else (
        "WARNING" if warning_images and image_count < warning_images else "READY"
    )
    score = max(0, 100 - 20 * len(blockers))
    details = {
        "image_count": image_count,
        "min_images": min_images,
        "warning_images": warning_images,
        "required_series": str(required_series or ""),
        "missing_required_series": missing_series,
        "series": evidence,
        "blockers": blockers,
    }
    signature = hashlib.sha256(json.dumps(details, sort_keys=True).encode()).hexdigest()
    return {"status": status, "score": score, "flags": flags,
            "details": details, "facts_sha256": signature}
