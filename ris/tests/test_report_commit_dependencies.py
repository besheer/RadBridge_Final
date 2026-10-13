"""Commit service contracts with independent persistence and artifact ports."""
from types import SimpleNamespace as Row
import uuid
import subprocess
import sys
from pathlib import Path

import pytest

from application.services.reporting.report_commit_service import commit_report_version
from application.services.reporting.commit_errors import TransactionalReportCommitError
from infrastructure.adapters.reporting.artifact_store import LocalReportArtifactStore
from infrastructure.adapters.reporting.report_commit_core import sha256_file


class PersistenceFailure(Exception):
    pass


class Repository:
    integrity_error = PersistenceFailure

    def __init__(self, fail=False):
        self.report = Row(id=1, status='DRAFT')
        self.fail, self.rolled_back = fail, False
        self.versions = []

    def lock_report(self, report_id):
        assert report_id == 1
        return self.report

    def find_commit(self, report_id, commit_id):
        return next((v for v in self.versions if v.commit_id == commit_id), None)

    def latest_version(self, report_id):
        return self.versions[-1] if self.versions else None

    def version_hashes(self, report_id):
        return [v.sha256 for v in self.versions]

    def create_version(self, **values):
        return Row(**values)

    def add(self, version):
        self.versions.append(version)

    def flush(self):
        if self.fail:
            raise PersistenceFailure('synthetic flush failure')

    def rollback(self):
        self.rolled_back = True


class Artifacts:
    def __init__(self):
        self.published, self.discarded = [], []

    def source_exists(self, source): return True
    def hash(self, source): return 'synthetic-hash'
    def extension(self, source): return 'pdf'
    def target(self, patient, order, number, ext): return 'synthetic/version.pdf'
    def publish(self, source, target, digest, ext): self.published.append(target)
    def size(self, target): return 42
    def discard(self, target): self.discarded.append(target)


def values(repository, artifacts):
    return dict(repository=repository, artifacts=artifacts,
                patient=Row(id=7), order=Row(patient_id=7, accession='SYNTHETIC', report=Row(id=1)),
                user=Row(id=2, username='synthetic'), editor_type='BROWSER', requested_status='DRAFT',
                source_file='synthetic.pdf', base_version_no=0, commit_id=str(uuid.uuid4()))


def test_independent_ports_and_retry_do_not_publish_twice():
    first_repo, second_repo = Repository(), Repository()
    first_store, second_store = Artifacts(), Artifacts()
    request = values(first_repo, first_store)
    first = commit_report_version(**request)
    assert not first['retry'] and len(first_store.published) == 1
    retry = commit_report_version(**dict(request, source_file=None))
    assert retry['retry'] and retry['version'] is first['version']
    assert len(first_store.published) == 1
    assert second_repo.versions == [] and second_store.published == []


def test_failed_flush_rolls_back_and_discards_only_its_published_artifact():
    repository, artifacts = Repository(fail=True), Artifacts()
    with pytest.raises(TransactionalReportCommitError, match='REPORT_COMMIT_INTEGRITY_FAILURE'):
        commit_report_version(**values(repository, artifacts))
    assert repository.rolled_back
    assert artifacts.discarded == artifacts.published == ['synthetic/version.pdf']


def test_final_barrier_precedes_artifact_publication():
    repository, artifacts = Repository(), Artifacts()
    repository.report.status = 'FINAL'
    with pytest.raises(TransactionalReportCommitError, match='FINAL_REPORT_REQUIRES_ADDENDUM'):
        commit_report_version(**values(repository, artifacts))
    assert artifacts.published == []
    assert repository.rolled_back


def test_no_clobber_publication_retains_existing_version(tmp_path):
    source, target = tmp_path / 'source.pdf', tmp_path / 'version.pdf'
    source.write_bytes(b'SYNTHETIC NEW')
    target.write_bytes(b'SYNTHETIC ORIGINAL')
    store = LocalReportArtifactStore(tmp_path, sha256_file)
    with pytest.raises(Exception):
        store.publish(source, target, sha256_file(source), 'pdf')
    assert target.read_bytes() == b'SYNTHETIC ORIGINAL'
    assert not list(tmp_path.glob('.report-commit-*'))


def test_copy_hash_mismatch_does_not_publish(tmp_path):
    source, target = tmp_path / 'source.pdf', tmp_path / 'version.pdf'
    source.write_bytes(b'SYNTHETIC')
    store = LocalReportArtifactStore(tmp_path, lambda path: 'different-hash')
    with pytest.raises(TransactionalReportCommitError, match='REPORT_COPY_HASH_MISMATCH'):
        store.publish(source, target, 'expected-hash', 'pdf')
    assert not target.exists()
    assert not list(tmp_path.glob('.report-commit-*'))


def test_service_import_does_not_load_database_web_storage_or_runtime():
    ris = str(Path(__file__).resolve().parents[1])
    code = "import sys; sys.path.insert(0, %r); import application.services.reporting.report_commit_service; assert not any(n == 'flask' or n == 'sqlalchemy' or n.startswith('infrastructure.') or n == 'application.legacy_runtime' for n in sys.modules)" % ris
    subprocess.run([sys.executable, '-c', code], check=True)
