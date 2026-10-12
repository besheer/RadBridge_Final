"""Registration validation and visit selection over explicit synthetic facts."""
from types import SimpleNamespace as Row
from datetime import date,datetime
from pathlib import Path
import subprocess
import sys

import pytest
from domain.registration.patient_validation import validate_patient_fields,allowed_registration_branches
from application.services.registration.visit_registration import RegistrationPolicies,select_visit


def test_birth_date_and_sex_validation_use_the_supplied_date_and_rules():
    calls=[]
    def validator(rule,value): calls.append((rule,value));return True,''
    validate_patient_fields({'dob':'20261011','sex':'M'},{'patient.dob':'synthetic-rule'},validator,date(2026,10,11))
    assert ('synthetic-rule','20261011') in calls
    with pytest.raises(ValueError,match='date of birth'):
        validate_patient_fields({'dob':'20261012'},{},validator,date(2026,10,11))
    with pytest.raises(ValueError,match='patient sex'):
        validate_patient_fields({'sex':'INVALID'},{},validator,date(2026,10,11))
    assert allowed_registration_branches(Row(role=Row(code='TECHNICIAN'),branch_id=5))==[5]
    assert allowed_registration_branches(Row(role=Row(code='CALL_CENTER'),branch_id=None)) is None
    assert allowed_registration_branches(None)==[]


class Form(dict):
    def get(self,key,default=None,type=None):
        value=super().get(key,default)
        return type(value) if type and value is not None else value


class Repository:
    def __init__(self):
        self.visit=Row(id=1,patient_id=2,branch_id=3,visit_date=date(2026,10,11),
                       assignment_mode='AUTO',preferred_doctor_id=None,registration_open=False)
        self.members=[];self.events=[]
    def find_visit(self, visit_id): return self.visit
    def lock_and_refresh_visit(self, visit): self.events.append('visit')
    def locked_members(self, visit_id): self.events.append('members');return self.members
    def active_assignment(self, order_id): return None
    def lock_active_doctor(self, doctor_id): return Row(id=doctor_id,role=Row(code='RADIOLOGIST'))
    def doctor_profile(self,doctor_id): return Row(modalities='CT',branches='3')
    def open_appointments(self,visit_id): return []
    def cancel_pending_offers(self, ids, now): self.events.append(('cancel',ids))
    def flush(self): self.events.append('flush')


def policies(repo, capacity=20):
    return RegistrationPolicies(lambda *args:1,lambda perm:True,lambda status:None,
        lambda doctor_id:0,lambda doctor_id:capacity,lambda *args:repo.events.append('audit'),
        lambda:datetime(2026,10,11),lambda *args,**kw:[],lambda *args:None,lambda *args:None)


def select(repo,form,capacity=20):
    return select_visit(repo,policies(repo,capacity),Row(id=2),Row(id=3),datetime(2026,10,11),[Row(modality='CT')],Form(form))


def test_mismatch_fails_before_lock_or_audit():
    repo=Repository();repo.visit.patient_id=99
    with pytest.raises(ValueError,match='same patient, branch and date'):
        select(repo,{'assignment_visit_id':'1'})
    assert repo.events==[]


def test_manual_reservation_checks_capacity_before_mutation():
    repo=Repository()
    with pytest.raises(ValueError,match='capacity'):
        select(repo,{'assignment_mode':'MANUAL','selected_doctor_id':'7'},capacity=0)
    assert repo.visit.preferred_doctor_id is None and repo.visit.assignment_mode=='AUTO'
    assert 'audit' not in repo.events


def test_manual_reservation_survives_later_device_registration():
    repo=Repository();repo.visit.assignment_mode='MANUAL';repo.visit.preferred_doctor_id=7
    assert select(repo,{'assignment_visit_id':'1','assignment_mode':'AUTO'})==1
    assert repo.visit.assignment_mode=='MANUAL' and repo.visit.preferred_doctor_id==7
    assert repo.events==['visit','members','audit','flush']


def test_saved_final_work_blocks_visit_membership_change():
    repo=Repository();repo.members=[Row(id=8,status='FINAL',report=None)]
    with pytest.raises(ValueError,match='completed or saved reporting'):
        select(repo,{'assignment_visit_id':'1'})
    assert repo.events==['visit','members']


def test_services_import_without_database_web_or_runtime():
    ris=str(Path(__file__).resolve().parents[1])
    code="import sys;sys.path.insert(0,%r);import domain.registration.patient_validation;import application.services.registration.visit_registration;assert not any(n == 'flask' or n == 'sqlalchemy' or n.startswith('infrastructure.') or n == 'application.legacy_runtime' for n in sys.modules)" % ris
    subprocess.run([sys.executable,'-c',code],check=True)
