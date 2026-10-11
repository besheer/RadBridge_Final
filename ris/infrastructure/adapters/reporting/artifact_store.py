"""Immutable no-clobber local report publication with copy hash verification."""
import os
import shutil
import tempfile
from infrastructure.adapters.reporting.report_storage_safety import (
    version_artifact_path, create_secure_directory, assert_new_version_target,
)
from application.services.reporting.commit_errors import TransactionalReportCommitError


class LocalReportArtifactStore:
    def __init__(self, root, hash_file):
        self.root, self.hash = root, hash_file

    def source_exists(self, source):
        return os.path.isfile(source)

    def extension(self, source):
        return os.path.splitext(source)[1].lower().lstrip('.')

    def target(self, patient, order, version_no, ext):
        return version_artifact_path(self.root, patient, order, version_no, ext)

    def size(self, target):
        return os.path.getsize(target)

    def discard(self, created_artifact):
        if created_artifact and os.path.exists(created_artifact):
            try:
                os.unlink(created_artifact)
            except Exception:
                pass

    def publish(self, source_file, target, incoming_hash, ext):
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
    
            copied_hash = self.hash(
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
    
            return str(target)
    
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
    
