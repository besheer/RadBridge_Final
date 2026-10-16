"""RadBridge assignment decision engine, phase 1.

The engine is deliberately side-effect free.  DISABLED is the safe default;
SHADOW computes a recommendation for comparison without enforcing it.
"""

from dataclasses import asdict, dataclass


SUPPORTED_MODES = frozenset({"DISABLED", "SHADOW"})


def normalize_mode(value):
    mode = str(value or "DISABLED").strip().upper()
    return mode if mode in SUPPORTED_MODES else "DISABLED"


@dataclass(frozen=True)
class DecisionResult:
    mode: str
    recommendation: str
    reasons: tuple
    enforce: bool = False

    def to_dict(self):
        return asdict(self)


def evaluate_assignment_decision(*, mode="DISABLED", facts=None):
    """Return a non-enforcing assignment recommendation.

    Facts are plain values so this function cannot query PACS, mutate a model,
    create an offer, or write to the database.
    """

    selected_mode = normalize_mode(mode)
    if selected_mode == "DISABLED":
        return DecisionResult(
            mode="DISABLED",
            recommendation="NO_DECISION",
            reasons=("ENGINE_DISABLED",),
        )

    facts = dict(facts or {})
    reasons = []

    if str(facts.get("exam_status") or "").strip().upper() != "EXAM_COMPLETED":
        reasons.append("EXAM_NOT_COMPLETED")
    if str(facts.get("pacs_status") or "").strip().upper() != "IMAGES_COMPLETE":
        reasons.append("IMAGES_NOT_COMPLETE")
    if str(facts.get("readiness_status") or "").strip().upper() != "READY":
        reasons.append("READINESS_NOT_READY")
    if bool(facts.get("return_open")):
        reasons.append("RETURNED_FOR_CORRECTION")
    if bool(facts.get("already_assigned")):
        reasons.append("ALREADY_ASSIGNED")

    return DecisionResult(
        mode="SHADOW",
        recommendation="BLOCK" if reasons else "ALLOW",
        reasons=tuple(reasons) if reasons else ("READY_FOR_ASSIGNMENT",),
    )
