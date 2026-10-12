"""Original SQL history evidence; reads only and preserves database trim semantics."""
from sqlalchemy import func


class SqlAlchemyReturnedDocumentsRepository:
    def __init__(self, session, Note):
        self.session, self.Note = session, Note

    def has_history(self, order_id):
        note = self.Note
        return self.session.query(note).filter(
            note.order_id == order_id,
            note.note_type.in_(('HISTORY', 'GENERAL', 'CLINICAL_HISTORY', 'NURSING_HISTORY')),
            func.length(func.trim(note.text)) > 0,
        ).first() is not None
