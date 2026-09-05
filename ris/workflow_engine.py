"""Clinical workflow transition policy.

Normal users may advance only one state at a time and only for transitions
assigned to their role. Supervisor/Super Admin override must remain explicit and
should be audited by the calling route.
"""


from dataclasses import dataclass
from typing import Dict, Set, Tuple

STATES = (
    "BOOKED",
    "ORDERED",
    "IN_PROGRESS",
    "EXAM_COMPLETED",
    "REPORTING",
    "VERIFIED",
    "FINAL",
)

NEXT_STATE = {
    "BOOKED": "ORDERED",
    "ORDERED": "IN_PROGRESS",
    "IN_PROGRESS": "EXAM_COMPLETED",
    "EXAM_COMPLETED": "REPORTING",
    "REPORTING": "VERIFIED",
    "VERIFIED": "FINAL",
}

ROLE_TRANSITIONS: Dict[str, Set[Tuple[str, str]]] = {
    "RECEPTION": {("BOOKED", "ORDERED")},
    "TECHNICIAN": {
        ("ORDERED", "IN_PROGRESS"),
        ("IN_PROGRESS", "EXAM_COMPLETED"),
    },
    "RADIOLOGIST": {
        ("EXAM_COMPLETED", "REPORTING"),
        ("REPORTING", "VERIFIED"),
        ("VERIFIED", "FINAL"),
    },
    "SUPERVISOR": set(),
    "SUPER_ADMIN": set(),
}

@dataclass(frozen=True)
class TransitionDecision:
    allowed: bool
    reason: str

def normalize_state(value: str) -> str:
    value = (value or "ORDERED").strip().upper()
    return value if value in STATES else "ORDERED"

def is_forward_one_step(current: str, target: str) -> bool:
    current = normalize_state(current)
    target = normalize_state(target)
    return NEXT_STATE.get(current) == target

def can_transition(role_code: str, current: str, target: str, override: bool = False) -> TransitionDecision:
    role_code = (role_code or "").upper()
    current = normalize_state(current)
    target = normalize_state(target)

    if override and role_code in {"SUPERVISOR", "SUPER_ADMIN"}:
        return TransitionDecision(True, "supervisor_override")

    if not is_forward_one_step(current, target):
        return TransitionDecision(False, "forward_only")

    if role_code in {"SUPER_ADMIN", "SUPERVISOR"}:
        return TransitionDecision(True, "privileged_forward")

    allowed = (current, target) in ROLE_TRANSITIONS.get(role_code, set())
    return TransitionDecision(allowed, "role_allowed" if allowed else "role_denied")
