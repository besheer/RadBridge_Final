"""Distribution decisions over supplied facts; no database or runtime access."""
from dataclasses import dataclass
from datetime import datetime

def start_timeout_seconds(policy, modality, priority, images):
    modality = str(modality or '').upper()
    priority = str(priority or 'ROUTINE').upper()
    matched = [r for r in policy['rules']
               if r['modality'] in ('*', modality)
               and r['priority'] in ('*', priority)
               and int(r['min_images']) <= int(images or 0)]
    if not matched:
        raise ValueError('START_DEADLINE_RULE_MISSING')
    rule = max(matched, key=lambda r: (r['priority'] != '*', r['modality'] != '*', r['min_images']))
    percent = 100
    if rule['priority'] == '*':
        percent = policy['stat_percent'] if priority == 'STAT' else policy['urgent_percent'] if priority == 'URGENT' else 100
    return max(60, int(rule['minutes']) * 60 * int(percent) // 100)


@dataclass(frozen=True)
class CandidateFacts:
    index: int
    doctor_id: int
    online: bool
    active: int
    pending: int
    capacity: int
    last_turn: datetime
    weight: float


def rank_candidate_facts(candidates, selection_mode):
    ranked = []
    for c in candidates:
        if c.active + c.pending >= c.capacity:
            continue
        if selection_mode == 'ROUND_ROBIN':
            key = (c.last_turn, c.doctor_id)
        elif selection_mode == 'LONGEST_WAITING':
            key = (0 if c.online else 1, c.last_turn, c.doctor_id)
        else:
            key = (0 if c.online else 1, c.active + c.pending, c.last_turn, -c.weight, c.doctor_id)
        ranked.append((key, c.index))
    return [index for _, index in sorted(ranked, key=lambda item: item[0])]
