import pytest

from app.evaluation import CATEGORIES, evaluate


def sample(provider='JEV', expected='TRANSFER', predicted='TRANSFER', probabilities=None, latency=10, cost=0.01):
    if probabilities is None and predicted is not None:
        probabilities = {category: (0.9 if category == predicted else 0.02) for category in CATEGORIES}
    return {'provider': provider, 'expected_category': expected, 'predicted_category': predicted,
            'probabilities': probabilities, 'latency_ms': latency, 'cost_usd': cost}


def test_evaluation_reports_aggregate_accuracy_coverage_calibration_and_cost_only():
    report = evaluate([sample(), sample(expected='STORAGE', predicted='TRANSFER', latency=50)])['JEV']
    assert report['sample_count'] == 2
    assert report['coverage'] == 1.0
    assert report['accuracy_on_answered'] == 0.5
    assert report['probability_sample_count'] == 2
    assert report['brier_score'] is not None
    assert report['latency_ms_p50'] == 10.0 and report['latency_ms_p95'] == 50.0
    assert report['cost_usd_per_correct'] == 0.02
    assert report['confusion_matrix']['STORAGE']['TRANSFER'] == 1
    assert 'patient' not in str(report).lower()


def test_evaluation_counts_abstentions_without_scoring_them_as_answers():
    report = evaluate([sample(), sample(expected='STORAGE', predicted=None, probabilities=None)])['JEV']
    assert report['coverage'] == 0.5
    assert report['accuracy_on_answered'] == 1.0
    assert report['confusion_matrix']['STORAGE']['ABSTAIN'] == 1
    assert report['probability_sample_count'] == 1


@pytest.mark.parametrize('bad', [
    {'unexpected': 'field'},
    {**sample(), 'latency_ms': float('nan')},
    {**sample(), 'cost_usd': -1},
    {**sample(), 'probabilities': {category: 0.2 for category in CATEGORIES}},
])
def test_evaluation_rejects_untrusted_or_malformed_rows(bad):
    with pytest.raises(ValueError):
        evaluate([bad])


def test_evaluation_refuses_empty_dataset():
    with pytest.raises(ValueError):
        evaluate([])
