from dataclasses import replace
from datetime import datetime, timedelta

import pytest

from domain.assignment.distribution import CandidateFacts, rank_candidate_facts, start_timeout_seconds


def candidate(index, **overrides):
    return replace(CandidateFacts(index, index + 10, True, 0, 0, 20, datetime(2026, 1, 1), 100), **overrides)


@pytest.mark.parametrize('mode', ['LEAST_ACTIVE', 'ROUND_ROBIN', 'LONGEST_WAITING'])
def test_pending_reservations_exclude_full_doctors_in_every_mode(mode):
    full = candidate(0, active=2, pending=3, capacity=5)
    available = candidate(1, active=1, pending=3, capacity=5)
    assert rank_candidate_facts([full, available], mode) == [1]


def test_round_robin_keeps_history_ahead_of_online_status_and_workload():
    older = candidate(0, online=False, active=5)
    newer = candidate(1, last_turn=older.last_turn + timedelta(hours=1))
    assert rank_candidate_facts([newer, older], 'ROUND_ROBIN') == [0, 1]
    assert rank_candidate_facts([older, newer], 'LONGEST_WAITING') == [1, 0]


def test_least_active_uses_pending_then_weight_then_doctor_identity():
    candidates = [candidate(0, pending=1), candidate(1, weight=200), candidate(2)]
    assert rank_candidate_facts(candidates, 'LEAST_ACTIVE') == [1, 2, 0]
    assert rank_candidate_facts([candidate(2), candidate(1)], 'LEAST_ACTIVE') == [1, 2]


def test_explicit_stat_rule_is_not_scaled_twice_and_missing_rule_fails():
    policy = dict(rules=[dict(modality='CT', priority='STAT', min_images=0, minutes=3)],
                  urgent_percent=50, stat_percent=25)
    assert start_timeout_seconds(policy, 'CT', 'STAT', 10) == 180
    with pytest.raises(ValueError, match='START_DEADLINE_RULE_MISSING'):
        start_timeout_seconds(policy, 'MR', 'STAT', 10)
