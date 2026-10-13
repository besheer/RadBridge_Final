"""Pure patient-safety helpers for the RadBridge OCR intake workflow."""

from __future__ import annotations

import hashlib
import re
from datetime import date, datetime
from difflib import SequenceMatcher
from typing import Any, Iterable, Mapping


ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
CORE_FIELDS = ("name", "national_id", "phone", "dob", "sex", "address")


def digits(value: Any) -> str:
    return re.sub(r"\D+", "", str(value or "").translate(ARABIC_DIGITS))


def normalize_name(value: Any) -> str:
    text = str(value or "").translate(ARABIC_DIGITS).strip().upper()
    text = re.sub(r"[^A-Z0-9\u0600-\u06FF ]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def normalize_phone(value: Any) -> str:
    value_digits = digits(value)
    if value_digits.startswith("0020"):
        value_digits = value_digits[4:]
    elif value_digits.startswith("20") and len(value_digits) >= 12:
        value_digits = value_digits[2:]
    if len(value_digits) == 10 and value_digits.startswith("1"):
        value_digits = "0" + value_digits
    return value_digits


def normalize_sex(value: Any) -> str:
    text = str(value or "").strip().lower()
    if text in {"m", "male", "ذكر", "رجل", "1"}:
        return "M"
    if text in {"f", "female", "أنثى", "انثى", "سيدة", "2"}:
        return "F"
    return ""


def normalize_dob(value: Any) -> str:
    text = str(value or "").translate(ARABIC_DIGITS).strip()
    if not text:
        return ""
    candidates = ("%Y%m%d", "%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d")
    for pattern in candidates:
        try:
            parsed = datetime.strptime(text, pattern).date()
            if date(1900, 1, 1) <= parsed <= date.today():
                return parsed.strftime("%Y%m%d")
        except ValueError:
            pass
    compact = digits(text)
    if len(compact) == 8:
        try:
            parsed = datetime.strptime(compact, "%Y%m%d").date()
            if date(1900, 1, 1) <= parsed <= date.today():
                return compact
        except ValueError:
            pass
    return compact


def national_id_details(value: Any) -> dict[str, Any]:
    national_id = digits(value)
    result = {
        "value": national_id,
        "valid": False,
        "status": "empty" if not national_id else "invalid",
        "message": "National ID is optional until final review." if not national_id else "National ID must contain 14 valid digits.",
        "dob": "",
        "sex": "",
    }
    if not national_id:
        return result
    if len(national_id) != 14 or national_id[0] not in {"2", "3"}:
        return result
    century = 1900 if national_id[0] == "2" else 2000
    try:
        born = date(century + int(national_id[1:3]), int(national_id[3:5]), int(national_id[5:7]))
    except ValueError:
        result["message"] = "The birth-date segment inside the National ID is invalid."
        return result
    if born > date.today():
        result["message"] = "National ID contains a future birth date."
        return result
    result.update({
        "valid": True,
        "status": "valid",
        "message": "National ID structure and encoded birth date are valid.",
        "dob": born.strftime("%Y%m%d"),
        "sex": "M" if int(national_id[12]) % 2 else "F",
    })
    return result


def normalize_identity(values: Mapping[str, Any]) -> dict[str, str]:
    national_id = national_id_details(values.get("national_id"))
    dob = normalize_dob(values.get("dob")) or national_id["dob"]
    sex = normalize_sex(values.get("sex")) or national_id["sex"]
    return {
        "name": normalize_name(values.get("name") or values.get("patient_name")),
        "national_id": national_id["value"],
        "phone": normalize_phone(values.get("phone")),
        "dob": dob,
        "sex": sex,
        "address": re.sub(r"\s+", " ", str(values.get("address") or "").strip())[:255],
    }


def validate_identity(values: Mapping[str, Any]) -> dict[str, Any]:
    clean = normalize_identity(values)
    fields: dict[str, dict[str, Any]] = {}

    if len(clean["name"]) < 3:
        fields["name"] = {"status": "invalid", "message": "Patient name is required and must be reviewed."}
    elif len(clean["name"]) > 120:
        fields["name"] = {"status": "invalid", "message": "Patient name exceeds the 120-character RIS limit."}
    else:
        fields["name"] = {"status": "valid", "message": "Name is present; confirm it against the identity document."}

    national_id = national_id_details(clean["national_id"])
    if not clean["national_id"]:
        fields["national_id"] = {"status": "warning", "message": "No National ID. Use manual/supervisor review for passport or exceptional registration."}
    else:
        fields["national_id"] = {"status": "valid" if national_id["valid"] else "invalid", "message": national_id["message"]}

    if not clean["phone"]:
        fields["phone"] = {"status": "warning", "message": "Phone is missing; duplicate matching will be weaker."}
    elif re.fullmatch(r"01[0125]\d{8}", clean["phone"]):
        fields["phone"] = {"status": "valid", "message": "Egyptian mobile format is valid."}
    elif 8 <= len(clean["phone"]) <= 15:
        fields["phone"] = {"status": "warning", "message": "Non-mobile number accepted only after manual confirmation."}
    else:
        fields["phone"] = {"status": "invalid", "message": "Phone format is invalid."}

    provided_dob = normalize_dob(values.get("dob"))
    if national_id["valid"] and provided_dob and provided_dob != national_id["dob"]:
        fields["dob"] = {"status": "invalid", "message": "Date of birth conflicts with the National ID."}
    elif not clean["dob"]:
        fields["dob"] = {"status": "warning", "message": "Date of birth is missing."}
    else:
        try:
            parsed = datetime.strptime(clean["dob"], "%Y%m%d").date()
            fields["dob"] = {"status": "valid", "message": f"Validated date: {parsed.isoformat()}."}
        except ValueError:
            fields["dob"] = {"status": "invalid", "message": "Date of birth is invalid."}

    provided_sex = normalize_sex(values.get("sex"))
    if national_id["valid"] and provided_sex and provided_sex != national_id["sex"]:
        fields["sex"] = {"status": "invalid", "message": "Sex conflicts with the National ID encoding."}
    else:
        fields["sex"] = {
            "status": "valid" if clean["sex"] in {"M", "F"} else "warning",
            "message": "Sex is normalized." if clean["sex"] else "Sex is missing; confirm manually.",
        }
    fields["address"] = {"status": "valid" if clean["address"] else "warning", "message": "Address captured." if clean["address"] else "Address is optional."}

    invalid = [key for key, item in fields.items() if item["status"] == "invalid"]
    reliable_identifier = bool(clean["national_id"] and national_id["valid"]) or bool(clean["phone"] and clean["dob"])
    if not reliable_identifier:
        invalid.append("reliable_identifier")
    return {
        "ok": not invalid,
        "normalized": clean,
        "fields": fields,
        "invalid_fields": invalid,
        "reliable_identifier": reliable_identifier,
    }


def _value(patient: Any, key: str) -> Any:
    if isinstance(patient, Mapping):
        return patient.get(key)
    return getattr(patient, key, None)


def _name_similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, normalize_name(a), normalize_name(b)).ratio()


