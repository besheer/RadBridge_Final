from types import SimpleNamespace as Row
import pytest
from application.services.clinical import rt_course_workflow as service
from domain.clinical.rt_course_policy import RTWorkflowError


class Repository:
    def __init__(self):
        self.calls=[]
        self.order=Row(id=2,patient_id=3,branch_id=4,modality='PT',status='SCHEDULED')
        self.course=Row(id=5,patient_id=3,branch_id=4,version=1,status='DRAFT')
    def find_order(self, accession):self.calls.append('order');return self.order
    def lock_course(self, id):self.calls.append('course');return self.course
    def create_course(self, **values):self.calls.append('create');return Row(id=5,version=1,**values)
    def create_pet_link(self, **values):self.calls.append('link');return Row(id=6,**values)
    def add(self, row):self.calls.append('add')
    def flush(self):self.calls.append('flush')


def arguments(repo):
    return dict(repository=repo,authorize_course=lambda course:repo.calls.append('course_scope'),
                authorize_order=lambda order:repo.calls.append('order_scope'),actor_id=lambda:7,
                audit=lambda *args:repo.calls.append(('audit',args)),course_id=5,expected_version='1',
                accession='Synthetic',purpose='PLANNING_REFERENCE',reason='Synthetic reviewed reference')


def test_course_creation_keeps_authoritative_identity_and_audits_after_flush():
    repo=Repository()
    row=service.create_course(repository=repo,authorize_order=lambda order:repo.calls.append('scope'),
        actor_id=lambda:7,audit=lambda *args:repo.calls.append('audit'),accession='Synthetic',reference='Synthetic course')
    assert (row.primary_order_id,row.patient_id,row.branch_id,row.created_by)==(2,3,4,7)
    assert repo.calls==['order','scope','create','add','flush','audit']


def test_pet_link_scope_and_version_precede_order_lookup():
    repo=Repository(); args=arguments(repo);args['expected_version']='0'
    with pytest.raises(RTWorkflowError) as exc:service.link_pet(**args)
    assert exc.value.code=='STALE_COURSE_VERSION' and repo.calls==['course','course_scope']
    assert repo.course.version==1


@pytest.mark.parametrize('field,value', [('patient_id',8),('branch_id',8),('modality','CT'),('status','CANCELLED')])
def test_wrong_pet_identity_branch_or_exam_never_mutates(field,value):
    repo=Repository();setattr(repo.order,field,value)
    with pytest.raises(RTWorkflowError) as exc:service.link_pet(**arguments(repo))
    assert exc.value.code=='PET_LINK_IDENTITY_MISMATCH'
    assert repo.calls==['course','course_scope','order','order_scope']
    assert repo.course.version==1


@pytest.mark.parametrize('status',['CANCELLED','COMPLETED'])
def test_terminal_course_blocks_before_order_lookup(status):
    repo=Repository();repo.course.status=status
    with pytest.raises(RTWorkflowError) as exc:service.link_pet(**arguments(repo))
    assert exc.value.code=='COURSE_TERMINAL' and repo.calls==['course','course_scope']


def test_successful_link_preserves_order_and_audits_versioned_result():
    repo=Repository(); before=dict(repo.order.__dict__)
    course,link=service.link_pet(**arguments(repo))
    assert course is repo.course and course.version==2
    assert link.order_id==2 and link.course_id==5 and link.linked_by==7
    assert repo.order.__dict__==before
    assert repo.calls[-2]=='flush' and repo.calls[-1][1][0]=='PET_LINKED'


def test_scope_denial_stops_before_identity_or_mutation():
    repo=Repository();args=arguments(repo)
    def deny(course):raise PermissionError('synthetic scope denial')
    args['authorize_course']=deny
    with pytest.raises(PermissionError):service.link_pet(**args)
    assert repo.calls==['course']


def test_invalid_purpose_has_original_bad_request_outcome():
    repo=Repository();args=arguments(repo);args['purpose']='MERGE_IDENTITY'
    with pytest.raises(RTWorkflowError) as exc:service.link_pet(**args)
    assert exc.value.code=='INVALID_PET_PURPOSE' and 'add' not in repo.calls
