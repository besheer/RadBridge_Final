"""Booking barriers and lock/write ordering without Flask or a database."""
from types import SimpleNamespace as Row
import pytest
from application.services.registration.appointment_creation import AppointmentCreation


class Repository:
    def __init__(self):
        self.branch=Row(id=1);self.procedure=Row(id=2,modality='DX',duration_min=30)
        self.patient_row=Row(id=3);self.device_row=Row(id=4,branch_id=1,modality='DX')
        self.events=[];self.values=None;self.fail_write=False
    def active_branch(self,id):self.events.append('branch');return self.branch
    def active_procedure(self,id):self.events.append('procedure');return self.procedure
    def patient(self,id):self.events.append('patient');return self.patient_row
    def device(self,id):self.events.append('device');return self.device_row
    def add(self,**values):
        self.events.append('add')
        if self.fail_write:raise RuntimeError('Synthetic persistence failure')
        self.values=values;return Row(id=8,**values)


def build(*, available=True, restriction=''):
    repo=Repository()
    def route(branch,modality):repo.events.append('route');return repo.device_row
    def lock(*args):repo.events.append('lock')
    def restricted(*args):repo.events.append('restriction');return restriction
    def audit(*args):repo.events.append('audit')
    service=AppointmentCreation(repo,procedure_available=lambda *args:available,route_device=route,
        lock_slot=lock,restriction_reason=restricted,actor_id=lambda:7,audit=audit)
    values=dict(branch_id=1,procedure_id=2,patient_id=3,device_id=4,scheduled='2037-02-03T10:00')
    return repo,service,values


def test_booking_locks_and_rechecks_before_write_then_audits_without_commit():
    repo,service,values=build();row=service.create(values)
    assert repo.events==['branch','procedure','patient','device','lock','restriction','add','audit']
    assert row.status=='BOOKED' and row.created_by==7 and row.duration_min==30
    assert row.source=='CALL_CENTER' and row.notes==''


@pytest.mark.parametrize('missing',['branch','procedure','patient_row'])
def test_missing_or_inactive_evidence_stops_before_device_lock_and_writes(missing):
    repo,service,values=build();setattr(repo,missing,None)
    with pytest.raises(ValueError):service.create(values)
    assert repo.values is None and repo.events==['branch','procedure','patient']


def test_unavailable_procedure_stops_before_date_device_and_lock():
    repo,service,values=build(available=False);values['scheduled']='invalid'
    with pytest.raises(ValueError,match='not available'):service.create(values)
    assert repo.events==['branch','procedure','patient'] and repo.values is None


@pytest.mark.parametrize('scheduled',['invalid','2037-02-03T10:00+02:00',None])
def test_invalid_or_timezone_aware_time_cannot_lock_or_write(scheduled):
    repo,service,values=build();values['scheduled']=scheduled
    with pytest.raises((ValueError,TypeError)):service.create(values)
    assert 'lock' not in repo.events and repo.values is None


@pytest.mark.parametrize('problem',['branch','modality','missing'])
def test_wrong_device_cannot_lock_or_write(problem):
    repo,service,values=build()
    if problem=='branch':repo.device_row.branch_id=9
    if problem=='modality':repo.device_row.modality='CT'
    if problem=='missing':repo.device_row=None
    with pytest.raises(ValueError):service.create(values)
    assert 'lock' not in repo.events and repo.values is None


def test_restriction_after_lock_blocks_creation_and_audit():
    repo,service,values=build(restriction='Synthetic overlapping booking')
    with pytest.raises(ValueError,match='overlapping'):service.create(values)
    assert repo.events[-2:]==['lock','restriction'] and repo.values is None


def test_missing_device_uses_router_and_original_duration_source_defaults():
    repo,service,values=build();values['device_id']=None;values['source']='';values['notes']='Synthetic note'
    repo.procedure.duration_min=0;repo.device_row.modality='dx'
    row=service.create(values)
    assert 'route' in repo.events and 'device' not in repo.events
    assert row.duration_min==20 and row.source=='' and row.notes=='Synthetic note'


def test_persistence_failure_propagates_to_transaction_owner_without_success_audit():
    repo,service,values=build();repo.fail_write=True
    with pytest.raises(RuntimeError):service.create(values)
    assert repo.events[-1]=='add' and 'audit' not in repo.events and repo.values is None
