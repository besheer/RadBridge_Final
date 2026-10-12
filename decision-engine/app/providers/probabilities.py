"""Validation and normalization for provider category probability maps."""
import math


def normalize_probabilities(values: dict[str, float], categories: frozenset[str]) -> dict[str, float]:
    """Validate a complete near-unit distribution and normalize rounding drift.

    The tolerance accommodates provider serialization rounding. It is not a
    confidence threshold and does not make a model result actionable.
    """
    if not isinstance(values, dict) or set(values) != categories:
        raise ValueError
    probabilities = {name: float(value) for name, value in values.items()}
    if any(not math.isfinite(value) or not 0 <= value <= 1 for value in probabilities.values()):
        raise ValueError
    total = math.fsum(probabilities.values())
    if not math.isfinite(total) or total <= 0 or abs(total - 1.0) > 0.02:
        raise ValueError
    return {name: value / total for name, value in probabilities.items()}
