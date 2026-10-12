from pathlib import Path
import os
import re


class ReportStorageError(Exception):
    pass


def safe_token(value):
    value = str(value or "").strip()

    # No path separators / traversal / dangerous characters.
    value = re.sub(
        r"[^A-Za-z0-9_.-]+",
        "_",
        value
    )

    value = value.strip("._-")

    if not value:
        raise ReportStorageError(
            "Unsafe or empty storage token"
        )

    if value in (".", ".."):
        raise ReportStorageError(
            "Unsafe storage token"
        )

    return value


def patient_folder_name(patient):
    """
    Canonical identity:
        PATIENT_ID__DBID

    Example:
        RBTEST-001__4
    """

    if not patient:
        raise ReportStorageError(
            "Patient is required"
        )

    patient_id = safe_token(
        getattr(patient, "patient_id", "")
    )

    dbid = int(
        getattr(patient, "id", 0) or 0
    )

    if dbid <= 0:
        raise ReportStorageError(
            "Patient DB ID is required"
        )

    return f"{patient_id}__{dbid}"


def accession_folder_name(order):
    if not order:
        raise ReportStorageError(
            "Order is required"
        )

    return safe_token(
        getattr(order, "accession", "")
    )


def _inside_root(root, target):
    root = Path(root).resolve()
    target = Path(target).resolve()

    try:
        target.relative_to(root)
    except ValueError:
        raise ReportStorageError(
            "Storage path escaped report root"
        )

    return target


def canonical_case_paths(
    report_root,
    patient,
    order,
):
    """
    /report-files/
      PATIENT_ID__DBID/
        documents/
        reports/
          ACCESSION/
            versions/
            working/
    """

    root = Path(report_root).resolve()

    patient_root = root / patient_folder_name(
        patient
    )

    documents = patient_root / "documents"

    case_root = (
        patient_root
        / "reports"
        / accession_folder_name(order)
    )

    versions = case_root / "versions"
    working = case_root / "working"

    for path in (
        patient_root,
        documents,
        case_root,
        versions,
        working,
    ):
        _inside_root(root, path)

    return {
        "root": root,
        "patient_root": patient_root,
        "documents": documents,
        "case_root": case_root,
        "versions": versions,
        "working": working,
    }


def version_directory(
    report_root,
    patient,
    order,
    version_no,
):
    version_no = int(version_no)

    if version_no <= 0:
        raise ReportStorageError(
            "Invalid report version"
        )

    paths = canonical_case_paths(
        report_root,
        patient,
        order,
    )

    target = (
        paths["versions"]
        / f"v{version_no:03d}"
    )

    return _inside_root(
        paths["root"],
        target
    )


def version_artifact_path(
    report_root,
    patient,
    order,
    version_no,
    ext="docx",
):
    ext = safe_token(
        str(ext or "").lower().lstrip(".")
    )

    if ext not in (
        "docx",
        "pdf",
        "odt",
    ):
        raise ReportStorageError(
            "Unsupported report artifact type"
        )

    folder = version_directory(
        report_root,
        patient,
        order,
        version_no,
    )

    return folder / f"report.{ext}"


def working_artifact_path(
    report_root,
    patient,
    order,
    editor_type,
    ext="docx",
):
    paths = canonical_case_paths(
        report_root,
        patient,
        order,
    )

    editor = safe_token(
        str(editor_type or "").upper()
    )

    ext = safe_token(
        str(ext or "").lower().lstrip(".")
    )

    target = (
        paths["working"]
        / editor
        / f"working.{ext}"
    )

    return _inside_root(
        paths["root"],
        target
    )


def assert_new_version_target(path):
    """
    Clinical versions are immutable.
    Existing artifact must never be overwritten.
    """

    path = Path(path)

    if path.exists():
        raise ReportStorageError(
            "Clinical version artifact already exists"
        )


def create_secure_directory(path):
    path = Path(path)

    path.mkdir(
        parents=True,
        exist_ok=True
    )

    try:
        os.chmod(path, 0o750)
    except Exception:
        pass

    return path
