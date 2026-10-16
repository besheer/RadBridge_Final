import uuid
from datetime import datetime
import pytest
import app as m
from application.services.readiness.scheduling import run_due
from domain.readiness_schedule import DEFAULTS
from infrastructure.adapters.readiness.schedule_repository import SqlAlchemyReadinessScheduleRepository


def repository():
    return SqlAlchemyReadinessScheduleRepository(m.db.session, lambda:m.db.engine,
        m.Order, m.Report, m.CaseReadiness, m.AuditLog)


def test_persisted_candidates_skip_final_and_scheduler_commits_synthetic_evidence(app_ctx):
    session=m.db.session
    key='SYNTH-'+uuid.uuid4().hex[:8]
    try:
        # Isolate the scheduler candidate set from other synthetic test modules.
        m.Order.query.update({m.Order.status:'CANCELLED'},synchronize_session=False)
        patient=m.Patient(patient_id=key,name='Synthetic schedule patient')
        session.add(patient);session.flush()
        due=m.Order(accession=key,patient_id=patient.id,modality='CT',procedure='Synthetic',
                    scheduled=datetime(2026,1,1),status='IMAGES_RECEIVED',exam_status='EXAM_COMPLETED')
        final=m.Order(accession=key+'-FINAL',patient_id=patient.id,modality='CT',procedure='Synthetic',
                    scheduled=datetime(2026,1,1),status='IMAGES_RECEIVED',exam_status='EXAM_COMPLETED')
        session.add_all([due,final]);session.flush()
        session.add(m.Report(order_id=final.id,status='FINAL'));session.flush()
        repo=repository()
        assert repo.candidate_ids()==[due.id]
        def refresh(order):
            session.add(m.CaseReadiness(order_id=order.id,status='BLOCKED',checked_at=datetime(2026,1,1)))
        # Keep fixture cleanup possible while verifying real flush/locks/queries.
        commits=[]
        repo.commit=lambda:(session.flush(),commits.append(True))
        assert run_due(repository=repo,config=dict(DEFAULTS,enabled=True),refresh_order=refresh,
                       clock=lambda:datetime(2026,1,1),monotonic=lambda:0)==dict(enabled=True,checked=1,errors=0)
        assert commits==[True]
        assert m.CaseReadiness.query.filter_by(order_id=due.id).one().status=='BLOCKED'
        assert m.CaseReadiness.query.filter_by(order_id=final.id).first() is None
    finally:
        session.rollback();session.remove()


def test_postgres_advisory_lock_blocks_other_connection_and_can_be_reacquired(app_ctx):
    if m.db.engine.dialect.name!='postgresql':
        pytest.skip('Requires isolated PostgreSQL connections')
    first=repository().acquire_run_lock()
    assert first.acquired
    try:
        second=repository().acquire_run_lock()
        assert not second.acquired
    finally:
        first.release()
    third=repository().acquire_run_lock()
    try:
        assert third.acquired
    finally:
        third.release()
