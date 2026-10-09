from types import SimpleNamespace
import pytest
from flask import render_template
from ui_localization import translate, role_label, CATALOG


def test_explicit_ui_translation_preserves_technical_and_unknown_values():
    assert translate('Save','ar')=='حفظ'
    assert translate('حفظ','en')=='Save'
    for value in ['PACS','DICOM','C-ECHO','AE Title','DX','CT','MR','1.2.826.0.1.123','CODEX-UAT-UNCHANGED','حسن أحمد علي']:
        assert translate(value,'ar')==value and translate(value,'en')==value
    assert role_label(SimpleNamespace(code='TECHNICIAN',name='Technician'),'ar')=='الفني'
    assert role_label(SimpleNamespace(code='CUSTOM_ROLE',name='My custom role'),'ar')=='My custom role'
    assert all(isinstance(v,list) and len(v)==2 and all(isinstance(x,str) and x for x in v) for v in CATALOG.values())


def render(m,name,lang,**kwargs):
    me=SimpleNamespace(id=1,full_name='CODEX-UAT DISPLAY NAME',username='codex-uat',role=SimpleNamespace(code='SUPER_ADMIN',name='Super Admin'))
    return render_template(name,ui_lang=lang,ui_dir='rtl' if lang=='ar' else 'ltr',me=me,
        ui_phrase=lambda text:translate(text,lang),ui_role=lambda role:role_label(role,lang),**kwargs)


@pytest.mark.parametrize('lang',['en','ar'])
def test_technician_filters_keep_canonical_submitted_values(app_ctx,lang):
    with app_ctx.app.test_request_context():
        body=render(app_ctx,'technician.html',lang,orders=[],image_urls={},attachment_counts={},queue_counts={'waiting':0,'in_progress':0,'returned':0},queue_view='waiting',queue_search=False,return_states={})
    assert '<option value="ROUTINE">' in body
    assert '<option value="URGENT">' in body
    assert '<option value="STAT">' in body
    assert 'CODEX-UAT DISPLAY NAME' in body
    if lang=='ar':assert 'تشغيل الفحوصات' in body and 'إنهاء الفحص' not in body and 'لم تصل صور' not in body
    else:assert 'Exam Operations' in body and 'تشغيل الفحوصات' not in body


@pytest.mark.parametrize('lang',['en','ar'])
def test_connections_show_one_language_and_preserve_ae_host_and_port(app_ctx,lang):
    branch=SimpleNamespace(id=999,code='CODEX-UAT',name='CODEX-UAT BRANCH',active=False)
    endpoint=SimpleNamespace(id=999,branch=branch,branch_id=999,kind='MINI_PACS',ae_title='CODEXUAT',host='uat.invalid',port=4242,active=False,echo_elapsed_ms=None,echo_checked_at=None,echo_message='',echo_result='NOT_TESTED')
    with app_ctx.app.test_request_context():
        body=render(app_ctx,'dicom_connections.html',lang,branches=[branch],endpoints=[endpoint],devices=[],central={'DicomAet':'RADBRIDGE','DicomPort':4242},kinds={'MINI_PACS':'Mini PACS / باكس الفرع'})
    assert 'CODEXUAT' in body and 'uat.invalid' in body and '4242' in body
    assert 'CODEX-UAT BRANCH' in body
    if lang=='ar':assert 'وجهات الفروع' in body and 'Branch destinations' not in body
    else:assert 'Branch destinations' in body and 'وجهات الفروع' not in body


def test_flash_translates_only_text_and_preserves_workflow_payload(app_ctx,monkeypatch):
    from flask import get_flashed_messages
    monkeypatch.setattr(app_ctx,'current_ui_language',lambda:'ar')
    payload={'order_id':999,'details':{'image_count':0,'minimum':2}}
    with app_ctx.app.test_request_context():
        app_ctx.flash('Save','success')
        app_ctx.flash(payload,'exam-completion-blocked')
        msgs=get_flashed_messages(with_categories=True)
        assert msgs==[('success','حفظ'),('exam-completion-blocked',payload)]


def test_all_templates_compile_in_application_environment(app_ctx):
    for name in app_ctx.app.jinja_env.list_templates():
        if name.endswith('.html'):app_ctx.app.jinja_env.get_template(name)


def test_imported_action_guidance_macro_keeps_its_language(app_ctx):
    with app_ctx.app.test_request_context():
        macro=app_ctx.app.jinja_env.get_template('_action_guidance.html').module.action_info
        en=macro('Test','Summary',lang='en')
        ar=macro('اختبار','ملخص',lang='ar')
        assert 'aria-label="Close"' in en
        assert 'aria-label="إغلاق"' in ar


@pytest.mark.parametrize('lang',['en','ar'])
def test_reconciliation_labels_and_imported_guidance_use_selected_language(app_ctx,lang):
    with app_ctx.app.test_request_context():
        body=render(app_ctx,'pacs_reconciliation.html',lang,correction_paused=False,
            can_reconcile=True,demo_mode=False,can_exam_link=True,
            eligible_exam_pairs=[],active_exam_links=[],exceptions=[])
        macro=app_ctx.app.jinja_env.get_template('_action_guidance.html').module.action_info
        guidance=macro('Safe Auto Match','Use after correcting RIS or PACS demographics.',lang=lang)
    if lang=='ar':
        assert 'مراجعة استثناءات PACS' in body and 'PACS Exception Review' not in body
        assert 'إعادة المطابقة التلقائية الآمنة' in body and 'Re-run Safe Auto Match' not in body
        assert 'يُستخدم بعد تصحيح' in guidance and 'Use after correcting' not in guidance
    else:
        assert 'PACS Exception Review' in body and 'مراجعة استثناءات PACS' not in body
        assert 'Use after correcting' in guidance and 'يُستخدم بعد تصحيح' not in guidance
