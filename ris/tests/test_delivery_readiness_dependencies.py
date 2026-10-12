"""Evidence ordering and failure cases without a database or live PACS."""
from types import SimpleNamespace as Row
import pytest
from application.services.finance.delivery_readiness import DeliveryReadiness
from infrastructure.adapters.reporting.delivery_files import ReportDeliveryFiles
from infrastructure.adapters.imaging.delivery_pacs import OrthancDeliveryEvidence


def build(*, method='DEMOGRAPHICS_EXACT', study=None, count=1, gate=True):
    calls=[]
    order=Row(id=1,status='COMPLETED',report=Row(status='FINAL'),pacs_study_id='study',
              pacs_image_count=1,pacs_status='IMAGES_COMPLETE',accession='RIS-A',
              patient=Row(patient_id='RIS-P'))
    match=Row(match_method=method,pacs_patient_id='CONFIRMED-P',pacs_accession='CONFIRMED-A')
    class Repository:
        def current_match(self,*args):calls.append(('match',args));return match
    class Files:
        def matches(self,*args):calls.append(('file',));return True
    class Pacs:
        def study(self,id):
            calls.append(('study',id))
            if isinstance(study,Exception):raise study
            return study if study is not None else dict(ID='study',PatientMainDicomTags={'PatientID':'RIS-P'},MainDicomTags={'AccessionNumber':'RIS-A'})
        def instance_count(self,id):calls.append(('count',id));return count
    def identity(order):calls.append(('gate',));return gate,'synthetic reason'
    return order,DeliveryReadiness(Repository(),report_files=Files(),pacs=Pacs(),demographic_gate=identity),calls


@pytest.mark.parametrize('status',['CANCELLED','REGISTERED','BOOKED'])
def test_terminal_or_unperformed_case_does_not_read_evidence(status):
    order,service,calls=build();order.status=status
    assert not service.delivery_readiness(order,'IMAGES',live=True)[0]
    assert not service.delivery_readiness(order,'REPORT')[0]
    assert calls==[]


@pytest.mark.parametrize('status',['DRAFT','VERIFIED','UNREPORTED'])
def test_nonfinal_report_does_not_read_artifact(status):
    order,service,calls=build();order.report.status=status
    assert not service.report_readiness(order)[0] and calls==[]


def test_cached_snapshot_uses_no_pacs_transport_but_live_check_does():
    order,service,calls=build()
    assert service.snapshot(order)['IMAGES']['allowed']
    assert not any(call[0] in ('study','count') for call in calls)
    calls.clear()
    assert service.delivery_readiness(order,'IMAGES',live=True)==(True,'')
    assert [call[0] for call in calls]==['match','gate','study','count']


def test_demographic_gate_failure_never_contacts_pacs():
    order,service,calls=build(gate=False)
    assert not service.images_readiness(order,live=True)[0]
    assert [call[0] for call in calls]==['match','gate']


@pytest.mark.parametrize('field',['ID','PatientID','AccessionNumber'])
def test_live_identity_mismatch_stops_before_statistics(field):
    study=dict(ID='study',PatientMainDicomTags={'PatientID':'RIS-P'},MainDicomTags={'AccessionNumber':'RIS-A'})
    target=study if field=='ID' else study['PatientMainDicomTags' if field=='PatientID' else 'MainDicomTags']
    target[field]='OTHER'
    order,service,calls=build(study=study)
    assert not service.images_readiness(order,live=True)[0]
    assert not any(call[0]=='count' for call in calls)


@pytest.mark.parametrize('method',['MANUAL_CONFIRMED','OVERRIDE_APPROVED'])
def test_manual_link_uses_recorded_confirmed_identity(method):
    study=dict(ID='study',PatientMainDicomTags={'PatientID':'CONFIRMED-P'},MainDicomTags={'AccessionNumber':'CONFIRMED-A'})
    order,service,calls=build(method=method,study=study)
    assert service.images_readiness(order,live=True)[0]
    study['PatientMainDicomTags']['PatientID']='RIS-P'
    assert not service.images_readiness(order,live=True)[0]


@pytest.mark.parametrize('study,count',[(RuntimeError('offline'),1),([],1),({'ID':'study','PatientMainDicomTags':['bad']},1),(None,0),(None,-1)])
def test_unavailable_malformed_or_empty_pacs_evidence_blocks(study,count):
    order,service,calls=build(study=study,count=count)
    assert not service.images_readiness(order,live=True)[0]


def test_file_evidence_rejects_outside_empty_and_wrong_extension(tmp_path):
    root=tmp_path/'reports';root.mkdir()
    outside=tmp_path/'outside.docx';outside.write_bytes(b'synthetic')
    empty=root/'empty.pdf';empty.touch()
    wrong=root/'wrong.txt';wrong.write_bytes(b'synthetic')
    calls=[]
    files=ReportDeliveryFiles(root,lambda *args:calls.append(args) or {'result':'MATCH'})
    report=Row(pdf_path=str(outside),docx_path=str(empty),source_path=str(wrong))
    assert not files.matches(Row(id=1),report) and calls==[]
    valid=root/'valid.docx';valid.write_bytes(b'synthetic artifact')
    report.source_path=str(valid)
    assert files.matches(Row(id=1),report) and len(calls)==1


def test_file_evidence_checks_later_candidate_after_validation_failure(tmp_path):
    first=tmp_path/'first.pdf';first.write_bytes(b'synthetic')
    second=tmp_path/'second.docx';second.write_bytes(b'synthetic')
    def validate(order,path,suffix):
        if suffix=='.pdf':raise ValueError('Invalid synthetic artifact')
        return {'result':'MATCH'}
    assert ReportDeliveryFiles(tmp_path,validate).matches(Row(id=1),Row(pdf_path=str(first),docx_path=str(second),source_path=None))


def test_transport_escapes_study_identifier_and_checks_http_status():
    calls=[]
    class Response:
        def raise_for_status(self):calls.append('status')
        def json(self):return {'CountInstances':'3'}
    def get(url,**kwargs):calls.append((url,kwargs));return Response()
    pacs=OrthancDeliveryEvidence('http://pacs.invalid',get,lambda:('synthetic','only'))
    assert pacs.instance_count('id/with space')==3
    assert calls==[('http://pacs.invalid/studies/id%2Fwith%20space/statistics',{'auth':('synthetic','only'),'timeout':8}),'status']
