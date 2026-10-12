"""Read-only distribution queries with an explicit repository dependency."""
import json
from typing import Protocol


class AssignmentQueryRepository(Protocol):
    def policy_record(self): ...
    def profile_capacity(self, doctor_id): ...
    def active_case_count(self, doctor_id): ...


class AssignmentQueries:
    def __init__(self, repository: AssignmentQueryRepository, default_rules):
        self.repository = repository
        self.default_rules = default_rules

    def policy_snapshot(self):
        row = self.repository.policy_record()
        if row is None:
            return dict(selection_mode='LEAST_ACTIVE', max_active_cases=20,
                        reclaim_enabled=True, urgent_percent=50, stat_percent=25,
                        rules=self.default_rules, special_rules=[], version_no=0)
        return dict(selection_mode=row.selection_mode, max_active_cases=row.max_active_cases,
                    reclaim_enabled=row.reclaim_enabled, urgent_percent=row.urgent_percent,
                    stat_percent=row.stat_percent, rules=json.loads(row.rules_json),
                    special_rules=json.loads(row.special_rules_json or '[]'), version_no=row.version_no)

    def active_case_count(self, doctor_id):
        return self.repository.active_case_count(doctor_id)

    def case_capacity(self, doctor_id, policy=None):
        policy = policy or self.policy_snapshot()
        capacity = self.repository.profile_capacity(doctor_id)
        return min(int(policy['max_active_cases']), int(capacity or 20))
