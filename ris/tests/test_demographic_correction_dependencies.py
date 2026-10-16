"""Failure boundaries and read-only review without Flask/SQLAlchemy runtime."""
from datetime import date
from types import SimpleNamespace as Row
import pytest
from application.services.registration.demographic_corrections import DemographicCorrections, ReviewDenied
from domain.registration.demographic_correction import normalize_value


class Repository:
    def __init__(self):
        self.patient=Row(id=1,name='Synthetic Patient One',dob='19900101',sex='M',phone='',
                         national_id='',address='',email='',dob_estimated=False)
        self.report=Row(id=3,status='FINAL',version=2,findings='immutable synthetic report')
        self.order=Row(id=2,patient=self.patient,branch_id=4,status='COMPLETED',exam_status='COMPLETED',
                       pacs_study_id='synthetic-study',pacs_image_count=10,report=self.report)
        self.writes=[];self.duplicate=None;self.version_count=1
    def nationality(self,id):return 'Synthetic'
    def orders(self,id):return [self.order]
    def report_version_count(self,id):return self.version_count
    def bookings(self,id):return []
    def visit_count(self,id):return 1
    def booking_count(self,id):return 0
    def open_request(self,id):return self.duplicate
    def lock_patient(self,id):return self.patient
    def add_request(self,order,reason,actor):
        row=Row(id=5,reason=reason,requested_by=actor)
        self.writes.append(('request',row));return row
    def add_detail(self,row,patient,field,old,value,snapshot,impact):
        row.demographic_detail=Row(patient_id=patient.id,field_name=field,old_value=old,
                                  proposed_value=value,snapshot_hash=snapshot,impact_json=impact)
        self.writes.append(('detail',row.demographic_detail))


def build(*, allowed=True, validator=lambda rule,value:(True,'')):
    repo=Repository();audits=[]
    service=DemographicCorrections(repo,registration_rules=lambda:{'patient.phone':'required'},
        validate_registration=validator,actor_id=lambda:7,branch_allowed=lambda order:allowed,
        audit=lambda *args:audits.append(args),today=lambda:date(2026,10,12))
    return repo,service,audits


def test_submit_and_review_preserve_patient_and_final_report():
    repo,service,audits=build()
    patient_before=vars(repo.patient).copy();report_before=vars(repo.report).copy()
    row=service.submit(repo.order,'name','Synthetic Corrected Name','Documented reason',service.snapshot(repo.patient))
    assert row.requested_by==7 and len(repo.writes)==2 and len(audits)==1
    assert row.demographic_detail.old_value==patient_before['name']
    service.assert_approvable(row)
    assert vars(repo.patient)==patient_before and vars(repo.report)==report_before
    assert len(repo.writes)==2 and len(audits)==1


@pytest.mark.parametrize('failure',['stale','duplicate','same','reason'])
def test_request_barriers_write_nothing(failure):
    repo,service,audits=build();preview=service.snapshot(repo.patient)
    value='Synthetic Corrected Name';reason='Documented reason'
    if failure=='stale':repo.version_count+=1
    if failure=='duplicate':repo.duplicate=Row(id=9)
    if failure=='same':value=repo.patient.name
    if failure=='reason':reason='no'
    with pytest.raises(ValueError):service.submit(repo.order,'name',value,reason,preview)
    assert repo.writes==[] and audits==[]


def test_review_requires_access_to_all_affected_orders():
    repo,service,audits=build(allowed=False)
    row=service.submit(repo.order,'sex','F','Documented reason',service.snapshot(repo.patient))
    with pytest.raises(ReviewDenied) as error:service.assert_approvable(row)
    assert error.value.status==403 and repo.patient.sex=='M'


def test_review_rechecks_snapshot_and_current_registration_rules():
    repo,service,audits=build()
    row=service.submit(repo.order,'phone','12345','Documented reason',service.snapshot(repo.patient))
    service.validate_registration=lambda rule,value:(False,'New rule rejects proposed value')
    with pytest.raises(ReviewDenied) as error:service.assert_approvable(row)
    assert error.value.status==409
    service.validate_registration=lambda rule,value:(True,'')
    repo.report.version+=1
    with pytest.raises(ReviewDenied) as error:service.assert_approvable(row)
    assert error.value.status==409


def test_unstructured_review_is_denied_without_writes():
    repo,service,audits=build()
    with pytest.raises(ReviewDenied) as error:service.assert_approvable(Row(demographic_detail=None))
    assert error.value.status==409 and repo.writes==[] and audits==[]


def test_date_validation_uses_explicit_clock():
    assert normalize_value('dob','2026-10-12',date(2026,10,12))=='20261012'
    with pytest.raises(ValueError):normalize_value('dob','2026-10-13',date(2026,10,12))
