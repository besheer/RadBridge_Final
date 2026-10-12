from datetime import date
from decimal import Decimal
from types import SimpleNamespace as Row
import pytest
from application.services.clinical.rt_plan_workflow import record_plan
from domain.clinical.rt_course_policy import RTWorkflowError


class Repository:
    def __init__(self):
        self.calls=[]
        self.course=Row(id=1,patient_id=2,branch_id=3,primary_order_id=4,status='DRAFT',version=1)
        self.started=None;self.delivered=None;self.file=Row(patient_id=2,order_id=4)
        self.prior=None
    def lock_course(self,id):self.calls.append('course');return self.course
    def started_fraction(self,id):self.calls.append('started');return self.started
    def latest_delivered_fraction(self,id):self.calls.append('delivered');return self.delivered
    def attachment(self,id):self.calls.append('attachment');return self.file
    def current_plan(self,id):self.calls.append('prior');return self.prior
    def maximum_revision(self,id):self.calls.append('revision');return 2
    def create_plan(self,**values):self.calls.append('create');return Row(id=5,**values)
    def add(self,row):self.calls.append('add')
    def flush(self):self.calls.append('flush')


def arguments(repo):
    return dict(repository=repo,authorize_actor=lambda:repo.calls.append('actor_scope'),
        authorize_course=lambda course:repo.calls.append('course_scope'),actor_id=lambda:7,
        audit=lambda *args:repo.calls.append(('audit',args)),today=lambda:date(2026,1,1),
        course_id=1,expected_version='1',values=dict(fractions='2',approved_on='2020-01-01',
        external_reference='Synthetic approved document',approved_by='Synthetic external approver',
        target='Synthetic record',total_gy='2',fraction_gy='1',reason='Synthetic reviewed record'))


def test_actor_denial_precedes_course_lock():
    repo=Repository();args=arguments(repo)
    def deny():raise PermissionError('synthetic nursing denial')
    args['authorize_actor']=deny
    with pytest.raises(PermissionError):record_plan(**args)
    assert repo.calls==[]


def test_stale_version_stops_before_delivery_queries():
    repo=Repository();args=arguments(repo);args['expected_version']='0'
    with pytest.raises(RTWorkflowError) as exc:record_plan(**args)
    assert exc.value.code=='STALE_COURSE_VERSION'
    assert repo.calls==['actor_scope','course','course_scope']


@pytest.mark.parametrize('status',['COMPLETED','CANCELLED'])
def test_terminal_course_never_reads_or_mutates_plan(status):
    repo=Repository();repo.course.status=status
    with pytest.raises(RTWorkflowError):record_plan(**arguments(repo))
    assert repo.calls==['actor_scope','course','course_scope']


def test_started_fraction_blocks_plan_change():
    repo=Repository();repo.started=Row(id=8)
    with pytest.raises(RTWorkflowError) as exc:record_plan(**arguments(repo))
    assert exc.value.code=='PLAN_EDIT_BLOCKED' and 'delivered' not in repo.calls


def test_reduced_count_cannot_remove_delivered_fraction():
    repo=Repository();repo.delivered=Row(number=3)
    with pytest.raises(RTWorkflowError):record_plan(**arguments(repo))
    assert 'prior' not in repo.calls and 'create' not in repo.calls


def test_future_external_approval_is_rejected_before_attachment_lookup():
    repo=Repository();args=arguments(repo);args['values']['approved_on']='2027-01-01';args['attachment_id']=8
    with pytest.raises(ValueError,match='Approval date cannot be in the future'):record_plan(**args)
    assert 'attachment' not in repo.calls and 'create' not in repo.calls


def test_wrong_patient_attachment_is_rejected_without_superseding_plan():
    repo=Repository();repo.file.patient_id=99;args=arguments(repo);args['attachment_id']=8
    with pytest.raises(RTWorkflowError) as exc:record_plan(**args)
    assert exc.value.code=='PLAN_ATTACHMENT_MISMATCH' and 'prior' not in repo.calls


def test_valid_plan_creates_revision_preserving_prior_prescription_and_audits_after_flush():
    repo=Repository();repo.prior=Row(id=9,status='ACTIVE',total_gy=Decimal('4'),fraction_gy=Decimal('2'),fractions=2)
    course,plan=record_plan(**arguments(repo))
    assert plan.revision==3 and plan.total_gy==Decimal('2') and plan.recorded_by==7
    assert repo.prior.status=='SUPERSEDED'
    assert (repo.prior.total_gy,repo.prior.fraction_gy,repo.prior.fractions)==(Decimal('4'),Decimal('2'),2)
    assert course.status=='ACTIVE' and course.version==2
    assert repo.calls[-2]=='flush'
    assert repo.calls[-1][1][0]=='EXTERNAL_PLAN_RECORDED'
    assert repo.calls[-1][1][3]['source']=='MANUAL'


def test_invalid_amount_does_not_supersede_or_add():
    repo=Repository();repo.prior=Row(id=9,status='ACTIVE');args=arguments(repo);args['values']['total_gy']='nan'
    with pytest.raises(ValueError):record_plan(**args)
    assert repo.prior.status=='ACTIVE' and 'add' not in repo.calls
