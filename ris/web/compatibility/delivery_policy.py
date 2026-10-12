"""Legacy delivery signatures with runtime composition at the web boundary."""
from application.legacy_runtime import resolve_runtime
from application.services.finance.delivery_readiness import DeliveryReadiness
from domain.finance.delivery_evidence import METHODS
from infrastructure.adapters.finance.delivery_repository import SqlAlchemyDeliveryRepository
from infrastructure.adapters.reporting.delivery_files import ReportDeliveryFiles
from infrastructure.adapters.imaging.delivery_pacs import OrthancDeliveryEvidence


def _service():
    m=resolve_runtime()
    return DeliveryReadiness(SqlAlchemyDeliveryRepository(m.db.session,m.PacsStudyMatch),
        report_files=ReportDeliveryFiles(m.REPORT_DIR,m.validate_report_patient_file),
        pacs=OrthancDeliveryEvidence(m.PACS_ORTHANC_URL,m.requests.get,m._orthanc_auth),
        demographic_gate=m.pacs_demographic_gate)


def report_readiness(order):return _service().report_readiness(order)
def images_readiness(order,live=False):return _service().images_readiness(order,live=live)
def delivery_readiness(order,item,live=False):return _service().delivery_readiness(order,item,live=live)
def snapshot(order):return _service().snapshot(order)
