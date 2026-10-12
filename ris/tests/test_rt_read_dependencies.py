from types import SimpleNamespace as Row
import pytest
from application.services.clinical.rt_read_queries import RTReadQueries
from domain.clinical.rt_course_policy import RTWorkflowError


class Repository:
    def __init__(self):
        self.calls=[];self.parent=Row(id=1,branch_id=3)
    def worklist(self,*args):self.calls.append(('worklist',args));return [self.parent]
    def course(self,id):self.calls.append('course');return self.parent
    def current_plan(self,id):self.calls.append('plan');return None
    def devices(self,id):self.calls.append('devices');return [Row(id=4),Row(id=5)]
    def device_matches(self,scope,device):self.calls.append(('device',device.id));return device.id==4
    def plans(self,id):return []
    def fractions(self,id,ids):self.calls.append(('fractions',ids));return []
    def pet_links(self,id):return []
    def notes(self,id,ids):self.calls.append(('notes',ids));return []
    def consumables(self,id,ids):self.calls.append(('consumables',ids));return []


def test_detail_scopes_course_before_device_projection_and_reuses_filtered_ids():
    repo=Repository()
    def scope():repo.calls.append('scope');return {'enabled':True}
    data=RTReadQueries(repo).detail(course_id=1,authorize_course=lambda row:repo.calls.append('authorize'),scope_provider=scope)
    assert repo.calls[:5]==['course','authorize','plan','devices','scope']
    assert [d.id for d in data['devices']]==[4]
    assert repo.calls[-3:]==[('fractions',[4]),('notes',[4]),('consumables',[4])]
    assert data['course'] is repo.parent


def test_missing_or_denied_course_never_reads_scope_or_related_records():
    repo=Repository();repo.parent=None
    with pytest.raises(RTWorkflowError) as exc:
        RTReadQueries(repo).detail(course_id=1,authorize_course=lambda row:1/0,scope_provider=lambda:1/0)
    assert exc.value.code=='COURSE_NOT_FOUND' and repo.calls==['course']
    repo=Repository()
    def deny(row):raise PermissionError('synthetic course scope')
    with pytest.raises(PermissionError):RTReadQueries(repo).detail(course_id=1,authorize_course=deny,scope_provider=lambda:1/0)
    assert repo.calls==['course']


def test_worklist_supplies_authoritative_branch_and_scope_with_trimmed_search():
    repo=Repository();scope={'invalid':True}
    assert RTReadQueries(repo).worklist(global_access=False,branch_id=None,scope=scope,search=' Synthetic ')==[repo.parent]
    assert repo.calls==[('worklist',(False,None,scope,'Synthetic'))]


def test_disabled_scope_does_not_query_device_and_independent_repositories_do_not_share_results():
    repo=Repository();other=Repository()
    assert RTReadQueries(repo).device_allowed(None,Row(id=99))
    assert not RTReadQueries(other).device_allowed({'enabled':True},Row(id=99))
    assert repo.calls==[] and other.calls==[('device',99)]