def score_patient_candidates(identity: Mapping[str, Any], patients: Iterable[Any]) -> dict[str, Any]:
    clean = normalize_identity(identity)
    candidates: list[dict[str, Any]] = []
    for patient in patients:
        patient_id = _value(patient, "id")
        p_name = normalize_name(_value(patient, "name"))
        p_nid = digits(_value(patient, "national_id"))
        p_phone = normalize_phone(_value(patient, "phone"))
        p_dob = normalize_dob(_value(patient, "dob"))
        name_similarity = _name_similarity(clean["name"], p_name)
        reasons: list[str] = []
        score = 0
        hard_conflict = False

        if clean["national_id"] and p_nid == clean["national_id"]:
            score = 100
            reasons.append("NATIONAL_ID_EXACT")
            if clean["name"] and p_name and name_similarity < 0.45:
                hard_conflict = True
                reasons.append("NAME_CONFLICT_WITH_NATIONAL_ID")
        elif clean["phone"] and p_phone == clean["phone"] and clean["dob"] and p_dob == clean["dob"]:
            score = 94
            reasons.extend(["PHONE_EXACT", "DOB_EXACT"])
        elif clean["phone"] and p_phone == clean["phone"] and name_similarity >= 0.88:
            score = 90
            reasons.extend(["PHONE_EXACT", "NAME_STRONG"])
        elif clean["dob"] and p_dob == clean["dob"] and name_similarity >= 0.90:
            score = 88
            reasons.extend(["DOB_EXACT", "NAME_STRONG"])
        elif clean["phone"] and p_phone == clean["phone"]:
            score = 72
            reasons.append("PHONE_ONLY")
        elif name_similarity >= 0.94:
            score = 60
            reasons.append("NAME_ONLY")

        if score:
            candidates.append({
                "patient_id": patient_id,
                "patient_code": _value(patient, "patient_id") or "",
                "name": _value(patient, "name") or "",
                "national_id_masked": ("*" * 10 + p_nid[-4:]) if len(p_nid) >= 4 else "",
                "phone_masked": ("*" * max(0, len(p_phone) - 4) + p_phone[-4:]) if p_phone else "",
                "dob": p_dob,
                "score": score,
                "reasons": reasons,
                "hard_conflict": hard_conflict,
                "name_similarity": round(name_similarity, 3),
            })

    candidates.sort(key=lambda item: (-item["score"], str(item["patient_id"])))
    top = candidates[0] if candidates else None
    tied = bool(len(candidates) > 1 and top and candidates[1]["score"] >= top["score"] - 3)
    if top and top["hard_conflict"]:
        resolution = "CONFLICT"
    elif tied and top and top["score"] >= 85:
        resolution = "AMBIGUOUS"
    elif top and top["score"] == 100:
        resolution = "EXACT_MATCH"
    elif top and top["score"] >= 85:
        resolution = "REVIEW_MATCH"
    elif top:
        resolution = "WEAK_MATCH"
    else:
        resolution = "NO_MATCH"
    return {"resolution": resolution, "candidates": candidates, "top": top}


