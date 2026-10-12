"""Settlement evidence queries and persistence; never rewrites cash entries."""


class SqlAlchemySettlementRepository:
    def __init__(self, session, Order, User, Revision, Settlement, FinancialEntry, ShareRule):
        self.session, self.Order, self.User = session, Order, User
        self.Revision, self.Settlement, self.FinancialEntry, self.ShareRule = Revision, Settlement, FinancialEntry, ShareRule

    def get_order(self, order_id): return self.session.get(self.Order, order_id)
    def get_doctor(self, doctor_id): return self.session.get(self.User, doctor_id)
    def latest(self, order_id):
        return self.session.query(self.Settlement).filter_by(order_id=order_id).order_by(self.Settlement.revision_no.desc()).first()
    def earlier_unsettled(self, order_id, revision_no, after, owner):
        R = self.Revision
        return self.session.query(R).filter_by(order_id=order_id,kind='REPLACEMENT',status='FINAL').filter(R.revision_no<revision_no,R.revision_no>after,R.doctor_id!=owner).first()
    def payouts(self, owner, branch_id, accession):
        return self.session.query(self.FinancialEntry).filter_by(entry_type='DOCTOR_FEE',status='POSTED',user_id=owner,branch_id=branch_id,reference_no=accession).order_by(self.FinancialEntry.id).all()
    def share_rules(self, doctor_id):
        return self.session.query(self.ShareRule).filter_by(doctor_user_id=doctor_id,active=True).all()
    def lock_order(self, order_id):
        return self.session.query(self.Order).filter_by(id=order_id).with_for_update().populate_existing().first()
    def lock_revision(self, revision_id):
        return self.session.query(self.Revision).filter_by(id=revision_id).with_for_update().populate_existing().first()
    def by_revision(self, revision_id):
        return self.session.query(self.Settlement).filter_by(revision_id=revision_id).first()
    def create(self, **values): return self.Settlement(**values)
    def add(self, row): self.session.add(row)
    def flush(self): self.session.flush()
