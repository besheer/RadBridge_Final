import hashlib
import io
import zipfile


class ReportSafetyError(Exception):
    code = "REPORT_SAFETY_ERROR"


class ReportVersionConflict(ReportSafetyError):
    code = "REPORT_VERSION_CONFLICT"


class InvalidReportDocument(ReportSafetyError):
    code = "REPORT_DOCUMENT_INVALID"


class DuplicateReportVersion(ReportSafetyError):
    code = "REPORT_VERSION_DUPLICATE"


class ReportImmutable(ReportSafetyError):
    code = "REPORT_IMMUTABLE"


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def validate_docx_bytes(data):
    if not data:
        raise InvalidReportDocument("Document is empty")

    if len(data) < 100:
        raise InvalidReportDocument("Document is too small")

    try:
        z = zipfile.ZipFile(io.BytesIO(data))
    except Exception as exc:
        raise InvalidReportDocument(
            "Invalid DOCX/ZIP container"
        ) from exc

    required = {
        "[Content_Types].xml",
        "word/document.xml",
    }

    names = set(z.namelist())

    missing = required - names

    if missing:
        raise InvalidReportDocument(
            "DOCX structure incomplete: " +
            ",".join(sorted(missing))
        )

    return {
        "sha256": sha256_bytes(data),
        "size": len(data),
    }


def assert_base_version(current_version, supplied_base):
    if supplied_base is None:
        return

    try:
        supplied_base = int(supplied_base)
    except Exception:
        raise ReportVersionConflict(
            "Invalid base version"
        )

    if int(current_version or 0) != supplied_base:
        raise ReportVersionConflict(
            "A newer report version already exists"
        )


def assert_report_editable(status):
    status = (status or "").upper()

    if status in ("FINAL", "FINALIZED"):
        raise ReportImmutable(
            "Finalized report cannot be overwritten"
        )


def next_version(current_version):
    return int(current_version or 0) + 1


VALID_EDITOR_TYPES = {
    "BROWSER",
    "WORD",
    "ONLYOFFICE",
    "UPLOAD",
    "LIBREOFFICE",
}


def normalize_editor_type(value):
    value = str(value or "").strip().upper()

    if value not in VALID_EDITOR_TYPES:
        raise ReportSafetyError(
            "Unsupported report editor type"
        )

    return value


def decide_report_commit(
    *,
    current_version,
    base_version,
    report_status,
    editor_type,
    incoming_hash=None,
    current_hash=None,
):
    """
    Pure decision layer.

    IMPORTANT:
    - No database writes.
    - No filesystem writes.
    - No report mutation.
    - Endpoints are NOT connected here.

    Returns the next safe action only.
    """

    editor_type = normalize_editor_type(editor_type)

    assert_report_editable(report_status)

    # Every real editor must save against the version it opened.
    if base_version is None:
        raise ReportVersionConflict(
            "base_version is required"
        )

    assert_base_version(
        current_version,
        base_version,
    )

    incoming_hash = (
        str(incoming_hash or "").strip().lower()
    )

    current_hash = (
        str(current_hash or "").strip().lower()
    )

    if (
        incoming_hash
        and current_hash
        and incoming_hash == current_hash
    ):
        raise DuplicateReportVersion(
            "Identical content already exists"
        )

    return {
        "action": "CREATE_VERSION",
        "version_no": next_version(current_version),
        "base_version": int(base_version),
        "editor_type": editor_type,
        "status": "DRAFT",
        "authoritative": False,
    }


def choose_authoritative_verified(versions):
    """
    Select the newest VERIFIED version only.

    A newer DRAFT must never become clinically authoritative.
    """

    verified = []

    for item in versions or []:
        status = str(
            item.get("status") or ""
        ).upper()

        if status == "VERIFIED":
            verified.append(item)

    if not verified:
        return None

    return max(
        verified,
        key=lambda x: int(x.get("version_no") or 0)
    )


def normalize_version_status(value):
    value = str(value or "DRAFT").strip().upper()

    allowed = {
        "DRAFT",
        "PARTIAL",
        "VERIFIED",
        "SECOND_VERIFIED",
        "FINALIZED",
        "AMENDED",
    }

    if value not in allowed:
        raise ReportSafetyError(
            "Unsupported report version status"
        )

    return value


def is_clinically_authoritative(status):
    """
    VERIFIED is the clinical authority boundary.

    FINALIZED is a delivery/locking state and is also authoritative.
    DRAFT/PARTIAL are never authoritative.
    """
    status = normalize_version_status(status)

    return status in {
        "VERIFIED",
        "SECOND_VERIFIED",
        "FINALIZED",
    }


def authoritative_version_from_rows(rows):
    """
    Choose newest clinically authoritative version.

    Newer DRAFT/PARTIAL versions must never replace the
    last verified clinical report.
    """

    candidates = []

    for row in rows or []:
        status = normalize_version_status(
            row.get("status") or "DRAFT"
        )

        if is_clinically_authoritative(status):
            candidates.append(row)

    if not candidates:
        return None

    return max(
        candidates,
        key=lambda x: int(x.get("version_no") or 0)
    )


def validate_version_commit_request(
    *,
    current_version,
    base_version,
    report_status,
    editor_type,
    requested_status,
    incoming_hash=None,
    current_hash=None,
):
    """
    Single decision point for all report editors.

    This function does not write to DB/filesystem.
    """

    requested_status = normalize_version_status(
        requested_status
    )

    decision = decide_report_commit(
        current_version=current_version,
        base_version=base_version,
        report_status=report_status,
        editor_type=editor_type,
        incoming_hash=incoming_hash,
        current_hash=current_hash,
    )

    decision["status"] = requested_status
    decision["authoritative"] = \
        is_clinically_authoritative(requested_status)

    return decision


def strict_authoritative_verified(rows):
    """
    Clinical source of truth:
    ONLY VERIFIED versions qualify.

    Finalization is workflow locking metadata,
    not another clinical-content status.
    """

    candidates = []

    for row in rows or []:
        status = str(
            row.get("status") or ""
        ).strip().upper()

        if status == "VERIFIED":
            candidates.append(row)

    if not candidates:
        return None

    return max(
        candidates,
        key=lambda x: int(
            x.get("version_no") or 0
        )
    )


def assert_authoritative_for_delivery(
    version,
    authoritative_version,
):
    """
    Blocks print/download/delivery of:
      - Draft
      - Partial
      - stale Verified version
      - wrong version
    """

    if not version:
        raise ReportSafetyError(
            "REPORT_VERSION_REQUIRED"
        )

    if not authoritative_version:
        raise ReportSafetyError(
            "NO_VERIFIED_REPORT_AVAILABLE"
        )

    status = str(
        version.get("status") or ""
    ).upper()

    if status != "VERIFIED":
        raise ReportSafetyError(
            "NON_VERIFIED_REPORT_BLOCKED"
        )

    if int(version.get("id") or 0) != int(
        authoritative_version.get("id") or 0
    ):
        raise ReportSafetyError(
            "STALE_VERIFIED_VERSION_BLOCKED"
        )

    return True


def assert_no_duplicate_hash(
    incoming_hash,
    existing_hashes,
):
    """
    Same report content must not create
    another version from another editor.
    """

    incoming_hash = str(
        incoming_hash or ""
    ).strip().lower()

    if not incoming_hash:
        return True

    known = {
        str(x or "").strip().lower()
        for x in (existing_hashes or [])
        if str(x or "").strip()
    }

    if incoming_hash in known:
        raise DuplicateReportVersion(
            "Identical report content already exists"
        )

    return True
