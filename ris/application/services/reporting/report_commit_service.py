"""Clinical report commit orchestration over explicit persistence/artifact ports.

The caller commits the database transaction. This service flushes under its row
lock and compensates its own newly published artifact on a failed flush.
"""
from datetime import datetime
from domain.reporting.content import ReportVersionConflict
from domain.reporting.commit_policy import (
    normalize_commit_id, validate_commit_identity, validate_base_version,
    validate_duplicate_content,
)
from application.services.reporting.commit_errors import (
    TransactionalReportCommitError, ReportCommitConflict, ReportCommitDuplicate,
)

def commit_report_version(
    *,
    repository,
    artifacts,
    order,
    patient,
    user,
    editor_type,
    requested_status,
    source_file,
    base_version_no,
    commit_id,
    findings="",
    impression="",
    radiologist="",
    change_summary="",
):
    """
    Unified transactional clinical report writer.

    IMPORTANT:
    - Caller owns surrounding request context.
    - Uses DB row locking.
    - Existing clinical version files are immutable.
    - Network retries return existing commit.
    """

    cid = normalize_commit_id(commit_id)

    editor = str(editor_type or "").upper().strip()
    status = str(requested_status or "").upper().strip()

    if editor not in (
        "BROWSER",
        "WORD",
        "ONLYOFFICE",
        "UPLOAD",
        "LIBREOFFICE",
    ):
        raise TransactionalReportCommitError(
            "INVALID_EDITOR_TYPE"
        )

    if status not in (
        "DRAFT",
        "VERIFIED",
    ):
        raise TransactionalReportCommitError(
            "INVALID_REPORT_COMMIT_STATUS"
        )

    action = f"{editor}_{status}"

    if len(action) > 20:
        raise TransactionalReportCommitError(
            "REPORT_ACTION_TOO_LONG"
        )

    validate_commit_identity(
        patient_db_id=patient.id,
        order_patient_db_id=order.patient_id,
        accession=order.accession,
        expected_accession=order.accession,
    )

    created_artifact = None

    try:
        # --------------------------------------------------
        # 1. Lock Report row.
        # --------------------------------------------------

        report = repository.lock_report(order.report.id)
        existing_commit = repository.find_commit(report.id, cid)

        if existing_commit:
            return {
                "version": existing_commit,
                "retry": True,
                "commit_id": cid,
            }

        # --------------------------------------------------
        # 3. Final lifecycle lock.
        #
        # A new clinical content commit is forbidden after
        # finalization. Idempotent retry of an already-known
        # commit_id is intentionally handled above.
        # --------------------------------------------------

        latest = repository.latest_version(report.id)

        report_is_final = (
            str(getattr(report, "status", "") or "")
            .upper()
            .strip()
            == "FINAL"
        )

        version_is_finalized = (
            latest is not None
            and getattr(latest, "finalized_at", None)
            is not None
        )

        if report_is_final or version_is_finalized:
            raise TransactionalReportCommitError(
                "FINAL_REPORT_REQUIRES_ADDENDUM"
            )

        # --------------------------------------------------
        # 4. Re-read latest version number after lock.
        # --------------------------------------------------

        current_version_no = (
            int(latest.version_no)
            if latest
            else 0
        )

        try:
            validate_base_version(
                current_version_no=current_version_no,
                base_version_no=base_version_no,
            )
        except ReportVersionConflict as exc:
            raise ReportCommitConflict(str(exc)) from exc

        # --------------------------------------------------
        # 5. Source artifact validation/hash.
        # --------------------------------------------------

        if not source_file:
            raise TransactionalReportCommitError(
                "SOURCE_FILE_REQUIRED"
            )

        if not artifacts.source_exists(source_file):
            raise TransactionalReportCommitError(
                "SOURCE_FILE_NOT_FOUND"
            )

        incoming_hash = artifacts.hash(source_file)

        all_hashes = repository.version_hashes(report.id)

        try:
            validate_duplicate_content(
                incoming_hash=incoming_hash,
                existing_hashes=all_hashes,
            )
        except Exception as exc:
            code = getattr(
                exc,
                "code",
                ""
            )

            if code == "REPORT_VERSION_DUPLICATE":
                raise ReportCommitDuplicate(
                    "REPORT_CONTENT_ALREADY_EXISTS"
                )

            raise

        # --------------------------------------------------
        # 6. Allocate version while row remains locked.
        # --------------------------------------------------

        version_no = current_version_no + 1

        # --------------------------------------------------
        # 7. Build canonical immutable target.
        # --------------------------------------------------

        ext = artifacts.extension(source_file)

        if ext not in (
            "docx",
            "pdf",
            "odt",
        ):
            raise TransactionalReportCommitError(
                "UNSUPPORTED_REPORT_FILE"
            )

        target = artifacts.target(patient, order, version_no, ext)
        artifacts.publish(source_file, target, incoming_hash, ext)
        created_artifact = str(target)

        # --------------------------------------------------
        # 9. Create immutable ReportVersion.
        # --------------------------------------------------

        username = (
            getattr(user, "full_name", None)
            or getattr(user, "username", None)
            or "Unknown"
        )

        role = (
            getattr(
                getattr(user, "role", None),
                "code",
                None
            )
            or "SYSTEM"
        )

        now = datetime.utcnow()

        version = repository.create_version(
            report_id=report.id,
            accession=order.accession,
            version_no=version_no,
            action=action,
            findings=findings or "",
            impression=impression or "",
            radiologist=(
                radiologist
                or username
            ),
            docx_path=(
                str(target)
                if ext == "docx"
                else None
            ),
            pdf_path=(
                str(target)
                if ext == "pdf"
                else None
            ),
            source_path=str(target),
            source_type=ext.upper(),
            created_at=now,
            created_by=getattr(
                user,
                "id",
                None
            ),
            created_role=role,
            change_summary=(
                change_summary
                or "Unified report commit"
            ),
            sha256=incoming_hash,
            file_size=artifacts.size(target),
            status=status,
            editor_type=editor,
            base_version_no=int(
                base_version_no
            ),
            commit_id=cid,
            verified_by_user_id=(
                getattr(user, "id", None)
                if str(requested_status).upper()
                == "VERIFIED"
                else None
            ),
            verified_at=(
                now
                if str(requested_status).upper()
                == "VERIFIED"
                else None
            ),
            previous_version_sha256=(
                str(latest.sha256 or "")
                if latest
                else None
            ),
        )

        repository.add(version)

        # --------------------------------------------------
        # 10. Update current working summary only.
        # --------------------------------------------------

        report.findings = version.findings
        report.impression = version.impression
        report.radiologist = version.radiologist

        if ext == "docx":
            report.docx_path = str(
                target
            )

        if ext == "pdf":
            report.pdf_path = str(
                target
            )

        report.source_path = str(target)
        report.source_type = ext.upper()
        report.updated_at = now

        if (
            str(requested_status).upper()
            == "VERIFIED"
        ):
            report.status = "VERIFIED"
            report.verified_by = username
            report.verified_at = now
        else:
            report.status = "DRAFT"

        order.status = "REPORTING"

        # --------------------------------------------------
        # 11. Flush while lock is active.
        # --------------------------------------------------

        repository.flush()

        return {
            "version": version,
            "retry": False,
            "commit_id": cid,
        }

    except repository.integrity_error as exc:
        repository.rollback()
        artifacts.discard(created_artifact)
        raise TransactionalReportCommitError("REPORT_COMMIT_INTEGRITY_FAILURE") from exc
    except Exception:
        repository.rollback()
        artifacts.discard(created_artifact)
        raise
