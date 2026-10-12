"""Offline metrics for synthetic or approved de-identified labeled results."""
from collections import Counter, defaultdict
import math
from typing import Any

from app.providers.probabilities import normalize_probabilities

CATEGORIES = frozenset({'CONNECTION', 'CONFIGURATION', 'STORAGE', 'TRANSFER', 'DATA_QUALITY', 'UNKNOWN'})
PROVIDERS = frozenset({'RULES', 'JEV', 'OPENAI_DECISIONS'})
FIELDS = frozenset({'provider', 'expected_category', 'predicted_category', 'probabilities', 'latency_ms', 'cost_usd'})


def _percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, math.ceil(percentile * len(ordered)) - 1)
    return round(ordered[index], 6)


def _validate_row(row: Any) -> dict[str, Any]:
    if not isinstance(row, dict) or set(row) != FIELDS:
        raise ValueError('Evaluation row has an invalid field set')
    if row['provider'] not in PROVIDERS or row['expected_category'] not in CATEGORIES:
        raise ValueError('Evaluation row has an unknown provider or category')
    predicted = row['predicted_category']
    if predicted is not None and predicted not in CATEGORIES:
        raise ValueError('Evaluation row has an unknown prediction')
    latency = float(row['latency_ms'])
    cost = float(row['cost_usd'])
    if not math.isfinite(latency) or latency < 0 or not math.isfinite(cost) or cost < 0:
        raise ValueError('Evaluation latency and cost must be finite and nonnegative')
    probabilities = row['probabilities']
    if probabilities is not None:
        probabilities = normalize_probabilities(probabilities, CATEGORIES)
        if predicted is None:
            raise ValueError('Abstentions cannot include a predicted probability distribution')
    return {**row, 'latency_ms': latency, 'cost_usd': cost, 'probabilities': probabilities}


def evaluate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Summarize provider and rules results; raw examples are never returned."""
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        validated = _validate_row(row)
        grouped[validated['provider']].append(validated)
    if not grouped:
        raise ValueError('At least one evaluation row is required')

    summary = {}
    for provider, samples in sorted(grouped.items()):
        matrix = {expected: Counter() for expected in sorted(CATEGORIES)}
        correct = answered = 0
        latencies = []
        costs = 0.0
        brier_scores = []
        for sample in samples:
            expected, predicted = sample['expected_category'], sample['predicted_category']
            matrix[expected][predicted if predicted is not None else 'ABSTAIN'] += 1
            latencies.append(sample['latency_ms'])
            costs += sample['cost_usd']
            if predicted is not None:
                answered += 1
                correct += predicted == expected
            if sample['probabilities'] is not None:
                brier_scores.append(math.fsum(
                    (sample['probabilities'][category] - float(category == expected)) ** 2
                    for category in CATEGORIES))

        precisions = []
        recalls = []
        for category in CATEGORIES:
            tp = matrix[category][category]
            predicted_count = sum(counts[category] for counts in matrix.values())
            support = sum(matrix[category].values())
            if predicted_count:
                precisions.append(tp / predicted_count)
            if support:
                recalls.append(tp / support)
        summary[provider] = {
            'sample_count': len(samples),
            'coverage': round(answered / len(samples), 6),
            'accuracy_on_answered': round(correct / answered, 6) if answered else None,
            'macro_precision': round(math.fsum(precisions) / len(precisions), 6) if precisions else None,
            'macro_recall': round(math.fsum(recalls) / len(recalls), 6) if recalls else None,
            'brier_score': round(math.fsum(brier_scores) / len(brier_scores), 6) if brier_scores else None,
            'probability_sample_count': len(brier_scores),
            'latency_ms_p50': _percentile(latencies, 0.50),
            'latency_ms_p95': _percentile(latencies, 0.95),
            'cost_usd_total': round(costs, 8),
            'cost_usd_per_correct': round(costs / correct, 8) if correct else None,
            'confusion_matrix': {expected: dict(sorted(counts.items())) for expected, counts in matrix.items()},
        }
    return summary
