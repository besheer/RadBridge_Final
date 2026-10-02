"""RadBridge canonical clinical workflow policy.

This module is intentionally framework/ORM independent.  It defines the shared
rules used by Registration/Work Order, Technician, PACS, Reporting and Journey
surfaces without taking ownership away from the specialist domain services.

Authority model
---------------
* Order.status: operational shell (REGISTERED/MWL/SCHEDULED/.../FINAL).
* Order.exam_status: acquisition workflow only.
* Order.pacs_status + PACS match: imaging availability/identity authority.
* Report/ReportVersion: reporting authority.
* Patient Journey: a projection of the authorities above, never an independent
  state machine.

Callers remain responsible for transactions, audit records and external I/O.
"""

from dataclasses import dataclass
from datetime import date
from typing import Dict, Iterable, Set, Tuple


EXAM_STATES = (
    "BOOKED",
    "ORDERED",
    "IN_PROGRESS",
    "EXAM_COMPLETED",
    "REPORTING",
    "CANCELLED",
)

EXAM_FORWARD_STATES = (
    "BOOKED",
    "ORDERED",
    "IN_PROGRESS",
    "EXAM_COMPLETED",
    "REPORTING",
)

NEXT_EXAM_STATE = {
    "BOOKED": "ORDERED",
    "ORDERED": "IN_PROGRESS",
    "IN_PROGRESS": "EXAM_COMPLETED",
    "EXAM_COMPLETED": "REPORTING",
}

ROLE_TRANSITIONS: Dict[str, Set[Tuple[str, str]]] = {
    "RECEPTION": {("BOOKED", "ORDERED")},
    "TECHNICIAN": {
        ("ORDERED", "IN_PROGRESS"),
        ("IN_PROGRESS", "EXAM_COMPLETED"),
    },
    "SERVICE": {
        ("ORDERED", "IN_PROGRESS"),
        ("IN_PROGRESS", "EXAM_COMPLETED"),
    },
    "RADIOLOGIST": {("EXAM_COMPLETED", "REPORTING")},
    "DOCTOR": {("EXAM_COMPLETED", "REPORTING")},
    "SUPERVISOR": set(),
    "SUPER_ADMIN": set(),
}

ORDER_TERMINAL_STATES = {"FINAL", "CANCELLED"}
WORK_ORDER_ACTIVE_STATES = {
    "SCHEDULED",
    "ARRIVED",
    "IN_PROGRESS",
    "COMPLETED",
    "IMAGES_RECEIVED",
    "REPORTING",
}
RESEND_MWL_ALLOWED_STATES = {"SCHEDULED", "MWL_ERROR"}

JOURNEY_STAGES = (
    "REGISTERED",
    "WAITING",
    "NURSING",
    "TECHNICIAN",
    "EXAM_DONE",
    "PACS_RECEIVED",
    "REPORTING",
    "FINALIZED",
    "DELIVERED",
    "CANCELLED",
)

REPORT_ACTIVE_STATES = {
    "DRAFT",
    "PARTIAL",
    "READY_FORMATTING",
    "FORMATTING",
    "READY_APPROVAL",
    "VERIFIED",
    "SECOND_VERIFIED",
    "ADDENDUM",
}

PACS_RECEIVED_STATES = {
    "RECEIVED",
    "RECEIVING",
    "IMAGES_COMPLETE",
    "AVAILABLE",
}


@dataclass(frozen=True)
class TransitionDecision:
    allowed: bool
    reason: str


@dataclass(frozen=True)
class GateDecision:
    allowed: bool
    reason: str
    blockers: Tuple[str, ...] = ()


def _upper(value, default="") -> str:
    return str(value or default).strip().upper()


def normalize_state(value: str) -> str:
    """Backward-compatible exam-state normalizer."""
    value = _upper(value, "ORDERED")
    return value if value in EXAM_STATES else "ORDERED"


def exam_status_rank(value: str) -> int:
    value = normalize_state(value)
    try:
        return EXAM_FORWARD_STATES.index(value)
    except ValueError:
        return -1


