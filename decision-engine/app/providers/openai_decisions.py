"""Fail-closed OpenAI Decisions adapter for sanitized DICOM error categories."""
from dataclasses import dataclass
import math
import os

import httpx
from app.providers.probabilities import normalize_probabilities

ENDPOINT = 'https://api.openai.com/v1/decisions'
MODEL_DEFAULT = 'gpt-6-luna'
ALLOWED_CATEGORIES = frozenset({'CONNECTION', 'CONFIGURATION', 'STORAGE', 'TRANSFER', 'DATA_QUALITY', 'UNKNOWN'})


@dataclass(frozen=True)
class OpenAISuggestion:
    category: str
    confidence: float
    probabilities: dict[str, float]
    model_name: str
    input_tokens: int
    output_tokens: int


class OpenAIUnavailable(Exception):
    """No valid provider suggestion is available; caller must keep human review."""


def _validate_response(data: dict) -> OpenAISuggestion:
    try:
        answers = data['answers']
        if not isinstance(answers, list) or len(answers) != 1:
            raise ValueError
        answer = answers[0]
        if answer.get('name') != 'category' or answer.get('type') != 'choice':
            raise ValueError
        category = answer['choice']
        confidence = float(answer['confidence'])
        probabilities = answer['probabilities']
        if category not in ALLOWED_CATEGORIES or not math.isfinite(confidence) or not 0 <= confidence <= 1:
            raise ValueError
        if not isinstance(probabilities, list) or len(probabilities) != len(ALLOWED_CATEGORIES):
            raise ValueError
        probability_map = normalize_probabilities(
            {item['value']: item['probability'] for item in probabilities}, ALLOWED_CATEGORIES)
        model = data['model']
        usage = data['usage']
        input_tokens, output_tokens = int(usage['input_tokens']), int(usage['output_tokens'])
        if not isinstance(model, str) or not model or len(model) > 80 or min(input_tokens, output_tokens) < 0:
            raise ValueError
        return OpenAISuggestion(category, confidence, probability_map, model, input_tokens, output_tokens)
    except (AttributeError, KeyError, TypeError, ValueError, OverflowError) as exc:
        raise OpenAIUnavailable('Provider response failed validation') from exc


def suggest_category(error_code: str, retry_count: int, *, api_key: str | None = None,
                     model: str | None = None, transport: httpx.BaseTransport | None = None) -> OpenAISuggestion:
    """Ask only about allowlisted machine codes; never transmit branch/AE/patient IDs."""
    key = api_key if api_key is not None else os.environ.get('OPENAI_API_KEY', '')
    if not key:
        raise OpenAIUnavailable('Provider credential is not configured')
    if error_code not in {'C_STORE_FAILURE', 'INVALID_DICOM_DATA'} or not 0 <= retry_count <= 100:
        raise OpenAIUnavailable('Evidence is not eligible for external classification')
    selected_model = model or os.environ.get('OPENAI_DECISIONS_MODEL', MODEL_DEFAULT)
    if selected_model != MODEL_DEFAULT:
        raise OpenAIUnavailable('Configured model is not approved')
    payload = {
        'model': selected_model,
        'input': f'DICOM router error code: {error_code}; retry count: {retry_count}.',
        'questions': [{
            'type': 'choice',
            'name': 'category',
            'instructions': 'Classify this operational DICOM router error only. This is a suggestion; do not recommend or execute an action.',
            'choices': [
                {'value': 'CONNECTION', 'description': 'Network association or connectivity failure.'},
                {'value': 'CONFIGURATION', 'description': 'Endpoint or AE title configuration failure.'},
                {'value': 'STORAGE', 'description': 'Receiver storage capacity or persistence failure.'},
                {'value': 'TRANSFER', 'description': 'DICOM object transfer or storage failure.'},
                {'value': 'DATA_QUALITY', 'description': 'Malformed or invalid DICOM data.'},
                {'value': 'UNKNOWN', 'description': 'Cannot safely classify; send for human review.'},
            ],
        }],
    }
    try:
        with httpx.Client(timeout=httpx.Timeout(4.0, connect=2.0), follow_redirects=False,
                          transport=transport) as client:
            response = client.post(ENDPOINT, headers={'Authorization': f'Bearer {key}'}, json=payload)
        if response.status_code != 200:
            raise OpenAIUnavailable('Provider returned an unsuccessful response')
        return _validate_response(response.json())
    except OpenAIUnavailable:
        raise
    except (httpx.HTTPError, ValueError) as exc:
        raise OpenAIUnavailable('Provider request failed') from exc
