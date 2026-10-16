"""
RadBridge Unified Report Commit Core.

This module contains editor-independent safety primitives.

Editors are transport mechanisms only:
BROWSER / WORD / ONLYOFFICE / UPLOAD / LIBREOFFICE

No editor owns a separate clinical report.
"""

import hashlib
from domain.reporting.commit_policy import (
    ReportCommitError, ReportCommitRetry, new_commit_id, normalize_commit_id,
    validate_commit_identity, validate_base_version, allocate_next_version,
    validate_duplicate_content, is_retry_of_existing_commit,
)
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










def sha256_file(path):
    h = hashlib.sha256()

    with open(path, "rb") as fh:
        for chunk in iter(
            lambda: fh.read(1024 * 1024),
            b""
        ):
            h.update(chunk)

    return h.hexdigest()










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
