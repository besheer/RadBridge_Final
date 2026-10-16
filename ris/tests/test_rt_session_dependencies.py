import hashlib
from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace as Row
import pytest
from application.services.clinical import rt_session_workflow as service
from domain.clinical.rt_course_policy import RTWorkflowError


NOW=datetime(2026,1,1)


class Repository:
    def __init__(self):
        self.calls=[]
        self.course=Row(id=1,branch_id=3,status='ACTIVE',version=1)
        self.plan=Row(id=2,fractions=2,fraction_gy=Decimal('1'))
        self.row=Row(id=4,course_id=1,device_id=5,plan_id=2,number=1,attempt=1,
            status='SCHEDULED',version=1,planned_gy=Decimal('1'),scheduled_at=NOW,
            completion_key='',completion_hash='')
        self.machine=Row(id=5,branch_id=3,operational_status='ACTIVE')
        self.previous=None
    def lock_course(self,id):self.calls.append('course');return self.course
    def fraction(self,id):self.calls.append('preview');return self.row
    def lock_fraction(self,id):self.calls.append('fraction');return self.row
    def device(self,id):self.calls.append('device');return self.machine
    def current_plan(self,id):self.calls.append('plan');return self.plan
    def previous_attempt(self,id,number):self.calls.append('previous');return self.previous
    def create_fraction(self,**values):self.calls.append('create');return Row(id=6,**values)
    def add(self,row):self.calls.append('add')
    def flush(self):self.calls.append('flush')


def policies(repo):
    return service.SessionPolicies(authorize_actor=lambda:repo.calls.append('actor_scope'),
        authorize_course=lambda course:repo.calls.append('course_scope'),
        authorize_device=lambda device:repo.calls.append('device_scope'),actor_id=lambda:7,
        audit=lambda *args:repo.calls.append(('audit',args)),clock=lambda:NOW)


def completion(repo,**changes):
    args=dict(repository=repo,policies=policies(repo),fraction_id=4,expected_version='1',
              values=dict(actual_gy='1',delivery_reference='Synthetic external record',
                          idempotency_key='synthetic-key-12345678',dose_variance_reason=''))
    args.update(changes);return args


def test_start_keeps_course_before_fraction_locks_and_scope_before_mutation():
    repo=Repository()
    course,row=service.start(repository=repo,policies=policies(repo),fraction_id=4,expected_version='1')
    assert repo.calls[:7]==['actor_scope','preview','course','course_scope','fraction','device','device_scope']
    assert row.status=='STARTED' and row.version==2 and row.started_at==NOW and row.operator_id==7
    assert repo.calls[-1][1][0]=='FRACTION_STARTED'


def test_actor_denial_stops_before_any_lookup():
    repo=Repository();args=completion(repo)
    def deny():raise PermissionError('synthetic nurse denial')
    pol=policies(repo)
    args['policies']=service.SessionPolicies(deny,pol.authorize_course,pol.authorize_device,pol.actor_id,pol.audit,pol.clock)
    with pytest.raises(PermissionError):service.complete(**args)
    assert repo.calls==[]


@pytest.mark.parametrize('boundary',['branch','scope'])
def test_device_boundary_precedes_any_session_change(boundary):
    repo=Repository();before=dict(repo.row.__dict__);pol=policies(repo)
    if boundary=='branch':
        repo.machine.branch_id=99
    else:
        def deny(device):raise PermissionError('synthetic device scope')
        pol=service.SessionPolicies(pol.authorize_actor,pol.authorize_course,deny,pol.actor_id,pol.audit,pol.clock)
    with pytest.raises((RTWorkflowError,PermissionError)):
        service.start(repository=repo,policies=pol,fraction_id=4,expected_version='1')
    assert repo.row.__dict__==before and 'plan' not in repo.calls


def test_completed_matching_replay_ignores_stale_version_and_new_plan_without_audit():
    repo=Repository();repo.row.status='COMPLETED';repo.course.status='CANCELLED';repo.plan=None
    repo.row.completion_key='synthetic-key-12345678'
    repo.row.completion_hash=hashlib.sha256(b'["1", "Synthetic external record", ""]').hexdigest()
    before=dict(repo.row.__dict__)
    course,row,accepted=service.complete(**completion(repo,expected_version='invalid'))
    assert not accepted and row.__dict__==before
    assert 'plan' not in repo.calls and not any(isinstance(call,tuple) for call in repo.calls)


