"""Read-only candidate search over an explicit repository.

Repository scope/SQL filtering and candidate limit precede ranking, preserving
the original result window. Results confer no permission to reconcile identity.
"""
from domain.readiness_resolution import normalize
from domain.readiness_search import score


def search_ris_orders(*, repository, query, limit=50):
    query = str(query or '').strip()
    if not query:
        return []
    limit = max(1, min(int(limit or 50), 100))
    rows = repository.candidates(query, limit)
    needle = normalize(query)

    def rank(order):
        values = [
            (getattr(order, 'accession', ''), 100),
            (getattr(order.patient, 'patient_id', ''), 95),
            (getattr(order, 'study_instance_uid', ''), 95),
            (str(getattr(order, 'id', '')), 90),
            (getattr(order.patient, 'name', ''), 80),
            (getattr(order, 'procedure', ''), 60),
        ]
        return (-score(values, needle), -order.id)

    return sorted(rows, key=rank)
