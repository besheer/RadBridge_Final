from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from werkzeug.exceptions import Forbidden


@pytest.fixture
def review(app_ctx, monkeypatch):
    import coordinator_bulk_assignment as bulk
    m=app_ctx
    order=SimpleNamespace(id=6,accession='CODEX-UAT-REVIEW',branch_id=42)
    monkeypatch.setattr(m,'Order',SimpleNamespace(query=SimpleNamespace(get_or_404=lambda oid:order)))
    monkeypatch.setattr(bulk,'actor',lambda module:SimpleNamespace(branch_id=42))
    monkeypatch.setattr(m,'has_perm',lambda perm:False)
    monkeypatch.setattr(m,'assignment_readiness_decision',Mock())
    monkeypatch.setattr(m,'manual_assign_order',Mock())
    monkeypatch.setattr(m,'offer_next_doctor',Mock())
    monkeypatch.setattr(m.db.session,'commit',Mock())
    return m,order,bulk


def test_get_opens_filtered_review_without_assigning(review):
    m,order,_=review
    with m.app.test_request_context('/orders/6/assign'):
        response=m.assign_case.__wrapped__(6)
    assert response.status_code==302
    assert '/coordinator/manual-assignment?' in response.location
    assert 'view=all' in response.location and 'q=CODEX-UAT-REVIEW' in response.location
    m.assignment_readiness_decision.assert_not_called()
    m.manual_assign_order.assert_not_called()
    m.offer_next_doctor.assert_not_called()
    m.db.session.commit.assert_not_called()


def test_get_rejects_other_branch(review):
    m,order,_=review;order.branch_id=99
    with m.app.test_request_context('/orders/6/assign'),pytest.raises(Forbidden):
        m.assign_case.__wrapped__(6)


def test_get_preserves_bulk_actor_restrictions(review,monkeypatch):
    m,_,bulk=review
    def deny(module):module.abort(403)
    monkeypatch.setattr(bulk,'actor',deny)
    with m.app.test_request_context('/orders/6/assign'),pytest.raises(Forbidden):
        m.assign_case.__wrapped__(6)


def test_get_allows_explicit_global_scope(review,monkeypatch):
    m,order,_=review;order.branch_id=99
    monkeypatch.setattr(m,'has_perm',lambda perm:perm=='*')
    with m.app.test_request_context('/orders/6/assign'):
        assert m.assign_case.__wrapped__(6).status_code==302


def test_assignment_route_supports_get_and_post(app_ctx):
    rule=next(r for r in app_ctx.app.url_map.iter_rules() if r.endpoint=='assign_case')
    assert {'GET','POST'}.issubset(rule.methods)
