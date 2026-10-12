from types import SimpleNamespace as Row
from decimal import Decimal
import pytest
from application.services.clinical import rt_support_workflow as service
from domain.clinical.rt_course_policy import RTWorkflowError
from test_rt_session_dependencies import Repository as SessionRepository,policies


class Repository(SessionRepository):
    def __init__(self):
        super().__init__();self.started=None;self.completed=2
    def started_fraction(self,id):self.calls.append('started');return self.started
    def completed_count(self,id):self.calls.append('completed');return self.completed
    def create_note(self,**values):self.calls.append('note');return Row(id=8,**values)
    def create_consumable(self,**values):self.calls.append('consumable');return Row(id=9,**values)


def state(repo,**changes):
    args=dict(repository=repo,policies=policies(repo),course_id=1,expected_version='1',target='COMPLETED',reason='Synthetic course close')
    args.update(changes);return args


def test_complete_course_requires_active_plan_and_exact_completed_count():
    repo=Repository();repo.completed=1;before=dict(repo.course.__dict__)
    with pytest.raises(RTWorkflowError):service.change_state(**state(repo))
    assert repo.course.__dict__==before
    repo.completed=2
    course=service.change_state(**state(repo))
    assert course.status=='COMPLETED' and course.version==2
    assert repo.calls[-1][1][3]=={'from':'ACTIVE','to':'COMPLETED','reason':'Synthetic course close'}


@pytest.mark.parametrize('target',['CANCELLED','COMPLETED'])
def test_started_session_prevents_terminal_course_change(target):
    repo=Repository();repo.started=Row(id=7)
    with pytest.raises(RTWorkflowError):service.change_state(**state(repo,target=target))
    assert repo.course.status=='ACTIVE' and repo.course.version==1
    assert 'completed' not in repo.calls


def test_terminal_course_cannot_reopen():
    repo=Repository();repo.course.status='COMPLETED'
    with pytest.raises(RTWorkflowError):service.change_state(**state(repo,target='ACTIVE'))
    assert repo.course.status=='COMPLETED' and 'started' not in repo.calls


def test_notes_keep_course_version_and_do_not_use_dose_actor_guard():
    repo=Repository()
    course,note=service.add_note(repository=repo,policies=policies(repo),course_id=1,kind='NURSING',body='Synthetic preparation')
    assert note.kind=='NURSING' and note.recorded_by==7 and course.version==1
    assert 'actor_scope' not in repo.calls
    assert repo.calls[-2]=='flush' and repo.calls[-1][1][0]=='NOTE_ADDED'


def test_note_cannot_reference_another_course_fraction():
    repo=Repository();repo.row.course_id=99
    with pytest.raises(RTWorkflowError) as exc:
        service.add_note(repository=repo,policies=policies(repo),course_id=1,
            fraction_id=4,kind='TECHNICAL',body='Synthetic note')
    assert exc.value.code=='NOTE_FRACTION_MISMATCH' and 'note' not in repo.calls


def test_note_fraction_scope_is_checked_before_record_creation():
    repo=Repository();repo.machine.branch_id=99
    with pytest.raises(RTWorkflowError):service.add_note(repository=repo,policies=policies(repo),
        course_id=1,fraction_id=4,kind='TECHNICAL',body='Synthetic note')
    assert 'note' not in repo.calls


def test_consumables_record_manual_quantity_without_stock_or_dose_mutation():
    repo=Repository();repo.row.status='COMPLETED';before=dict(repo.row.__dict__)
    course,item=service.add_consumable(repository=repo,policies=policies(repo),fraction_id=4,
        name='Synthetic consumable',quantity='2',unit='EA')
    assert item.quantity==Decimal('2') and item.recorded_by==7
    assert repo.row.__dict__==before and course.version==1
    assert 'actor_scope' not in repo.calls
    assert repo.calls[-1][1][3]['stock_posted'] is False


@pytest.mark.parametrize('status',['CANCELLED','NOT_GIVEN'])
def test_consumable_cannot_be_recorded_for_unperformed_attempt(status):
    repo=Repository();repo.row.status=status
    with pytest.raises(RTWorkflowError):service.add_consumable(repository=repo,policies=policies(repo),
        fraction_id=4,name='Synthetic consumable',quantity='2',unit='EA')
    assert 'consumable' not in repo.calls