def registration_fingerprint(intake_id: Any, identity: Mapping[str, Any], document_hashes: Iterable[str] = ()) -> str:
    clean = normalize_identity(identity)
    payload = "|".join([
        "SMART_INTAKE",
        str(intake_id),
        clean["national_id"],
        clean["phone"],
        clean["dob"],
        clean["name"],
        *sorted(str(item or "") for item in document_hashes),
    ])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Smart Intake v2 - conservative document classification
# ---------------------------------------------------------------------------

DOCUMENT_CLASSIFICATION_TYPES = (
    "IDENTITY",
    "INSURANCE_CARD",
    "PRESCRIPTION",
    "APPROVAL",
    "PREVIOUS_REPORT",
    "CONSENT",
    "QUESTIONNAIRE",
    "OTHER",
)


def classify_document_text(text: Any) -> dict[str, Any]:
    """
    Conservative text classifier for Smart Intake.

    This function only suggests a document type. A low-confidence or
    ambiguous result MUST remain OTHER until staff review.
    """
    raw = str(text or "")
    normalized = re.sub(r"\s+", " ", raw).upper()

    rules = {
        "IDENTITY": (
            "NATIONAL ID",
            "IDENTITY CARD",
            "ID NUMBER",
            "PASSPORT",
            "الرقم القومي",
            "بطاقة تحقيق الشخصية",
            "بطاقة الرقم القومي",
            "جواز سفر",
        ),
        "INSURANCE_CARD": (
            "INSURANCE",
            "MEMBER ID",
            "MEMBER NUMBER",
            "POLICY NUMBER",
            "POLICY NO",
            "HEALTH CARD",
            "MEDICAL CARD",
            "تأمين",
            "التأمين",
            "رقم العضوية",
            "رقم الوثيقة",
            "كارنيه",
        ),
        "PRESCRIPTION": (
            "PRESCRIPTION",
            "REFERRAL",
            "DIAGNOSIS",
            "CLINICAL HISTORY",
            "REQUESTED EXAM",
            "RADIOLOGY REQUEST",
            "RX",
            "روشتة",
            "تحويل",
            "التشخيص",
            "الفحص المطلوب",
        ),
        "APPROVAL": (
            "APPROVAL",
            "AUTHORIZATION",
            "PREAUTHORIZATION",
            "PRE-AUTHORIZATION",
            "APPROVAL NUMBER",
            "AUTHORIZATION NUMBER",
            "موافقة",
            "رقم الموافقة",
        ),
        "PREVIOUS_REPORT": (
            "RADIOLOGY REPORT",
            "IMAGING REPORT",
            "CT REPORT",
            "MRI REPORT",
            "ULTRASOUND REPORT",
            "X-RAY REPORT",
            "FINDINGS",
            "IMPRESSION",
            "تقرير الأشعة",
            "النتيجة",
        ),
        "CONSENT": (
            "CONSENT",
            "INFORMED CONSENT",
            "PATIENT CONSENT",
            "إقرار",
            "الموافقة المستنيرة",
        ),
        "QUESTIONNAIRE": (
            "QUESTIONNAIRE",
            "SCREENING FORM",
            "PATIENT QUESTIONNAIRE",
            "استبيان",
        ),
    }

    scores = {}
    hits = {}

    for dtype, keywords in rules.items():
        matched = [keyword for keyword in keywords if keyword in normalized]
        hits[dtype] = matched
        scores[dtype] = len(matched)

    ranked = sorted(
        scores.items(),
        key=lambda item: (-item[1], item[0]),
    )

    if not ranked or ranked[0][1] == 0:
        return {
            "type": "OTHER",
            "confidence": 0.0,
            "status": "UNCLASSIFIED",
            "hits": [],
        }

    best_type, best_score = ranked[0]
    second_score = ranked[1][1] if len(ranked) > 1 else 0

    # Deliberately conservative:
    # one generic keyword is not sufficient for automatic classification.
    if best_score < 2:
        confidence = 0.45
        status = "REVIEW_REQUIRED"
        selected = "OTHER"
    elif second_score >= best_score:
        confidence = 0.40
        status = "AMBIGUOUS"
        selected = "OTHER"
    elif second_score == best_score - 1:
        confidence = 0.65
        status = "REVIEW_REQUIRED"
        selected = "OTHER"
    else:
        confidence = min(0.95, 0.70 + (best_score * 0.05))
        status = "SUGGESTED"
        selected = best_type

    return {
        "type": selected,
        "suggested_type": best_type,
        "confidence": round(confidence, 3),
        "status": status,
        "hits": hits.get(best_type, [])[:10],
    }
