from types import SimpleNamespace
import pytest
from flask import get_flashed_messages, render_template
from technician_image_policy import completion_image_policy


def evidence(**changes):
    values=dict(matched=False,pacs_present=False,error='timeout',image_count=0,
                policy_defined=True,min_images=2,required_series='',series=[])
    values.update(changes)
    return completion_image_policy(**values)


@pytest.mark.parametrize('override',[False,True])
def test_blocked_completion_keeps_structured_evidence_without_state_change(app_ctx,monkeypatch,override):
    result=evidence()
    monkeypatch.setattr(app_ctx,'technician_completion_evidence',lambda _:(result,None))
    order=SimpleNamespace(id=991,exam_status='IN_PROGRESS',status='IN_PROGRESS',exam_completed_at=None)
    decision,_=app_ctx._apply_exam_transition(order,'EXAM_COMPLETED','SUPER_ADMIN' if override else 'TECHNICIAN',override=override)
    assert not decision.allowed and decision.details==result
    assert order.exam_status=='IN_PROGRESS' and order.exam_completed_at is None
    with app_ctx.app.test_request_context():
        app_ctx.flash_exam_transition_blocked(order,decision,'IN_PROGRESS','EXAM_COMPLETED')
        category,payload=get_flashed_messages(with_categories=True)[0]
        assert category=='exam-completion-blocked' and payload['order_id']==991


@pytest.mark.parametrize('language',['en','ar'])
def test_bilingual_message_escapes_series_and_links_to_correct_exam(app_ctx,language):
    result=evidence()
    result['missing_series']=['<script>alert(1)</script>']
    with app_ctx.app.test_request_context():
        html=render_template('exam_completion_message.html',msg={'order_id':991,'details':result},ui_lang=language,ui_phrase=lambda text:__import__('ui_localization').translate(text,language))
    assert ('لا يمكن إنهاء الفحص الآن' if language=='ar' else 'Cannot complete the exam yet') in html
    assert ('الصور المستلمة: 0' if language=='ar' else 'Images received: 0') in html
    assert ('الحد الأدنى المطلوب: 2' if language=='ar' else 'Minimum required: 2') in html
    assert '/technician/991' in html
    assert '<script>' not in html and '&lt;script&gt;' in html


def test_connection_failure_does_not_claim_images_missing(app_ctx):
    result=evidence(matched=True,image_count=4)
    with app_ctx.app.test_request_context():
        html=render_template('exam_completion_message.html',msg={'order_id':991,'details':result})
    assert 'does not necessarily mean they were not sent' in html
    assert 'image count is below' not in html
    assert 'have not been confirmed as belonging' not in html
