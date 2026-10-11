import os
import shutil
import tempfile
from datetime import datetime

from sqlalchemy.exc import IntegrityError

from report_version_safety import ReportVersionConflict
from report_commit_core import (
    normalize_commit_id,
    validate_commit_identity,
    validate_base_version,
    validate_duplicate_content,
    sha256_file,
)

from report_storage_safety import (
    version_artifact_path,
    create_secure_directory,
    assert_new_version_target,
)


class TransactionalReportCommitError(Exception):
    code = "REPORT_COMMIT_ERROR"


class ReportCommitConflict(TransactionalReportCommitError):
    code = "REPORT_VERSION_CONFLICT"


class ReportCommitDuplicate(TransactionalReportCommitError):
    code = "REPORT_VERSION_DUPLICATE"


def commit_report_version(
    *,
    db,
    Report,
    ReportVersion,
    report_root,
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

        report = (
            db.session.query(Report)
            .filter(Report.id == order.report.id)
            .with_for_update()
            .one()
        )

        # --------------------------------------------------
        # 2. Idempotency lookup after lock.
        # --------------------------------------------------

        existing_commit = (
            ReportVersion.query
            .filter_by(
                report_id=report.id,
                commit_id=cid,
            )
            .first()
        )

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

        latest = (
            ReportVersion.query
            .filter_by(report_id=report.id)
            .order_by(
                ReportVersion.version_no.desc()
            )
            .first()
        )

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

        if not os.path.isfile(source_file):
            raise TransactionalReportCommitError(
                "SOURCE_FILE_NOT_FOUND"
            )

        incoming_hash = sha256_file(
            source_file
        )

        all_hashes = [
            str(x.sha256 or "")
            for x in (
                ReportVersion.query
                .filter_by(report_id=report.id)
                .all()
            )
        ]

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

        ext = os.path.splitext(
            source_file
        )[1].lower().lstrip(".")

        if ext not in (
            "docx",
            "pdf",
            "odt",
        ):
            raise TransactionalReportCommitError(
                "UNSUPPORTED_REPORT_FILE"
            )

        target = version_artifact_path(
            report_root,
            patient,
            order,
            version_no,
            ext,
        )

        create_secure_directory(
            target.parent
        )

        assert_new_version_target(
            target
        )

        # --------------------------------------------------
        # 8. Atomic filesystem write.
        # --------------------------------------------------

        fd, temp_path = tempfile.mkstemp(
            prefix=".report-commit-",
            suffix="." + ext,
            dir=str(target.parent),
        )

        os.close(fd)

        try:
            shutil.copy2(
                source_file,
                temp_path,
            )

            copied_hash = sha256_file(
                temp_path
            )

            if copied_hash != incoming_hash:
                raise TransactionalReportCommitError(
                    "REPORT_COPY_HASH_MISMATCH"
                )

            # Immutable no-clobber publication.
            #
            # os.replace() is intentionally forbidden here because
            # it can overwrite an existing clinical version artifact.
            #
            # hard-link creation is atomic and fails with
            # FileExistsError if target already exists.
            try:
                os.link(
                    temp_path,
                    target,
                )
            except FileExistsError as exc:
                raise TransactionalReportCommitError(
                    "REPORT_VERSION_ARTIFACT_EXISTS"
                ) from exc

            os.unlink(temp_path)

            created_artifact = str(
                target
            )

        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

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

        version = ReportVersion(
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
            file_size=os.path.getsize(
                target
            ),
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

        db.session.add(version)

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

        db.session.flush()

        return {
            "version": version,
            "retry": False,
            "commit_id": cid,
        }

    except IntegrityError as exc:
        db.session.rollback()

        if (
            created_artifact
            and os.path.exists(
                created_artifact
            )
        ):
            try:
                os.unlink(
                    created_artifact
                )
            except Exception:
                pass

        raise TransactionalReportCommitError(
            "REPORT_COMMIT_INTEGRITY_FAILURE"
        ) from exc

    except Exception:
        db.session.rollback()

        if (
            created_artifact
            and os.path.exists(
                created_artifact
            )
        ):
            try:
                os.unlink(
                    created_artifact
                )
            except Exception:
                pass

        raise
