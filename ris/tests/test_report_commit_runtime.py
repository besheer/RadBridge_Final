"""Synthetic report commit contracts against the real writer and temporary files."""
import uuid
from datetime import datetime
from pathlib import Path

import pytest

from report_transaction_writer import commit_report_version, TransactionalReportCommitError, ReportCommitConflict


@pytest.fixture
def case(app_ctx, tmp_path):
    m = app_ctx
    key = 'SYNTHETIC-COMMIT-' + uuid.uuid4().hex[:8]
    patient = m.Patient(patient_id=key, name='Synthetic Commit Patient')
    doctor = m.User(username=key, full_name='Synthetic Doctor', active=True, password_hash='not-a-login-secret',
                    role=m.Role.query.filter_by(code='RADIOLOGIST').one())
    m.db.session.add_all([patient, doctor]); m.db.session.flush()
    order = m.Order(accession=key, patient_id=patient.id, modality='CT', procedure='Synthetic',
                    scheduled=datetime.utcnow(), status='IMAGES_RECEIVED')
    m.db.session.add(order); m.db.session.flush()
    report = m.Report(order_id=order.id, status='UNREPORTED')
    m.db.session.add(report); m.db.session.flush()
    source = tmp_path / 'synthetic.pdf'
    source.write_bytes(b'%PDF-1.4\nSYNTHETIC TEST PAYLOAD\n%%EOF')
    values = dict(db=m.db, Report=m.Report, ReportVersion=m.ReportVersion, report_root=tmp_path / 'reports',
                  order=order, patient=patient, user=doctor, editor_type='BROWSER', requested_status='DRAFT',
                  source_file=str(source), base_version_no=0, commit_id=str(uuid.uuid4()))
    try:
        yield m, values
    finally:
        m.db.session.rollback(); m.db.session.remove()


def test_known_commit_retry_after_final_returns_existing_artifact_without_a_new_file(case):
    m, values = case
    first = commit_report_version(**values)
    target = Path(first['version'].source_path)
    original = target.read_bytes()
    values['order'].report.status = 'FINAL'
    retry = commit_report_version(**dict(values, source_file=None))
    assert retry['retry'] and retry['version'].id == first['version'].id
    assert target.read_bytes() == original
    assert m.ReportVersion.query.filter_by(report_id=values['order'].report.id).count() == 1
    with pytest.raises(TransactionalReportCommitError, match='FINAL_REPORT_REQUIRES_ADDENDUM'):
        commit_report_version(**dict(values, commit_id=str(uuid.uuid4()), base_version_no=1))
    assert target.read_bytes() == original


def test_stale_base_never_publishes_a_second_version(case):
    m, values = case
    first = commit_report_version(**values)
    target = Path(first['version'].source_path)
    original = target.read_bytes()
    with pytest.raises(ReportCommitConflict):
        commit_report_version(**dict(values, commit_id=str(uuid.uuid4()), base_version_no=0))
    assert target.read_bytes() == original
    assert not list(target.parent.parent.glob('v000002/*'))
