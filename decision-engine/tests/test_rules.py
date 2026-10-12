import pytest
from app.rules import classify

@pytest.mark.parametrize(('code','category','action','status'),[
    ('ASSOCIATION_TIMEOUT','CONNECTION','CHECK_CONNECTIVITY','CLASSIFIED'),
    ('ASSOCIATION_REJECTED','CONFIGURATION','CHECK_AE_TITLE','CLASSIFIED'),
    ('UNKNOWN_CALLED_AE_TITLE','CONFIGURATION','CHECK_AE_TITLE','CLASSIFIED'),
    ('OUT_OF_RESOURCES','STORAGE','ALERT_OPERATOR','CLASSIFIED'),
    ('C_STORE_FAILURE','TRANSFER','HUMAN_REVIEW','NEEDS_REVIEW'),
    ('INVALID_DICOM_DATA','DATA_QUALITY','HUMAN_REVIEW','NEEDS_REVIEW'),
    ('UNRECOGNIZED','UNKNOWN','HUMAN_REVIEW','NEEDS_REVIEW'),
])
def test_registered_error_rules(code,category,action,status):
    result=classify(code,0)
    assert (result.category,result.suggested_action,result.status)==(category,action,status)

def test_timeout_at_retry_limit_always_escalates():
    assert classify('ASSOCIATION_TIMEOUT',5).reason_code=='RETRY_BUDGET_REACHED'
    assert classify('ASSOCIATION_TIMEOUT',4).status=='CLASSIFIED'

def test_rule_codes_are_case_and_whitespace_normalized():
    assert classify(' association_timeout ',0)==classify('ASSOCIATION_TIMEOUT',0)
