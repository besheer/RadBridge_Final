"""Contact preference storage through explicit repository/settings dependencies."""
import json
from domain.identity.contact_policy import CONTACT_FIELDS


class UserContacts:
    def __init__(self, repository, settings_reader):
        self.repository,self.settings_reader=repository,settings_reader

    def contacts(self, user):
        profile=self.repository.profile(user.id)
        data=self.settings_reader(profile).get('contacts',{}) if profile else {}
        return {key:str(data.get(key,'') or '') for key in CONTACT_FIELDS} if isinstance(data,dict) else {key:'' for key in CONTACT_FIELDS}

    def save(self, user, data, form):
        profile=self.repository.ensure_profile(user)
        settings=self.settings_reader(profile);settings['contacts']=data
        profile.settings_json=json.dumps(settings,ensure_ascii=False)
        if 'department' in form:profile.department=(form.get('department') or '').strip()[:80]
        if 'specialty' in form:profile.specialty=(form.get('specialty') or '').strip()[:120]
