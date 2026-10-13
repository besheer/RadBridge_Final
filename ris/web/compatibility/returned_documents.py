"""Compose legacy runtime evidence without granting mutation or approval authority."""
from application.services.clinical.returned_documents import ReturnedDocuments
from infrastructure.adapters.clinical.returned_documents_repository import SqlAlchemyReturnedDocumentsRepository


def correction_documents_ready(m, order, state):
    return ReturnedDocuments(
        SqlAlchemyReturnedDocumentsRepository(m.db.session, m.ClinicalNote),
        quality_rule=m.quality_rule_for,
        attachment_count=m._order_attachment_count,
    ).ready(order, state)