def is_forward_one_step(current: str, target: str) -> bool:
    current = normalize_state(current)
    target = normalize_state(target)
    return NEXT_EXAM_STATE.get(current) == target


def can_transition(
    role_code: str,
    current: str,
    target: str,
    override: bool = False,
) -> TransitionDecision:
    """Canonical exam transition authorization.

    Reporting VERIFIED/FINAL are deliberately absent: they belong to the report
    state machine and cannot be written through the exam endpoint.
    """
    role_code = _upper(role_code)
    current = _upper(current, "ORDERED")
    target = _upper(target)

    # Display normalization must never turn an invalid transition into a valid one.
    if current not in EXAM_STATES:
        return TransitionDecision(False, "invalid_current_exam_state")
    if target not in EXAM_STATES:
        return TransitionDecision(False, "invalid_target_exam_state")

    if target == "CANCELLED":
        return TransitionDecision(False, "cancellation_requires_cancellation_workflow")

    if override and role_code in {"SUPERVISOR", "SUPER_ADMIN"}:
        return TransitionDecision(True, "supervisor_override")

    if not is_forward_one_step(current, target):
        return TransitionDecision(False, "forward_only")

    if role_code in {"SUPER_ADMIN", "SUPERVISOR"}:
        return TransitionDecision(True, "privileged_forward")

    allowed = (current, target) in ROLE_TRANSITIONS.get(role_code, set())
    return TransitionDecision(
        allowed,
        "role_allowed" if allowed else "role_denied",
    )


def work_order_gate(
    *,
    order_status,
    balance,
    patient_id,
    patient_dob,
    accession,
    modality,
    procedure,
    device_id,
    station_ae,
) -> GateDecision:
    """Preconditions for REGISTERED -> Work Order/MWL.

    DOB is required because RadBridge's strict PACS auto-link policy requires
    exact Accession + Patient ID + DOB.  Sending MWL without DOB would create a
    case that can never satisfy AUTO_SAFE without manual reconciliation.
    """
    blockers = []
    status = _upper(order_status)

    if status != "REGISTERED":
        blockers.append("ORDER_NOT_REGISTERED")

    try:
        outstanding = float(balance or 0)
    except (TypeError, ValueError):
        outstanding = 0.0

    if outstanding > 0.01:
        blockers.append("FINANCIAL_CLEARANCE_REQUIRED")

    if not str(patient_id or "").strip():
        blockers.append("PATIENT_ID_REQUIRED")

    dob = str(patient_dob or "").strip()
    if not dob:
        blockers.append("PATIENT_DOB_REQUIRED_FOR_PACS_MATCH")
    elif len(dob) != 8 or not dob.isascii() or not dob.isdigit():
        blockers.append("PATIENT_DOB_INVALID_FOR_DICOM")
    else:
        try:
            date(int(dob[:4]), int(dob[4:6]), int(dob[6:8]))
        except ValueError:
            blockers.append("PATIENT_DOB_INVALID_FOR_DICOM")

    if not str(accession or "").strip():
        blockers.append("ACCESSION_REQUIRED")

    if not str(modality or "").strip():
        blockers.append("MODALITY_REQUIRED")

    if not str(procedure or "").strip():
        blockers.append("PROCEDURE_REQUIRED")

    if not device_id:
        blockers.append("DEVICE_REQUIRED")

    if not str(station_ae or "").strip():
        blockers.append("STATION_AE_REQUIRED")

    if blockers:
        return GateDecision(False, blockers[0], tuple(blockers))

    return GateDecision(True, "WORK_ORDER_READY", ())


def resend_mwl_gate(*, order_status, device_available=True) -> GateDecision:
    status = _upper(order_status)
    blockers = []

    if status not in RESEND_MWL_ALLOWED_STATES:
        blockers.append("MWL_RESEND_STATE_BLOCKED")

    if not device_available:
        blockers.append("NO_ACTIVE_DEVICE_ROUTE")

    if blockers:
        return GateDecision(False, blockers[0], tuple(blockers))

    return GateDecision(True, "MWL_RESEND_READY", ())


