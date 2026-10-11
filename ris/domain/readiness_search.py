"""Search ranking only; a search result does not establish patient identity."""
from domain.readiness_resolution import normalize


def score(values, needle):
    best = 0
    for value, weight in values:
        current = normalize(value)
        if current == needle:
            best = max(best, weight)
        elif needle and needle in current:
            best = max(best, weight - 20)
    return best
