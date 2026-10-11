from types import SimpleNamespace as Row
import pytest
from application.services.readiness.order_search import search_ris_orders


class Repository:
    def __init__(self, rows=()): self.rows = rows; self.calls = []
    def candidates(self, query, limit): self.calls.append((query, limit)); return self.rows


def row(id, accession='', patient_id='', name='', procedure='', uid=''):
    return Row(id=id, accession=accession, procedure=procedure, study_instance_uid=uid,
               patient=Row(patient_id=patient_id, name=name))


def test_rank_exact_identifiers_before_names_and_partial_matches():
    rows = [row(8, name='MATCH'), row(7, accession='MATCH-extra'),
            row(6, patient_id='MATCH'), row(5, accession='MATCH'), row(9, uid='MATCH')]
    repo = Repository(rows)
    assert [r.id for r in search_ris_orders(repository=repo, query=' MATCH ')] == [5,9,6,8,7]
    assert repo.calls == [('MATCH',50)]
    assert [r.id for r in rows] == [8,7,6,5,9]


@pytest.mark.parametrize('limit,expected', [(1000,100),(-1,1),(0,50),('2',2)])
def test_repository_gets_bounded_window_before_ranking(limit, expected):
    repo = Repository()
    assert search_ris_orders(repository=repo, query='synthetic', limit=limit) == []
    assert repo.calls == [('synthetic', expected)]


def test_empty_query_never_queries_or_parses_limit():
    repo = Repository()
    assert search_ris_orders(repository=repo, query=' ', limit='invalid') == []
    assert repo.calls == []


def test_ties_preserve_newest_order_first_and_no_shared_repositories():
    first = Repository([row(2,name='Synthetic'),row(1,name='Synthetic')])
    second = Repository([row(3,name='Synthetic')])
    assert [r.id for r in search_ris_orders(repository=first,query='Synthetic')] == [2,1]
    assert [r.id for r in search_ris_orders(repository=second,query='Synthetic')] == [3]
