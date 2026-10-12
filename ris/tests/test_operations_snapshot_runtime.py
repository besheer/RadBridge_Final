import uuid
from datetime import datetime,timedelta,timezone
import app as m
from case_operations_dashboard_service import build_case_operations_snapshot


def test_persisted_editor_lease_has_datetime_and_receiving_never_projects_ready(app_ctx):
    session=m.db.session; key='SYNTH-'+uuid.uuid4().hex[:8];now=datetime(2026,1,1,tzinfo=timezone.utc)
    try:
        patient=m.Patient(patient_id=key,name='Synthetic dashboard patient')
        user=m.User(username=key,full_name='Synthetic dashboard doctor',password_hash='DISABLED-SYNTHETIC',
                    role=m.Role.query.filter_by(code='RADIOLOGIST').one())
        session.add_all([patient,user]);session.flush()
        order=m.Order(accession=key,patient_id=patient.id,modality='CT',procedure='Synthetic',
                      scheduled=now,status='REPORTING',pacs_status='RECEIVING')
        session.add(order);session.flush()
        report=m.Report(order_id=order.id,status='DRAFT')
        session.add(report);session.flush()
        session.add(m.ReportEditLease(order_id=order.id,report_id=report.id,user_id=user.id,
            editor_type='ONLYOFFICE',lease_token_hash='SYNTHETIC',acquired_at=now,renewed_at=now,expires_at=now+timedelta(seconds=120)))
        session.add(m.CaseReadiness(order_id=order.id,status='READY',image_count=10))
        session.flush()
        args=dict(db=m.db,Order=m.Order,Report=m.Report,CaseAssignment=m.CaseAssignment,
                  AssignmentOffer=m.AssignmentOffer,AssignmentStrategy=m.AssignmentStrategy,
                  AssignmentEscalationEvent=m.AssignmentEscalationEvent,CaseReadiness=m.CaseReadiness,
                  PacsStudyInbox=m.PacsStudyInbox,PacsExamLink=m.PacsExamLink,PacsResolutionEvent=m.PacsResolutionEvent)
        result=build_case_operations_snapshot(**args,now=now.replace(tzinfo=None))
        case=next(c for c in result['cases'] if c['order'].id==order.id)
        assert isinstance(case['lease']['expires_at'],datetime)
        assert case['readiness'].status=='BLOCKED'
        assert 'ACTIVE_EDITOR' in case['attention_reasons']
        assert m.CaseReadiness.query.filter_by(order_id=order.id).one().status=='READY'
        assert order.accession==key and report.status=='DRAFT'
    finally:
        session.rollback();session.remove()
