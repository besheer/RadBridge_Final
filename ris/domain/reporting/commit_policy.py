"""Editor-independent report identity, version and retry policy; no I/O."""
import uuid
from domain.reporting.content import ReportSafetyError, ReportVersionConflict, DuplicateReportVersion

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
