"""Deterministic, non-clinical DICOM router error classification."""
from dataclasses import dataclass

POLICY_VERSION = 'dicom-router-v1'

@dataclass(frozen=True)
class RuleResult:
    category: str
    suggested_action: str
    status: str
    reason_code: str

RULES = {
    'ASSOCIATION_TIMEOUT': RuleResult('CONNECTION', 'CHECK_CONNECTIVITY', 'CLASSIFIED', 'RULE_MATCH'),
    'ASSOCIATION_REJECTED': RuleResult('CONFIGURATION', 'CHECK_AE_TITLE', 'CLASSIFIED', 'RULE_MATCH'),
    'UNKNOWN_CALLED_AE_TITLE': RuleResult('CONFIGURATION', 'CHECK_AE_TITLE', 'CLASSIFIED', 'RULE_MATCH'),
    'OUT_OF_RESOURCES': RuleResult('STORAGE', 'ALERT_OPERATOR', 'CLASSIFIED', 'RULE_MATCH'),
    'C_STORE_FAILURE': RuleResult('TRANSFER', 'HUMAN_REVIEW', 'NEEDS_REVIEW', 'AMBIGUOUS_TRANSFER'),
    'INVALID_DICOM_DATA': RuleResult('DATA_QUALITY', 'HUMAN_REVIEW', 'NEEDS_REVIEW', 'DATA_REQUIRES_REVIEW'),
}

def classify(error_code: str, retry_count: int) -> RuleResult:
    code=error_code.strip().upper()
    if retry_count >= 5 and code == 'ASSOCIATION_TIMEOUT':
        return RuleResult('CONNECTION', 'HUMAN_REVIEW', 'NEEDS_REVIEW', 'RETRY_BUDGET_REACHED')
    return RULES.get(code, RuleResult('UNKNOWN', 'HUMAN_REVIEW', 'NEEDS_REVIEW', 'UNKNOWN_ERROR_CODE'))
