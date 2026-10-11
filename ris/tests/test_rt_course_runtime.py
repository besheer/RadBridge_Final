from test_radiotherapy import f,course,post
from test_technician_return_queue import queue_cases


def test_persisted_pet_link_preserves_identity_and_rejects_stale_retry(f):
    c=course(f); target=f.cases['complete'];target.modality='PT';f.m.db.session.commit()
    before=(target.patient_id,target.branch_id,target.status,target.exam_status)
    original=c.version
    values=dict(version=original,accession=target.accession,purpose='PLANNING_REFERENCE',reason='Synthetic planning reference')
    url=f'/radiotherapy/{c.id}/pet-links'
    assert post(f,url,**values).status_code==302
    link=f.m.rt_models['PetLink'].query.filter_by(course_id=c.id).one()
    assert link.order_id==target.id and link.purpose=='PLANNING_REFERENCE'
    assert c.version==original+1
    assert before==(target.patient_id,target.branch_id,target.status,target.exam_status)
    assert post(f,url,**values).status_code==409
    assert f.m.rt_models['PetLink'].query.filter_by(course_id=c.id).count()==1
    assert f.m.AuditLog.query.filter_by(action='RT_PET_LINKED',entity_id=str(link.id)).count()==1
