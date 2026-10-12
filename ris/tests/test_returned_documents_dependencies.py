"""Required evidence order and short-circuiting without ORM, HTTP or runtime bindings."""
from types import SimpleNamespace as Row
import pytest
from application.services.clinical.returned_documents import ReturnedDocuments


def build(rule=None, history=True, count=1):
    calls = []
    class Repository:
        def has_history(self, order_id):
            calls.append(('history', order_id))
            return history
    def quality(order):
        calls.append(('rule', order.id))
        return rule
    def attachments(order):
        calls.append(('attachments', order.id))
        return count
    return ReturnedDocuments(Repository(), quality_rule=quality, attachment_count=attachments), calls


def test_no_requirements_do_not_query_documents():
    service, calls = build()
    assert service.ready(Row(id=7), {'reason': ''})
    assert calls == [('rule', 7)]


@pytest.mark.parametrize('rule,reason', [
    (None, 'MISSING_HISTORY'),
    (Row(require_history=True, require_attachments=True), ''),
])
def test_missing_required_history_stops_before_attachment_query(rule, reason):
    service, calls = build(rule, history=False)
    assert not service.ready(Row(id=7), {'reason': reason})
    assert calls == [('rule', 7), ('history', 7)]


@pytest.mark.parametrize('count,expected', [(0, False), (1, True), (2, True)])
def test_history_and_attachment_requirements_are_independent(count, expected):
    service, calls = build(Row(require_history=True, require_attachments=True), count=count)
    assert service.ready(Row(id=7), {'reason': ''}) is expected
    assert calls == [('rule', 7), ('history', 7), ('attachments', 7)]


def test_attachment_only_requirement_does_not_read_history():
    service, calls = build(Row(require_history=False, require_attachments=True), history=False, count=0)
    assert not service.ready(Row(id=7), {'reason': ''})
    assert calls == [('rule', 7), ('attachments', 7)]


def test_failed_evidence_query_is_not_converted_to_ready():
    class Repository:
        def has_history(self, order_id):
            raise RuntimeError('synthetic unavailable evidence')
    service = ReturnedDocuments(Repository(), quality_rule=lambda order: None,
                                attachment_count=lambda order: 1)
    with pytest.raises(RuntimeError, match='unavailable evidence'):
        service.ready(Row(id=7), {'reason': 'MISSING_HISTORY'})
