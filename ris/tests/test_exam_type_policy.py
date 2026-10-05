import pytest
from exam_type_policy import exam_type_match


def check(procedure,part,modality='MR',**changes):
    values=dict(expected_modality='MR',procedure=procedure,study_description='',
                series=[{'body_part':part,'modality':modality,'instance_count':10}],block_unknown=True)
    values.update(changes)
    return exam_type_match(**values)


@pytest.mark.parametrize('requested,received',[
    ('MRI Knee','CSPINE'),('MRI Cervical Spine','LSPINE'),('MRI Brain','ABDOMEN'),
    ('رنين فقرات عنقية','LSPINE'),('رنين ركبة','CSPINE'),('رنين مخ','ABDOMEN'),
])
def test_wrong_region_blocks(requested,received):
    result=check(requested,received)
    assert result['status']=='MISMATCH' and not result['allowed']


@pytest.mark.parametrize('requested,received',[
    ('MRI Knee','KNEE'),('MRI Cervical Spine','CSPINE'),('MRI Lumbar Spine','LSPINE'),
    ('MRI Brain','HEAD'),('رنين فقرات عنقية','CSPINE'),('رنين مخ','HEAD'),
])
def test_matching_metadata(requested,received):
    result=check(requested,received)
    assert result['status']=='MATCH' and result['allowed']


def test_unknown_never_claimed_as_match():
    assert check('MRI Knee','')['status']=='REVIEW_REQUIRED'
    assert not check('MRI Knee','')['allowed']
    warning=check('MRI Knee','',block_unknown=False)
    assert warning['allowed'] and warning['status']=='REVIEW_REQUIRED'


def test_extra_conflicting_series_not_hidden_by_matching_description():
    result=check('MRI Knee','CSPINE',study_description='MRI Knee')
    assert result['status']=='MISMATCH'


def test_wrong_modality_blocks_even_when_body_part_matches():
    assert check('MRI Knee','KNEE',modality='CT')['status']=='MISMATCH'


def test_cr_and_dx_equivalence():
    assert check('XRay Knee','KNEE',modality='CR',expected_modality='DX')['allowed']


def test_empty_series_not_evidence():
    assert not check('MRI Knee','KNEE',series=[{'body_part':'KNEE','modality':'MR','instance_count':0}])['allowed']


def test_word_boundary_does_not_guess_from_substring():
    assert check('Unmapped examination','KNEE')['status']=='REVIEW_REQUIRED'


def test_multi_region_requires_all_expected_regions():
    assert not check('MRI Abdomen Pelvis','ABDOMEN')['allowed']


def test_auxiliary_dicom_objects_are_not_wrong_modality_acquisitions():
    result=check('MRI Knee','KNEE',series=[
        {'body_part':'KNEE','modality':'MR','instance_count':20},
        {'body_part':'','modality':'SR','instance_count':1}])
    assert result['allowed']
