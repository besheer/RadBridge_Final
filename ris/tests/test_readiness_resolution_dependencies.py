from datetime import datetime
from types import SimpleNamespace as Row
import pytest
from application.services.readiness import resolution_workflow as service
from domain.readiness_resolution import CaseExceptionResolutionError


class Repository:
    has_readiness = True

    def __init__(self, status='UNREPORTED', images=10):
        self.status = status
        self.order = Row(id=1, status='IMAGES_RECEIVED', modality='CT', procedure='Synthetic CT')
        self.readiness = Row(image_count=images, expected_min_images=80,
                             series_evidence_json='[{"description":"Synthetic Axial"}]')
        self.calls = []
        self.previous = None
        self.alias = Row(active=False)

    def lock_order(self, order_id): self.calls.append('order'); return self.order
    def latest_report_status(self, order_id): self.calls.append('report'); return self.status
    def lock_readiness(self, order_id): self.calls.append('readiness'); return self.readiness
    def lock_quality_rules(self, modality):
        self.calls.append('rules')
        return [Row(id=2, procedure_pattern='Synthetic', required_series='AXIAL/CORONAL')]
    def lock_alias_key(self, *args): return None
    def lock_alias_id(self, alias_id): return self.alias
    def lock_active_override(self, order_id): return self.previous
    def create_alias(self, **values): return Row(**values)
    def create_event(self, **values): self.calls.append('event'); return Row(**values)
    def create_override(self, **values): self.calls.append('override'); return Row(**values)
    def create_note(self, **values): self.calls.append('note'); return Row(**values)
    def add(self, row): self.calls.append('add')
    def flush(self): self.calls.append('flush')


def arguments(repo):
    return dict(repository=repo, clock=lambda: datetime(2026, 1, 1),
                order_id=1, actor_user_id=3, reason='Synthetic reviewed reason')


@pytest.mark.parametrize('status', ['VERIFIED', 'FINAL'])
@pytest.mark.parametrize('operation,extra', [
    (service.atomic_add_clinical_history, dict(text_value='Synthetic history')),
    (service.atomic_image_minimum_override, dict(approved_minimum=10)),
    (service.atomic_series_alias_mapping, dict(source_alias='Synthetic Axial', canonical_series='AXIAL', match_field='DESCRIPTION')),
    (service.atomic_deactivate_series_alias, dict(alias_id=2)),
    (service.atomic_deactivate_readiness_override, dict(override_id=2)),
])
def test_terminal_report_barrier_precedes_evidence_and_mutations(status, operation, extra):
    repo = Repository(status)
    with pytest.raises(CaseExceptionResolutionError, match='TERMINAL_REPORT_RESOLUTION_LOCKED'):
        operation(**arguments(repo), **extra)
    assert repo.calls == ['order', 'report']


def test_alias_requires_captured_pacs_evidence_before_rule_lookup():
    repo = Repository()
    with pytest.raises(CaseExceptionResolutionError, match='SERIES_ALIAS_NOT_IN_PACS_EVIDENCE'):
        service.atomic_series_alias_mapping(**arguments(repo), source_alias='Absent', canonical_series='AXIAL', match_field='DESCRIPTION')
    assert repo.calls == ['order', 'report', 'readiness']


def test_alias_uses_required_rule_and_records_audit():
    repo = Repository()
    result = service.atomic_series_alias_mapping(**arguments(repo), source_alias='Synthetic Axial', canonical_series='AXIAL', match_field='DESCRIPTION')
    assert result['action'] == 'CREATED'
    assert result['alias'].canonical_series == 'AXIAL'
    assert repo.calls[-3:] == ['event', 'add', 'flush']
    with pytest.raises(CaseExceptionResolutionError, match='CANONICAL_SERIES_NOT_REQUIRED_BY_RULE'):
        service.atomic_series_alias_mapping(**arguments(repo), source_alias='Synthetic Axial', canonical_series='SAGITTAL', match_field='DESCRIPTION')


def test_replacement_override_flushes_previous_deactivation_first():
    repo = Repository()
    repo.previous = Row(active=True, deactivated_at=None)
    result = service.atomic_image_minimum_override(**arguments(repo), approved_minimum=10)
    assert not repo.previous.active
    assert repo.previous.deactivated_at == datetime(2026, 1, 1)
    assert repo.calls.index('flush') < repo.calls.index('override')
    assert result.override_value == '10'


@pytest.mark.parametrize('images,minimum,code', [(0,1,'PACS_IMAGES_REQUIRED'), (10,11,'APPROVED_MINIMUM_MUST_NOT_EXCEED_CURRENT_IMAGES')])
def test_minimum_cannot_invent_images(images, minimum, code):
    repo = Repository(images=images)
    with pytest.raises(CaseExceptionResolutionError, match=code):
        service.atomic_image_minimum_override(**arguments(repo), approved_minimum=minimum)
    assert not {'event', 'add', 'override', 'flush'}.intersection(repo.calls)


def test_inactive_alias_retry_has_no_duplicate_event():
    repo = Repository()
    assert service.atomic_deactivate_series_alias(**arguments(repo), alias_id=2)['action'] == 'IDEMPOTENT'
    assert repo.calls == ['order', 'report']
