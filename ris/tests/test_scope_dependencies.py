"""Framework-free scope policy and explicitly supplied access repository."""
import subprocess
import sys
from types import SimpleNamespace

import pytest

from application.services.identity.scope_access import ClinicalScopeAccess
from domain.clinical.scope import normalize_scope, parse_scope


@pytest.mark.parametrize('raw', [False, [], {}, {'enabled': False},
    {'enabled': True, 'modalities': [], 'device_keys': ['BR/AE'], 'room_keys': [], 'device_ids': [True]}])
def test_invalid_stored_scope_never_becomes_unrestricted(raw):
    assert normalize_scope(raw) == {'enabled': True, 'invalid': True}
    def forbidden(*args):
        pytest.fail('Invalid scope must fail before querying order evidence')
    repo = SimpleNamespace(order_matches=forbidden)
    assert ClinicalScopeAccess(repo).allowed(SimpleNamespace(active=True), SimpleNamespace(id=1), normalize_scope(raw)) is False


def test_domain_configuration_resolves_explicit_catalog_identifiers():
    values = dict(scope_enabled='true', modalities='ct', device_keys='BR/AE', room_keys='BR/ROOM')
    catalog = ({'CT'}, {'BR/AE': [4]}, {'BR/ROOM': (2, 'ROOM')})
    scope = parse_scope(values, 'TECHNICIAN', catalog)
    assert scope == dict(enabled=True, modalities=['CT'], device_keys=['BR/AE'], room_keys=['BR/ROOM'], device_ids=[4])
    with pytest.raises(ValueError, match='ambiguous'):
        parse_scope(values, 'TECHNICIAN', ({'CT'}, {'BR/AE': [4, 5]}, catalog[2]))


def test_disabled_scope_preserves_early_return_without_reading_catalog(monkeypatch):
    import clinical_scope
    monkeypatch.setattr(clinical_scope, 'catalog', lambda m: pytest.fail('Disabled scope must not query the catalog'))
    assert clinical_scope.parse(None, {'scope_enabled': 'false'}, None) is None


def test_access_uses_the_injected_repository_and_never_queries_for_inactive_actor():
    calls = []
    scope = dict(enabled=True, modalities=['CT'], device_keys=[], room_keys=[])
    access = ClinicalScopeAccess(SimpleNamespace(order_matches=lambda oid, s: calls.append((oid, s)) or oid == 7))
    assert access.allowed(SimpleNamespace(active=True), SimpleNamespace(id=7), scope)
    assert not access.allowed(SimpleNamespace(active=True), SimpleNamespace(id=8), scope)
    assert not access.allowed(SimpleNamespace(active=False), SimpleNamespace(id=7), scope)
    assert [oid for oid, _ in calls] == [7, 8]


def test_scope_core_imports_without_web_database_or_runtime():
    code = '''
import sys
import domain.clinical.scope
import application.services.identity.scope_access
assert not any(n in sys.modules for n in ('app', 'flask', 'sqlalchemy', 'application.legacy_runtime'))
'''
    subprocess.run([sys.executable, '-c', code], check=True)
