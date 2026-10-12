import pytest
import httpx
from app.providers.jev import JevUnavailable, suggest_category

def provider_payload(category='TRANSFER', confidence=0.91):
    return {'model':'jev-latest','usage':{'input_tokens':18,'output_tokens':4},'answers':{'category':{
        'type':'choice','choice':category,'confidence':confidence,
        'probabilities':{'CONNECTION':0.01,'CONFIGURATION':0.01,'STORAGE':0.02,
          'TRANSFER':0.91,'DATA_QUALITY':0.03,'UNKNOWN':0.02}}}}

def test_jev_adapter_sends_only_allowlisted_machine_evidence_and_validates_result():
    captured={}
    def handler(request):
        captured['url']=str(request.url)
        captured['headers']=dict(request.headers)
        captured['body']=request.read().decode()
        return httpx.Response(200,json=provider_payload())
    result=suggest_category('C_STORE_FAILURE',2,api_key='synthetic-test-key',
        transport=httpx.MockTransport(handler))
    assert result.category=='TRANSFER' and result.confidence==0.91
    assert result.probabilities['TRANSFER']==0.91
    assert captured['url']=='https://api.typesafe.ai/v1/systemone'
    assert captured['headers']['authorization']=='Bearer synthetic-test-key'
    assert 'C_STORE_FAILURE' in captured['body'] and 'retry_count' in captured['body']
    assert 'branch_id' not in captured['body'] and 'destination_id' not in captured['body']

@pytest.mark.parametrize('code,count',[('VENDOR_ERROR 12345',1),('C_STORE_FAILURE',101)])
def test_jev_rejects_non_allowlisted_or_invalid_evidence(code,count):
    with pytest.raises(JevUnavailable):
        suggest_category(code,count,api_key='synthetic-test-key')

def test_jev_rejects_malformed_or_unexpected_categories():
    transport=httpx.MockTransport(lambda request:httpx.Response(200,json=provider_payload('RUN_RETRY')))
    with pytest.raises(JevUnavailable):
        suggest_category('C_STORE_FAILURE',0,api_key='synthetic-test-key',transport=transport)

def test_jev_transport_failure_fails_closed_without_retry():
    def fail(request):
        raise httpx.ReadTimeout('sensitive transport details')
    transport=httpx.MockTransport(fail)
    with pytest.raises(JevUnavailable,match='Provider request failed'):
        suggest_category('C_STORE_FAILURE',0,api_key='synthetic-test-key',transport=transport)
