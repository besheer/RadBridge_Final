import json
import uuid
from datetime import datetime
import pytest
import app as m
from application.services.readiness import resolution_workflow as service
from domain.readiness_resolution import CaseExceptionResolutionError
from infrastructure.adapters.readiness.resolution_repository import SqlAlchemyReadinessResolutionRepository


def test_persisted_evidence_resolution_and_terminal_barrier(app_ctx):
    key = 'SYNTH-' + uuid.uuid4().hex[:8]
    session = m.db.session
    try:
        role = m.Role(code=key, name='Synthetic technician')
        patient = m.Patient(patient_id=key, name='Synthetic readiness patient')
        session.add_all([role, patient]); session.flush()
        actor = m.User(username=key, full_name='Synthetic technician', role_id=role.id, password_hash='DISABLED-SYNTHETIC')
        order = m.Order(accession=key, patient_id=patient.id, modality='CT', procedure=key,
                        scheduled=datetime(2026, 1, 1), status='IMAGES_RECEIVED')
        rule = m.ProcedureQualityRule(modality='CT', procedure_pattern=key, required_series='AXIAL', active=True)
        session.add_all([actor, order, rule]); session.flush()
        report = m.Report(order_id=order.id, status='UNREPORTED')
        readiness = m.CaseReadiness(order_id=order.id, image_count=10, expected_min_images=80,
                                   series_evidence_json=json.dumps([dict(description='Synthetic Axial')]))
        session.add_all([report, readiness]); session.flush()
        repo = SqlAlchemyReadinessResolutionRepository(session, m.Order, m.Report,
            m.ProcedureQualityRule, m.ReadinessSeriesAlias, m.CaseExceptionResolutionEvent,
            m.CaseReadiness, m.ClinicalNote, m.CaseReadinessOverride)
        args = dict(repository=repo, clock=lambda: datetime(2026, 1, 2), order_id=order.id,
                    actor_user_id=actor.id, reason='Synthetic reviewed evidence')
        note = service.atomic_add_clinical_history(**args, text_value='Synthetic history')
        alias = service.atomic_series_alias_mapping(**args, source_alias='Synthetic Axial',
                    canonical_series='AXIAL', match_field='DESCRIPTION')['alias']
        override = service.atomic_image_minimum_override(**args, approved_minimum=10)
        assert note.id and alias.id and override.id
        assert alias.rule_id == rule.id
        assert m.CaseExceptionResolutionEvent.query.filter_by(order_id=order.id).count() == 3
        assert service.atomic_deactivate_readiness_override(**args, override_id=override.id)['action'] == 'DEACTIVATED'
        assert not override.active and override.deactivated_at == datetime(2026, 1, 2)
        assert service.atomic_deactivate_readiness_override(**args, override_id=override.id)['action'] == 'IDEMPOTENT'
        assert m.CaseExceptionResolutionEvent.query.filter_by(order_id=order.id).count() == 4
        report.status = 'VERIFIED'; session.flush()
        with pytest.raises(CaseExceptionResolutionError, match='TERMINAL_REPORT_RESOLUTION_LOCKED'):
            service.atomic_add_clinical_history(**args, text_value='Forbidden history')
        assert m.ClinicalNote.query.filter_by(order_id=order.id).count() == 1
        assert order.accession == key and patient.patient_id == key
        assert readiness.series_evidence_json == json.dumps([dict(description='Synthetic Axial')])
    finally:
        session.rollback()
        session.remove()
