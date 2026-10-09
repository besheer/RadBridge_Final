from datetime import datetime
from types import SimpleNamespace
import pytest


def order(name='محمد أحمد علي', worklist=''):
    return SimpleNamespace(id=-98765, contract=None, patient=SimpleNamespace(name=name,worklist_name=worklist,
        patient_id='CODEX-UAT-MWL-LATIN',dob='19900101',sex='M'),
        accession='CDUATLATIN',procedure='CODEX UAT X-Ray',station_ae='CODEXUAT',
        modality='DX',scheduled=datetime(2037,2,3,10,30))


@pytest.mark.parametrize('manual',['','محمد^أحمد^علي','MOHAMED AHMED ALI'])
def test_actual_mwl_payload_is_latin_and_original_identity_is_preserved(app_ctx,monkeypatch,manual):
    m=app_ctx
    case=order(worklist=manual)
    before=vars(case.patient).copy()
    calls=[]
    def post(url,**kwargs):
        calls.append(kwargs['json']['Tags'])
        return SimpleNamespace(ok=True,json=lambda:{'ID':'synthetic'})
    monkeypatch.setattr(m.requests,'post',post)
    assert m.send_mwl(case)=={'ID':'synthetic'}
    tags=calls[0]
    assert tags['PatientName'].isascii()
    assert tags['PatientName']==m.dicom_worklist_patient_name(case.patient)
    assert tags['PatientID']==case.patient.patient_id
    assert tags['PatientBirthDate']=='19900101' and tags['PatientSex']=='M'
    assert tags['AccessionNumber']==case.accession
    assert tags['ScheduledProcedureStepSequence'][0]['ScheduledStationAETitle']=='CODEXUAT'
    assert vars(case.patient)==before
    if manual=='MOHAMED AHMED ALI':assert tags['PatientName']=='MOHAMED^AHMED^ALI'


@pytest.mark.parametrize('name,manual',[('张三',''),('محمد أحمد علي','张三'),('A'*65,''),('12345','')])
def test_unsafe_or_overlong_name_is_blocked_before_network_send(app_ctx,monkeypatch,name,manual):
    monkeypatch.setattr(app_ctx.requests,'post',lambda *a,**k:pytest.fail('Invalid name must not leave RIS'))
    with pytest.raises(ValueError):app_ctx.send_mwl(order(name,manual))


def test_registration_uses_reviewed_name_or_suggestion_and_keeps_original(app_ctx):
    form={'new_first_name':'محمد','new_middle_name':'أحمد','new_third_name':'علي'}
    assert app_ctx._rb_registration_v2_patient_name(form)=='محمد أحمد علي'
    assert app_ctx._rb_registration_v2_worklist_name(form).isascii()
    form['new_worklist_name']='Mohamed Ahmed Aly'
    assert app_ctx._rb_registration_v2_worklist_name(form)=='MOHAMED AHMED ALY'
    assert app_ctx._rb_registration_v2_patient_name(form)=='محمد أحمد علي'


def test_long_multiword_name_keeps_every_word_in_a_valid_component_group(app_ctx):
    patient=order('ONE TWO THREE FOUR FIVE SIX SEVEN').patient
    value=app_ctx.dicom_worklist_patient_name(patient)
    assert value.count('^')==4
    assert value.replace('^',' ')==patient.name
