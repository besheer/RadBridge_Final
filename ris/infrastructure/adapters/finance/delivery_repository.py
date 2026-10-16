"""Read-only current PACS match lookup; delivery writes belong to the caller."""


class SqlAlchemyDeliveryRepository:
    def __init__(self, session, Match):self.session,self.Match=session,Match

    def current_match(self, order_id, study_id):
        return self.session.query(self.Match).filter_by(order_id=order_id,
            orthanc_study_id=study_id,is_current=True).first()
