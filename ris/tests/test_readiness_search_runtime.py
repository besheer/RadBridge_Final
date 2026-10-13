import uuid
from datetime import datetime
import app as m
from application.services.readiness.order_search import search_ris_orders
from infrastructure.adapters.readiness.search_repository import SqlAlchemyReadinessSearchRepository
from case_exception_resolution_service import search_ris_orders as legacy_search


def test_sql_candidates_window_ranking_and_compatibility(app_ctx):
    key = 'SYNTH-' + uuid.uuid4().hex[:8]
    session = m.db.session
    try:
        patient = m.Patient(patient_id=key, name=key + ' Patient', phone=key+'-PHONE', national_id=key+'-NID')
        session.add(patient); session.flush()
        older = m.Order(accession=key, patient_id=patient.id, modality='CT', procedure='Synthetic', scheduled=datetime(2026,1,1))
        newer = m.Order(accession=key+'-NEW', patient_id=patient.id, modality='CT', procedure='Synthetic', scheduled=datetime(2026,1,1), study_instance_uid=key+'-UID')
        session.add(older); session.flush(); session.add(newer); session.flush()
        repo = SqlAlchemyReadinessSearchRepository(session, m.Order, m.Patient)
        args = dict(repository=repo,query=key)
        assert [r.id for r in search_ris_orders(**args)] == [older.id,newer.id]
        # SQL window precedes ranking: do not silently expand the candidate set.
        assert [r.id for r in search_ris_orders(**args,limit=1)] == [newer.id]
        assert legacy_search(Order=m.Order,Patient=m.Patient,query=key) == search_ris_orders(**args)
        for query in (key+'-PHONE',key+'-NID'):
            assert {r.id for r in search_ris_orders(repository=repo,query=query)} == {older.id,newer.id}
        assert search_ris_orders(repository=repo,query=key+'-UID') == [newer]
        assert newer in search_ris_orders(repository=repo,query=str(newer.id))
        assert older.accession == key and patient.patient_id == key
    finally:
        session.rollback(); session.remove()