def exam_transition_gate(
    *,
    role_code,
    current_exam_status,
    target_exam_status,
    order_status,
    override=False,
    pacs_gate_ok=False,
) -> TransitionDecision:
    """Combine role/sequence policy with cross-domain prerequisites."""
    current = _upper(current_exam_status, "ORDERED")
    target = _upper(target_exam_status)
    status = _upper(order_status)

    decision = can_transition(
        role_code,
        current,
        target,
        override=override,
    )
    if not decision.allowed:
        return decision

    if status in ORDER_TERMINAL_STATES:
        return TransitionDecision(False, "order_terminal")

    if target == "IN_PROGRESS" and status not in WORK_ORDER_ACTIVE_STATES:
        return TransitionDecision(False, "work_order_not_active")

    if target == "EXAM_COMPLETED" and status not in {
        "IN_PROGRESS",
        "COMPLETED",
    }:
        return TransitionDecision(False, "exam_not_in_progress")

    if target == "REPORTING" and not pacs_gate_ok:
        return TransitionDecision(False, "pacs_demographic_gate_required")

    return decision


def order_status_for_exam_transition(current_order_status, target_exam_status) -> str:
    current = _upper(current_order_status)
    if current in ORDER_TERMINAL_STATES:
        return current

    target = normalize_state(target_exam_status)
    mapping = {
        "IN_PROGRESS": "IN_PROGRESS",
        "EXAM_COMPLETED": "COMPLETED",
        "REPORTING": "REPORTING",
    }
    return mapping.get(target, current)


def derive_journey_stage(
    *,
    order_status,
    exam_status,
    pacs_status,
    pacs_image_count=0,
    report_status="",
    report_delivered=False,
    images_delivered=False,
) -> str:
    """Derive the patient journey from authoritative domain state."""
    order = _upper(order_status, "REGISTERED")
    exam = normalize_state(exam_status)
    pacs = _upper(pacs_status, "WAITING")
    report = _upper(report_status, "UNREPORTED")

    if order == "CANCELLED" or exam == "CANCELLED":
        return "CANCELLED"

    if report == "FINAL" or order == "FINAL":
        if report_delivered or images_delivered:
            return "DELIVERED"
        return "FINALIZED"

    if report in REPORT_ACTIVE_STATES or exam == "REPORTING" or order == "REPORTING":
        return "REPORTING"

    try:
        images = int(pacs_image_count or 0)
    except (TypeError, ValueError):
        images = 0

    if (
        order == "IMAGES_RECEIVED"
        or (images > 0 and pacs in PACS_RECEIVED_STATES)
    ):
        return "PACS_RECEIVED"

    if exam == "EXAM_COMPLETED" or order == "COMPLETED":
        return "EXAM_DONE"

    if exam == "IN_PROGRESS" or order == "IN_PROGRESS":
        return "TECHNICIAN"

    if order == "ARRIVED":
        return "NURSING"

    if order in {"SCHEDULED", "MWL_PENDING", "MWL_ERROR"}:
        return "WAITING"

    return "REGISTERED"


def canonical_display_state(
    *,
    order_status,
    exam_status,
    report_status="",
) -> str:
    """Human-facing lifecycle state without mutating any domain column."""
    report = _upper(report_status, "UNREPORTED")
    if report == "FINAL":
        return "FINAL"
    if report in {"VERIFIED", "SECOND_VERIFIED"}:
        return "VERIFIED"

    exam = normalize_state(exam_status)
    if exam in {"IN_PROGRESS", "EXAM_COMPLETED", "REPORTING"}:
        return exam

    return _upper(order_status, "REGISTERED")


def report_source_allowed(report_status) -> bool:
    return _upper(report_status) == "FINAL"


def blockers_text(blockers: Iterable[str]) -> str:
    return ", ".join(str(x) for x in blockers if x)
