"""
RadBridge Unified Report Commit Core.

This module contains editor-independent safety primitives.

Editors are transport mechanisms only:
BROWSER / WORD / ONLYOFFICE / UPLOAD / LIBREOFFICE

No editor owns a separate clinical report.
"""

import hashlib
import uuid
from pathlib import Path

from report_storage_safety import (
    version_artifact_path,
    assert_new_version_target,
    create_secure_directory,
)

from report_version_safety import (
    ReportSafetyError,
    ReportVersionConflict,
    DuplicateReportVersion,
    normalize_editor_type,
)


class ReportCommitError(ReportSafetyError):
    pass


class ReportCommitRetry(ReportCommitError):
    pass


def new_commit_id():
    return str(uuid.uuid4())


def normalize_commit_id(value=None):
    """
    A client may reuse the same commit_id after a timeout.
    This allows the application layer to make retries idempotent.
    """

    if not value:
        return new_commit_id()

    try:
        return str(uuid.UUID(str(value)))
    except Exception as exc:
        raise ReportCommitError(
            "INVALID_COMMIT_ID"
        ) from exc


def sha256_file(path):
    h = hashlib.sha256()

    with open(path, "rb") as fh:
        for chunk in iter(
            lambda: fh.read(1024 * 1024),
            b""
        ):
            h.update(chunk)

    return h.hexdigest()


def validate_commit_identity(
    *,
    patient_db_id,
    order_patient_db_id,
    accession,
    expected_accession,
):
    """
    Database identity gate.

    Never commit an artifact if patient/order/accession
    context does not exactly match.
    """

    if int(patient_db_id) != int(
        order_patient_db_id
    ):
        raise ReportCommitError(
            "REPORT_PATIENT_CONTEXT_MISMATCH"
        )

    if str(accession) != str(
        expected_accession
    ):
        raise ReportCommitError(
            "REPORT_ACCESSION_CONTEXT_MISMATCH"
        )

    return True


def validate_base_version(
    *,
    current_version_no,
    base_version_no,
):
    """
    Optimistic concurrency gate.

    Example:
      Word opens v3.
      ONLYOFFICE creates v4.
      Word must NOT overwrite from v3.
    """

    if base_version_no is None:
        raise ReportVersionConflict(
            "BASE_VERSION_REQUIRED"
        )

    if int(base_version_no) != int(
        current_version_no
    ):
        raise ReportVersionConflict(
            "REPORT_VERSION_CONFLICT"
        )

    return True


def allocate_next_version(
    current_version_no
):
    value = int(
        current_version_no or 0
    ) + 1

    if value <= 0:
        raise ReportCommitError(
            "INVALID_NEXT_VERSION"
        )

    return value


def validate_duplicate_content(
    *,
    incoming_hash,
    existing_hashes,
):
    incoming = str(
        incoming_hash or ""
    ).lower().strip()

    if not incoming:
        raise ReportCommitError(
            "REPORT_HASH_REQUIRED"
        )

    for existing in existing_hashes or []:
        if incoming == str(
            existing or ""
        ).lower().strip():

            raise DuplicateReportVersion(
                "REPORT_CONTENT_ALREADY_EXISTS"
            )

    return True


def prepare_immutable_target(
    *,
    report_root,
    patient,
    order,
    version_no,
    extension,
):
    """
    Calculates the canonical version path.

    Does NOT overwrite an existing clinical artifact.
    """

    target = version_artifact_path(
        report_root,
        patient,
        order,
        version_no,
        extension,
    )

    create_secure_directory(
        target.parent
    )

    assert_new_version_target(
        target
    )

    return Path(target)


def build_commit_plan(
    *,
    report_root,
    patient,
    order,
    current_version_no,
    base_version_no,
    editor_type,
    incoming_hash,
    existing_hashes,
    extension="docx",
    commit_id=None,
):
    """
    Pure safety/planning layer.

    The application transaction will:
      SELECT report FOR UPDATE
      re-read current version
      call this planner
      create immutable artifact
      INSERT ReportVersion
      COMMIT

    The DB unique constraint remains the final
    protection against concurrent version allocation.
    """

    editor = normalize_editor_type(
        editor_type
    )

    validate_commit_identity(
        patient_db_id=patient.id,
        order_patient_db_id=order.patient_id,
        accession=order.accession,
        expected_accession=order.accession,
    )

    validate_base_version(
        current_version_no=current_version_no,
        base_version_no=base_version_no,
    )

    validate_duplicate_content(
        incoming_hash=incoming_hash,
        existing_hashes=existing_hashes,
    )

    version_no = allocate_next_version(
        current_version_no
    )

    target = prepare_immutable_target(
        report_root=report_root,
        patient=patient,
        order=order,
        version_no=version_no,
        extension=extension,
    )

    return {
        "commit_id": normalize_commit_id(
            commit_id
        ),
        "editor_type": editor,
        "base_version_no": int(
            base_version_no
        ),
        "version_no": version_no,
        "sha256": incoming_hash,
        "artifact_path": str(target),
    }


def is_retry_of_existing_commit(
    *,
    commit_id,
    existing_commit_ids,
):
    """
    Network retry protection.

    True means:
      this request was already committed;
      return the existing result instead of
      creating another version.
    """

    cid = normalize_commit_id(
        commit_id
    )

    known = {
        str(x)
        for x in (
            existing_commit_ids or []
        )
        if x
    }

    return cid in known
