"""Assignment query behavior without a Flask runtime or implicit database."""
import json
import subprocess
import sys
from types import SimpleNamespace

import pytest

from application.services.assignment.assignment_queries import AssignmentQueries


class MemoryRepository:
    def __init__(self, capacity=None, count=0, policy=None):
        self.capacity, self.count, self.policy = capacity, count, policy
        self.doctors = []

    def policy_record(self):
        return self.policy

    def profile_capacity(self, doctor_id):
        self.doctors.append(doctor_id)
        return self.capacity

    def active_case_count(self, doctor_id):
        self.doctors.append(doctor_id)
        return self.count


def test_queries_import_without_flask_sqlalchemy_or_a_clinical_runtime():
    code = '''
import sys
from application.services.assignment.assignment_queries import AssignmentQueries
assert not any(n in sys.modules for n in ('app', 'flask', 'sqlalchemy', 'application.legacy_runtime'))
'''
    subprocess.run([sys.executable, '-c', code], check=True)


def test_separate_repository_instances_do_not_share_capacity_or_counts():
    first = MemoryRepository(capacity=3, count=2)
    second = MemoryRepository(capacity=8, count=7)
    a, b = AssignmentQueries(first, []), AssignmentQueries(second, [])
    assert (a.case_capacity(11), a.active_case_count(11)) == (3, 2)
    assert (b.case_capacity(11), b.active_case_count(11)) == (8, 7)
    assert first.doctors == second.doctors == [11, 11]


@pytest.mark.parametrize('profile,policy,expected', [(None, 30, 20), (0, 30, 20), (40, 5, 5), (3, 20, 3)])
def test_capacity_retains_policy_cap_and_missing_profile_default(profile, policy, expected):
    queries = AssignmentQueries(MemoryRepository(capacity=profile), [])
    assert queries.case_capacity(9, {'max_active_cases': policy}) == expected


def test_policy_snapshot_decodes_persisted_rules_and_preserves_version():
    row = SimpleNamespace(selection_mode='ROUND_ROBIN', max_active_cases=6,
                          reclaim_enabled=False, urgent_percent=40, stat_percent=20,
                          rules_json='[{"minutes":17}]', special_rules_json=None, version_no=4)
    query = AssignmentQueries(MemoryRepository(policy=row), [])
    result = query.policy_snapshot()
    assert result['rules'] == [{'minutes': 17}]
    assert result['special_rules'] == []
    assert result['version_no'] == 4 and result['reclaim_enabled'] is False
    row.rules_json = 'invalid'
    with pytest.raises(json.JSONDecodeError):
        query.policy_snapshot()


def test_sql_repository_uses_injected_sessions_without_a_flask_context(monkeypatch):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from infrastructure.extensions import db
    from infrastructure.models import AssignmentDistributionPolicy, DoctorAssignmentProfile, CaseAssignment, Order, Report
    from infrastructure.adapters.assignment.query_repository import SqlAlchemyAssignmentQueryRepository
    import application.legacy_runtime as legacy

    def forbidden():
        raise AssertionError('Query services must not resolve a clinical runtime')

    monkeypatch.setattr(legacy, 'resolve_runtime', forbidden)
    engines = [create_engine('sqlite:///:memory:') for _ in range(2)]
    sessions = []
    try:
        services = []
        for engine, cap in zip(engines, (3, 8)):
            db.metadata.create_all(engine)
            session = Session(engine)
            sessions.append(session)
            session.add(AssignmentDistributionPolicy(id=1, max_active_cases=cap, rules_json='[]'))
            session.flush()
            repository = SqlAlchemyAssignmentQueryRepository(
                session=session, Policy=AssignmentDistributionPolicy,
                Profile=DoctorAssignmentProfile, Assignment=CaseAssignment, Order=Order, Report=Report)
            services.append(AssignmentQueries(repository, []))
        assert [s.case_capacity(77) for s in services] == [3, 8]
        assert [s.active_case_count(77) for s in services] == [0, 0]
    finally:
        for session in sessions:
            session.close()
        for engine in engines:
            engine.dispose()
