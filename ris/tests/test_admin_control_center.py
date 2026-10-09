from admin_control_center import ENTRIES, visible_sections
import pytest

def test_catalogue_has_valid_unique_page_links(app_ctx):
    with app_ctx.app.test_request_context():
        sections=visible_sections(lambda _:True,app_ctx.url_for if hasattr(app_ctx,'url_for') else __import__('flask').url_for,app_ctx.app.view_functions)
        urls=[x['url'] for s in sections for x in s['links']]
        assert len(urls)>=60 and len(urls)==len(set(urls))
        for group,endpoint,permissions,en,ar in ENTRIES:
            assert endpoint in app_ctx.app.view_functions, endpoint
            rules=[r for r in app_ctx.app.url_map.iter_rules(endpoint) if not r.arguments and 'GET' in r.methods]
            assert rules, endpoint
            assert en and ar and permissions
        assert '/admin/pacs/discovery' in urls and '/admin/dicom-connections' in urls
        assert '/admin/report-header' in urls

def test_sections_do_not_expose_other_permissions():
    endpoints={e[1] for e in ENTRIES}
    sections=visible_sections(lambda p:p=='devices.manage',lambda e:'/'+e,endpoints)
    urls=[x['url'] for s in sections for x in s['links']]
    assert '/dicom_connections_page' in urls
    assert '/admin_users' not in urls and '/admin_audit' not in urls
    assert all(s['links'] for s in sections)
    assert visible_sections(lambda _:False,lambda e:'/'+e,endpoints)==[]

@pytest.mark.parametrize('path',['/admin','/admin/'])
def test_admin_aliases_preserve_authorization(app_ctx,monkeypatch,path):
    monkeypatch.setattr(app_ctx,'current_user',lambda:__import__('types').SimpleNamespace(active=True,id=None,role=None))
    monkeypatch.setattr(app_ctx,'has_perm',lambda _:False)
    monkeypatch.setattr(app_ctx,'render_template',lambda template,**kw: __import__('flask').jsonify(kw))
    client=app_ctx.app.test_client()
    assert client.get(path).status_code==403
    monkeypatch.setattr(app_ctx,'has_perm',lambda p:p=='devices.manage')
    monkeypatch.setattr(app_ctx,'render_template',lambda template,**kw: __import__('flask').jsonify(kw))
    response=client.get(path)
    assert response.status_code==200
    links=[x['url'] for s in response.json['sections'] for x in s['links']]
    assert '/admin/dicom-connections' in links and '/admin/users' not in links

def test_admin_template_supports_both_languages(app_ctx):
    from flask import render_template
    with app_ctx.app.test_request_context():
        me=__import__('types').SimpleNamespace(id=1,full_name='CODEX UAT',role=__import__('types').SimpleNamespace(code='SUPER_ADMIN',name='Super Admin'))
        en=render_template('admin.html',sections=[],ui_lang='en',me=me)
        ar=render_template('admin.html',sections=[],ui_lang='ar',me=me)
        assert 'Admin Control Centre' in en and 'Search control panels' in en
        assert 'مركز تحكم الإدارة' in ar and 'بحث في لوحات التحكم' in ar
        assert 'dir="rtl"' in ar and 'dir="ltr"' in en



