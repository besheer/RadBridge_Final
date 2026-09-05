"""Pure patient-safety policy for PACS study resolution."""

TERMINAL_ORDER_STATUSES = frozenset({"FINAL", "CANCELLED"})
TERMINAL_REPORT_STATUSES = frozenset({"VERIFIED", "FINAL"})


class PacsResolutionPolicyError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def normalize(value):
    return str(value or "").strip()


def assert_primary_link_allowed(*, order_status, report_status,
                                current_study_id, requested_study_id):
    current = normalize(current_study_id)
    requested = normalize(requested_study_id)
    if not requested:
        raise PacsResolutionPolicyError("PACS_STUDY_ID_REQUIRED")
    terminal = (
        normalize(order_status).upper() in TERMINAL_ORDER_STATUSES
        or normalize(report_status).upper() in TERMINAL_REPORT_STATUSES
    )
    if terminal and current != requested:
        raise PacsResolutionPolicyError("TERMINAL_CASE_PACS_LOCKED")
    return "IDEMPOTENT" if current == requested else "CHANGE"


def assert_exam_link_allowed(*, primary_patient_id, secondary_patient_id,
                             secondary_order_status, secondary_report_status,
                             reason):
    if primary_patient_id is None or secondary_patient_id is None:
        raise PacsResolutionPolicyError("EXAM_LINK_PATIENT_REQUIRED")
    if int(primary_patient_id) != int(secondary_patient_id):
        raise PacsResolutionPolicyError("EXAM_LINK_PATIENT_MISMATCH")
    if normalize(secondary_order_status).upper() in TERMINAL_ORDER_STATUSES:
        raise PacsResolutionPolicyError("TERMINAL_CASE_PACS_LOCKED")
    if normalize(secondary_report_status).upper() in TERMINAL_REPORT_STATUSES:
        raise PacsResolutionPolicyError("TERMINAL_CASE_PACS_LOCKED")
    if len(normalize(reason)) < 5:
        raise PacsResolutionPolicyError("EXAM_LINK_REASON_REQUIRED")
    return True


def assert_exam_unlink_allowed(*, secondary_order_status,
                               secondary_report_status, reason):
    """Protect removal as strongly as creation."""
    if normalize(secondary_order_status).upper() in TERMINAL_ORDER_STATUSES:
        raise PacsResolutionPolicyError("TERMINAL_CASE_PACS_LOCKED")
    if normalize(secondary_report_status).upper() in TERMINAL_REPORT_STATUSES:
        raise PacsResolutionPolicyError("TERMINAL_CASE_PACS_LOCKED")
    if len(normalize(reason)) < 5:
        raise PacsResolutionPolicyError("EXAM_UNLINK_REASON_REQUIRED")
    return True
