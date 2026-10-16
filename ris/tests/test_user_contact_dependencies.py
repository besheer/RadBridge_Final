import json
from types import SimpleNamespace as Row
import pytest
from application.services.identity.user_contacts import UserContacts
from domain.identity.user_management import can_manage_target


class Repository:
    def __init__(self, profile):self.row=profile;self.calls=[]
    def profile(self,id):self.calls.append(('read',id));return self.row
    def ensure_profile(self,user):self.calls.append(('ensure',user.id));return self.row


def test_contacts_preserve_other_settings_and_omitted_profile_fields():
    profile=Row(settings_json=json.dumps(dict(reporting={'preferred_editor':'ONLYOFFICE'},clinical_scope={'enabled':True})),department='Earlier',specialty='MR')
    repo=Repository(profile);service=UserContacts(repo,lambda p:json.loads(p.settings_json))
    user=Row(id=7)
    service.save(user,dict(phone='+201000000000'),{})
    settings=json.loads(profile.settings_json)
    assert settings['reporting']=={'preferred_editor':'ONLYOFFICE'}
    assert settings['clinical_scope']=={'enabled':True}
    assert profile.department=='Earlier' and profile.specialty=='MR'
    assert service.contacts(user)['phone']=='+201000000000'
    assert repo.calls==[('ensure',7),('read',7)]


def test_malformed_contact_subobject_does_not_expose_other_preference_data():
    repo=Repository(Row(settings_json='{}'))
    service=UserContacts(repo,lambda p:{'contacts':['malformed'],'reporting':{'private':'synthetic'}})
    assert all(value=='' for value in service.contacts(Row(id=7)).values())


@pytest.mark.parametrize('target_permissions,target_code,allowed',[
    (['users.view'],'ORDINARY',True),(['*'],'ORDINARY',False),([], 'SUPER_ADMIN',False),
])
def test_delegated_manager_cannot_modify_protected_target(target_permissions,target_code,allowed):
    actor=Row(active=True,role=Row(code='IT',permissions=lambda:['users.view','users.manage']))
    target=Row(role=Row(code=target_code,permissions=lambda:target_permissions))
    assert can_manage_target(actor,target)==allowed


def test_role_assignment_requires_permission_subset_and_active_actor():
    actor=Row(active=True,role=Row(code='IT',permissions=lambda:['users.view','users.manage']))
    role=Row(code='RADIOLOGIST',permissions=lambda:['reports.edit'])
    assert not can_manage_target(actor,role=role)
    actor.role=Row(code='SUPER_ADMIN')
    assert can_manage_target(actor,role=role)
    actor.active=False
    assert not can_manage_target(actor,role=role)
