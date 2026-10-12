"""Minimal, fail-closed TypeSafe Jev adapter for sanitized DICOM error categories."""
from dataclasses import dataclass
import math
import os
import httpx

ENDPOINT = 'https://api.typesafe.ai/v1/systemone'
MODEL_DEFAULT = 'jev-latest'
ALLOWED_CATEGORIES = frozenset({'CONNECTION','CONFIGURATION','STORAGE','TRANSFER','DATA_QUALITY','UNKNOWN'})

@dataclass(frozen=True)
class JevSuggestion:
    category: str
    confidence: float
    probabilities: dict[str, float]
    model_name: str
    input_tokens: int
    output_tokens: int

class JevUnavailable(Exception):
    """No valid provider suggestion is available; caller must keep human review."""

def _validate_response(data: dict) -> JevSuggestion:
    try:
        answer = data['answers']['category']
        category = answer['choice']
        confidence = float(answer['confidence'])
        probabilities = answer['probabilities']
        usage = data['usage']
        model = data['model']
        if answer['type'] != 'choice' or category not in ALLOWED_CATEGORIES:
            raise ValueError
        if not math.isfinite(confidence) or not 0 <= confidence <= 1:
            raise ValueError
        if not isinstance(probabilities, dict) or set(probabilities) != ALLOWED_CATEGORIES:
            raise ValueError
        probability_map = {name: float(value) for name, value in probabilities.items()}
        if any(not math.isfinite(value) or not 0 <= value <= 1 for value in probability_map.values()):
            raise ValueError
        if not isinstance(model, str) or not model or len(model) > 80:
            raise ValueError
        input_tokens, output_tokens = int(usage['input_tokens']), int(usage['output_tokens'])
        if input_tokens < 0 or output_tokens < 0:
            raise ValueError
        return JevSuggestion(category, confidence, probability_map, model, input_tokens, output_tokens)
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        raise JevUnavailable('Provider response failed validation') from exc

def suggest_category(error_code: str, retry_count: int, *, api_key: str | None = None,
                     transport: httpx.BaseTransport | None = None) -> JevSuggestion:
    """Ask Jev only about allowlisted machine codes; never transmit branch/AE/patient IDs."""
    key = api_key if api_key is not None else os.environ.get('JEV_API_KEY', '')
    if not key:
        raise JevUnavailable('Provider credential is not configured')
    if error_code not in {'C_STORE_FAILURE','INVALID_DICOM_DATA'} or not 0 <= retry_count <= 100:
        raise JevUnavailable('Evidence is not eligible for external classification')
    payload = {
        'state': {'dicom_error_code': error_code, 'retry_count': retry_count},
        'model': os.environ.get('JEV_MODEL', MODEL_DEFAULT),
        'questions': {'category': {
            'type': 'choice',
            'instructions': 'Choose the operational DICOM transport error category only. This is a suggestion; do not recommend or execute any action.',
            'criteria': {
                'CONNECTION': 'Network association and connectivity failures.',
                'CONFIGURATION': 'AE title or endpoint configuration failures.',
                'STORAGE': 'Receiver storage capacity or persistence failures.',
                'TRANSFER': 'DICOM object transfer or storage failures.',
                'DATA_QUALITY': 'Malformed or invalid DICOM data.',
                'UNKNOWN': 'The error cannot be safely classified.'
            }
        }}
    }
    try:
        with httpx.Client(timeout=httpx.Timeout(4.0, connect=2.0), follow_redirects=False,
                          transport=transport) as client:
            response = client.post(ENDPOINT, headers={'Authorization': f'Bearer {key}'}, json=payload)
        if response.status_code != 200:
            raise JevUnavailable(f'Provider returned HTTP {response.status_code}')
        return _validate_response(response.json())
    except JevUnavailable:
        raise
    except (httpx.HTTPError, ValueError) as exc:
        # Do not propagate response bodies, URLs, or request headers to app logs/errors.
        raise JevUnavailable('Provider request failed') from exc
