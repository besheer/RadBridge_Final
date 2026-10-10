"""Compatibility facade for the extracted readiness domain policy.

Keep existing imports working while new code depends on domain.readiness.
No business rule, return structure or evidence hash changes in this extraction.
"""
from domain.readiness import (
    _norm,
    evaluate_readiness,
    evaluate_required_series,
    required_series_groups,
)

__all__ = ["evaluate_readiness", "evaluate_required_series", "required_series_groups"]
