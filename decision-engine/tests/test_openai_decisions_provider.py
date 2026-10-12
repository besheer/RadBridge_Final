import json

import httpx
import pytest

from app.providers.openai_decisions import OpenAIUnavailable, suggest_category


def response(category='TRANSFER', confidence=0.91):
    values = ['CONNECTION', 'CONFIGURATION', 'STORAGE', 'TRANSFER', 'DATA_QUALITY', 'UNKNOWN']
    probabilities = [{'value': value, 'probability': confidence if value == category else (1 - confidence) / 5}
                     for value in values]
    return {'model': 'gpt-6-luna', 'usage': {'input_tokens': 30, 'output_tokens': 3}, 'answers': [{
        'type': 'choice', 'name': 'category', 'choice': category,
        'confidence': confidence, 'probabilities': probabilities,
    }]}


def test_openai_adapter_posts_fixed_allowlisted_payload_and_validates_response():
    captured = {}

    def handler(request):
        captured['url'] = str(request.url)
        captured['headers'] = dict(request.headers)
        captured['payload'] = json.loads(request.read())
        return httpx.Response(200, json=response())

    result = suggest_category('C_STORE_FAILURE', 2, api_key='synthetic-test-key',
                              transport=httpx.MockTransport(handler))
    assert result.category == 'TRANSFER' and result.confidence == 0.91
    assert result.probabilities['TRANSFER'] == 0.91
    assert captured['url'] == 'https://api.openai.com/v1/decisions'
    assert captured['headers']['authorization'] == 'Bearer synthetic-test-key'
    assert captured['payload']['model'] == 'gpt-6-luna'
    assert 'C_STORE_FAILURE' in captured['payload']['input']
    assert 'retry count: 2' in captured['payload']['input']
    serialized = json.dumps(captured['payload'])
    assert all(value not in serialized for value in ('branch_id', 'destination_id', 'patient_id', 'accession'))


@pytest.mark.parametrize('code,retries', [('PATIENT-12345', 0), ('C_STORE_FAILURE', 101)])
def test_openai_adapter_rejects_unapproved_evidence_before_network(code, retries):
    called = []
    transport = httpx.MockTransport(lambda request: called.append(request) or httpx.Response(200, json=response()))
    with pytest.raises(OpenAIUnavailable):
        suggest_category(code, retries, api_key='synthetic-test-key', transport=transport)
    assert called == []


def test_openai_adapter_rejects_refusal_and_malformed_probability_sets():
    refusal = httpx.MockTransport(lambda request: httpx.Response(200, json={
        'model': 'gpt-6-luna', 'usage': {'input_tokens': 1, 'output_tokens': 0},
        'answers': [{'type': 'refusal', 'name': 'category'}],
    }))
    with pytest.raises(OpenAIUnavailable):
        suggest_category('C_STORE_FAILURE', 0, api_key='synthetic-test-key', transport=refusal)

    invalid = response()
    invalid['answers'][0]['probabilities'].pop()
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json=invalid))
    with pytest.raises(OpenAIUnavailable):
        suggest_category('C_STORE_FAILURE', 0, api_key='synthetic-test-key', transport=transport)

    invalid_mass = response()
    for item in invalid_mass['answers'][0]['probabilities']:
        item['probability'] = 0.2
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json=invalid_mass))
    with pytest.raises(OpenAIUnavailable):
        suggest_category('C_STORE_FAILURE', 0, api_key='synthetic-test-key', transport=transport)

    malformed = {'model': 'gpt-6-luna', 'usage': {'input_tokens': 1, 'output_tokens': 0},
                 'answers': ['unexpected-shape']}
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json=malformed))
    with pytest.raises(OpenAIUnavailable):
        suggest_category('C_STORE_FAILURE', 0, api_key='synthetic-test-key', transport=transport)


def test_openai_adapter_fails_closed_without_leaking_transport_details():
    def fail(request):
        raise httpx.ReadTimeout('secret URL or header detail')

    with pytest.raises(OpenAIUnavailable, match='Provider request failed') as error:
        suggest_category('C_STORE_FAILURE', 0, api_key='synthetic-test-key',
                         transport=httpx.MockTransport(fail))
    assert 'secret URL' not in str(error.value)
