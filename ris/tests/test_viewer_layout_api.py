import json
from types import SimpleNamespace
from unittest.mock import Mock
import pytest

@pytest.fixture
def preference_api(app_ctx,monkeypatch):
    m=app_ctx
    user=SimpleNamespace(id=41)
    profile=SimpleNamespace(settings_json=json.dumps({'unrelated':{'keep':17},'reporting':{'preferred_editor':'ONLYOFFICE','preferred_layout':'70_30','preferred_display':'OTHER'}}))
    monkeypatch.setattr(m,'Order',SimpleNamespace(query=SimpleNamespace(get_or_404=lambda oid:SimpleNamespace(id=oid))))
    monkeypatch.setattr(m,'require_valid_ohif_case_context',lambda order:None)
    monkeypatch.setattr(m,'require_ohif_doctor_user',lambda oid:(user,None))
    get_profile=Mock(side_effect=lambda actor:profile if actor is user else pytest.fail('Must use signed doctor identity'))
    monkeypatch.setattr(m,'get_user_profile',get_profile)
    monkeypatch.setattr(m,'audit_as_user',Mock())
    monkeypatch.setattr(m.db.session,'commit',Mock())
    return m,profile,get_profile

def invoke(m,method='GET',body=None):
    with m.app.test_request_context('/api/ohif/report/16/preferences',method=method,json=body):
        result=m.api_ohif_reporting_preferences.__wrapped__(16)
        return result if isinstance(result,tuple) else (result,200)

def test_get_returns_exact_layout_separate_from_display(preference_api):
    m,profile,_=preference_api
    response,status=invoke(m)
    assert status==200
    assert response.get_json()['preferred_layout']=='70_30'
    assert response.get_json()['preferred_display']=='OTHER'

@pytest.mark.parametrize('layout',['50_50','70_30','30_70','FULL_EDITOR','FULL_VIEWER','DUAL_MONITOR','CASCADE','NEW_WINDOW'])
def test_save_uses_signed_profile_and_preserves_editor_display_and_other_settings(preference_api,layout):
    m,profile,_=preference_api
    response,status=invoke(m,'POST',{'preferred_layout':layout,'user_id':999})
    assert status==200 and response.get_json()['preferred_layout']==layout
    prefs=m.user_reporting_preferences(profile)
    assert prefs=={'preferred_editor':'ONLYOFFICE','preferred_layout':layout,'preferred_display':'OTHER'}
    assert json.loads(profile.settings_json)['unrelated']=={'keep':17}
    assert m.audit_as_user.call_args.args[1]=='OHIF_REPORTING_PREFERENCES_UPDATED'

@pytest.mark.parametrize('body',[{'preferred_layout':'javascript:bad'}, {'preferred_layout':None},[]])
def test_invalid_save_does_not_change_profile_or_commit(preference_api,body):
    m,profile,_=preference_api;before=profile.settings_json
    _,status=invoke(m,'POST',body)
    assert status==400 and profile.settings_json==before
    m.db.session.commit.assert_not_called()

@pytest.mark.parametrize('boundary',['case','doctor'])
def test_context_or_doctor_denial_prevents_profile_write(preference_api,monkeypatch,boundary):
    m,profile,get_profile=preference_api;before=profile.settings_json
    denied=(m.jsonify(ok=False),403)
    if boundary=='case':monkeypatch.setattr(m,'require_valid_ohif_case_context',lambda order:denied)
    else:monkeypatch.setattr(m,'require_ohif_doctor_user',lambda oid:(None,denied))
    _,status=invoke(m,'POST',{'preferred_layout':'30_70'})
    assert status==403 and profile.settings_json==before
    get_profile.assert_not_called();m.db.session.commit.assert_not_called()
