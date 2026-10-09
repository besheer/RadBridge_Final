import json
from types import SimpleNamespace

import pytest


@pytest.mark.parametrize('layout', ['50_50','70_30','30_70','FULL_EDITOR','FULL_VIEWER','DUAL_MONITOR','CASCADE','NEW_WINDOW'])
def test_layout_roundtrip_preserves_unrelated_profile_settings(app_ctx, layout):
    profile=SimpleNamespace(settings_json=json.dumps({'unrelated': {'keep': 17}}))
    result=app_ctx.set_user_reporting_preferences(profile,'ONLYOFFICE',layout,'OTHER')
    assert app_ctx.user_reporting_preferences(profile)==result
    assert result['preferred_layout']==layout and result['preferred_display']=='OTHER'
    assert json.loads(profile.settings_json)['unrelated']=={'keep':17}


def test_invalid_preferences_fail_back_to_supported_layout(app_ctx):
    profile=SimpleNamespace(settings_json='{}')
    result=app_ctx.set_user_reporting_preferences(profile,'INVALID','javascript:bad','invalid')
    assert result=={'preferred_editor':'ONLYOFFICE','preferred_layout':'50_50','preferred_display':'CURRENT'}


def test_legacy_save_preserves_existing_display(app_ctx):
    profile=SimpleNamespace(settings_json='{"reporting":{"preferred_display":"OTHER"}}')
    result=app_ctx.set_user_reporting_preferences(profile,'ONLYOFFICE','70_30')
    assert result['preferred_display']=='OTHER'


def test_each_doctor_profile_is_independent(app_ctx):
    first=SimpleNamespace(settings_json='{}');second=SimpleNamespace(settings_json='{}')
    app_ctx.set_user_reporting_preferences(first,'ONLYOFFICE','CASCADE','OTHER')
    assert app_ctx.user_reporting_preferences(second)=={'preferred_editor':'ONLYOFFICE','preferred_layout':'50_50','preferred_display':'CURRENT'}


@pytest.mark.parametrize('raw',['not json','[]','{"reporting":"corrupt"}'])
def test_corrupt_stored_profile_does_not_break_viewer_preferences(app_ctx, raw):
    assert app_ctx.user_reporting_preferences(SimpleNamespace(settings_json=raw))=={'preferred_editor':'ONLYOFFICE','preferred_layout':'50_50','preferred_display':'CURRENT'}
