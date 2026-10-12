import uuid
from datetime import datetime, timezone

import app as m
from case_operations_dashboard_service import build_case_operations_snapshot


def test_snapshot_and_related_worklists_are_limited_to_allowed_branches(app_ctx):
    session=m.db.session
    suffix=uuid.uuid4().hex[:8]
    now=datetime(2026,1,1,tzinfo=timezone.utc)
    try:
        branch_a=m.Branch(code='A'+suffix[:6],name='Synthetic branch A')
        branch_b=m.Branch(code='B'+suffix[:6],name='Synthetic branch B')
        patient=m.Patient(patient_id='P'+suffix,name='Synthetic scope patient')
        session.add_all([branch_a,branch_b,patient]);session.flush()
        order_a=m.Order(accession='A'+suffix,patient_id=patient.id,modality='CT',procedure='Synthetic A',
                        scheduled=now,status='REPORTING',pacs_status='RECEIVING',branch_id=branch_a.id)
        order_b=m.Order(accession='B'+suffix,patient_id=patient.id,modality='CT',procedure='Synthetic B',
                        scheduled=now,status='REPORTING',pacs_status='RECEIVING',branch_id=branch_b.id)
        session.add_all([order_a,order_b]);session.flush()
        inbox_a=m.PacsStudyInbox(orthanc_study_id='OA'+suffix,order_id=order_a.id,state='REVIEW_REQUIRED')
        inbox_b=m.PacsStudyInbox(orthanc_study_id='OB'+suffix,order_id=order_b.id,state='REVIEW_REQUIRED')
        link_a=m.PacsExamLink(orthanc_study_id='LA'+suffix,order_id=order_a.id,reason='synthetic')
        link_b=m.PacsExamLink(orthanc_study_id='LB'+suffix,order_id=order_b.id,reason='synthetic')
        session.add_all([inbox_a,inbox_b,link_a,link_b])
        session.add_all([
            m.AssignmentStrategy(name='scope-global-'+suffix,branch_id=None,enabled=True),
            m.AssignmentStrategy(name='scope-a-'+suffix,branch_id=branch_a.id,enabled=True),
            m.AssignmentStrategy(name='scope-b-'+suffix,branch_id=branch_b.id,enabled=True),
        ])
        session.flush()

        args=dict(db=m.db,Order=m.Order,Report=m.Report,CaseAssignment=m.CaseAssignment,
                  AssignmentOffer=m.AssignmentOffer,AssignmentStrategy=m.AssignmentStrategy,
                  AssignmentEscalationEvent=m.AssignmentEscalationEvent,CaseReadiness=m.CaseReadiness,
                  PacsStudyInbox=m.PacsStudyInbox,PacsExamLink=m.PacsExamLink,
                  PacsResolutionEvent=m.PacsResolutionEvent)
        result=build_case_operations_snapshot(**args,branch_ids=[branch_a.id],now=now.replace(tzinfo=None))
        assert [row['order'].id for row in result['cases']]==[order_a.id]
        assert [row.id for row in result['pacs_review']]==[inbox_a.id]
        assert [row.id for row in result['active_exam_links']]==[link_a.id]
        assert {row.name for row in result['enabled_strategies']} >= {'scope-global-'+suffix,'scope-a-'+suffix}
        assert 'scope-b-'+suffix not in {row.name for row in result['enabled_strategies']}

        empty=build_case_operations_snapshot(**args,branch_ids=[],now=now.replace(tzinfo=None))
        assert empty['cases']==[] and empty['pacs_review']==[] and empty['active_exam_links']==[]
    finally:
        session.rollback()
        session.remove()