def test_completed_changed_payload_is_conflict_and_never_overwrites():
    repo=Repository();repo.row.status='COMPLETED';repo.row.completion_key='synthetic-key-12345678'
    repo.row.completion_hash=hashlib.sha256(b'["1", "Synthetic external record", ""]').hexdigest()
    args=completion(repo);args['values']['actual_gy']='2';before=dict(repo.row.__dict__)
    with pytest.raises(RTWorkflowError) as exc:service.complete(**args)
    assert exc.value.code=='COMPLETION_REPLAY_CONFLICT' and repo.row.__dict__==before


def test_paused_course_allows_recording_started_session_but_not_a_new_start():
    repo=Repository();repo.course.status='PAUSED'
    with pytest.raises(RTWorkflowError):
        service.start(repository=repo,policies=policies(repo),fraction_id=4,expected_version='1')
    repo.row.status='STARTED'
    course,row,accepted=service.complete(**completion(repo))
    assert accepted and row.status=='COMPLETED' and row.actual_gy==Decimal('1')


@pytest.mark.parametrize('boundary',['old_plan','inactive_device','not_started','stale_version'])
def test_completion_barriers_leave_delivered_data_unchanged(boundary):
    repo=Repository();repo.row.status='STARTED';args=completion(repo)
    if boundary=='old_plan':repo.row.plan_id=99
    if boundary=='inactive_device':repo.machine.operational_status='MAINTENANCE'
    if boundary=='not_started':repo.row.status='SCHEDULED'
    if boundary=='stale_version':args['expected_version']='0'
    before=dict(repo.row.__dict__)
    with pytest.raises(RTWorkflowError):service.complete(**args)
    assert repo.row.__dict__==before


def test_actual_variance_requires_reviewed_reason_before_mutation():
    repo=Repository();repo.row.status='STARTED';args=completion(repo);args['values']['actual_gy']='2'
    before=dict(repo.row.__dict__)
    with pytest.raises(ValueError):service.complete(**args)
    assert repo.row.__dict__==before
    args['values']['dose_variance_reason']='Synthetic recorded variance'
    course,row,accepted=service.complete(**args)
    assert accepted and row.planned_gy==Decimal('1') and row.actual_gy==Decimal('2')
    assert row.reason=='Synthetic recorded variance'


def test_rebooking_retains_cancelled_attempt_and_cannot_reuse_delivered_attempt():
    repo=Repository();repo.previous=Row(id=8,attempt=2,status='CANCELLED')
    args=dict(repository=repo,policies=policies(repo),course_id=1,expected_version='1',device_id=5,
              values=dict(number='1',planned_gy='1',reason='Synthetic rebooking',scheduled_at='2026-01-01T13:00:00+03:00'))
    course,row=service.schedule(**args)
    assert row.attempt==3 and row.scheduled_at==datetime(2026,1,1,10)
    assert repo.previous.status=='CANCELLED' and course.version==2
    assert repo.calls[-2]=='flush' and repo.calls[-1][1][3]['previous_attempt_id']==8
    repo.calls=[];repo.previous.status='COMPLETED';args['expected_version']='2'
    with pytest.raises(RTWorkflowError):service.schedule(**args)
    assert 'add' not in repo.calls and course.version==2


def test_cancellation_cannot_change_started_or_completed_session():
    for status in ('STARTED','COMPLETED'):
        repo=Repository();repo.row.status=status;before=dict(repo.row.__dict__)
        with pytest.raises(RTWorkflowError):service.cancel(repository=repo,policies=policies(repo),
            fraction_id=4,expected_version='1',status='CANCELLED',reason='Synthetic cancellation')
        assert repo.row.__dict__==before


def test_reschedule_changes_only_pending_attempt_to_current_plan():
    repo=Repository();repo.row.plan_id=99
    course,row=service.reschedule(repository=repo,policies=policies(repo),fraction_id=4,expected_version='1',
        values=dict(planned_gy='1',reason='Synthetic updated schedule',scheduled_at='2026-01-01T13:00:00+03:00'))
    assert row.plan_id==2 and row.version==2 and row.status=='SCHEDULED'
    assert repo.calls[-1][1][3]['before']['plan_id']==99
