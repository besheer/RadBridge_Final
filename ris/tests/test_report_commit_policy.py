import subprocess
import sys
import uuid

import pytest

from domain.reporting import commit_policy as policy
from domain.reporting.content import ReportVersionConflict, DuplicateReportVersion


def test_legacy_exports_keep_the_same_policy_functions_and_exception_types():
    import report_commit_core as legacy
    for name in ('normalize_commit_id', 'validate_commit_identity', 'validate_base_version',
                 'allocate_next_version', 'validate_duplicate_content', 'ReportCommitError'):
        assert getattr(legacy, name) is getattr(policy, name)


def test_patient_context_and_stale_version_are_rejected():
    with pytest.raises(policy.ReportCommitError, match='PATIENT_CONTEXT_MISMATCH'):
        policy.validate_commit_identity(patient_db_id=2, order_patient_db_id=1,
                                         accession='SYNTHETIC', expected_accession='SYNTHETIC')
    with pytest.raises(ReportVersionConflict):
        policy.validate_base_version(current_version_no=4, base_version_no=3)
    with pytest.raises(DuplicateReportVersion):
        policy.validate_duplicate_content(incoming_hash=' ABC ', existing_hashes=['abc'])


def test_retry_uses_normalized_commit_identity():
    commit_id = str(uuid.uuid4())
    assert policy.is_retry_of_existing_commit(commit_id=commit_id.upper(), existing_commit_ids=[commit_id])
    with pytest.raises(policy.ReportCommitError, match='INVALID_COMMIT_ID'):
        policy.normalize_commit_id('not-a-commit-id')


def test_policy_import_has_no_storage_framework_or_runtime_dependency():
    code = '''
import sys
import domain.reporting.commit_policy
assert not any(n in sys.modules for n in ('app', 'flask', 'sqlalchemy', 'report_storage_safety'))
assert not any(n.startswith('infrastructure.') for n in sys.modules)
'''
    subprocess.run([sys.executable, '-c', code], check=True)
