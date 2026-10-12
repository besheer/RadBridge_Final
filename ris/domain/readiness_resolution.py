"""Readiness resolution barriers and evidence aliasing; no DICOM mutations."""
import re

TERMINAL_ORDER_STATUSES = {"FINAL", "CANCELLED"}
TERMINAL_REPORT_STATUSES = {"VERIFIED", "FINAL"}
ALLOWED_MATCH_FIELDS = {"DESCRIPTION", "PROTOCOL", "EITHER"}


class CaseExceptionResolutionError(ValueError):
    def __init__(self, code):
        self.code = str(code)
        super().__init__(self.code)


def normalize(value):
    return re.sub(r"[^A-Z0-9]+", " ", str(value or "").upper()).strip()


def assert_editable(order_status, report_status):
    if normalize(order_status) in TERMINAL_ORDER_STATUSES:
        raise CaseExceptionResolutionError("TERMINAL_CASE_RESOLUTION_LOCKED")
    if normalize(report_status) in TERMINAL_REPORT_STATUSES:
        raise CaseExceptionResolutionError("TERMINAL_REPORT_RESOLUTION_LOCKED")


def apply_series_aliases(series, aliases):
    """Return copied PACS evidence enriched with configured canonical names."""
    output = []
    for source in series or []:
        row = dict(source)
        description = str(row.get("description") or "")
        protocol = str(row.get("protocol") or "")
        matched = []
        for alias in aliases or []:
            if not bool(getattr(alias, "active", True)):
                continue
            token = normalize(getattr(alias, "alias_normalized", "") or
                              getattr(alias, "source_alias", ""))
            field = normalize(getattr(alias, "match_field", "EITHER"))
            haystacks = []
            if field in {"DESCRIPTION", "EITHER"}:
                haystacks.append(normalize(description))
            if field in {"PROTOCOL", "EITHER"}:
                haystacks.append(normalize(protocol))
            if token and any(token in value for value in haystacks):
                canonical = normalize(getattr(alias, "canonical_series", ""))
                if canonical and canonical not in matched:
                    matched.append(canonical)
        if matched:
            row["description"] = " ".join([description] + matched).strip()
            row["mapped_series"] = matched
        output.append(row)
    return output

