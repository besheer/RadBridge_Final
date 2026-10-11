"""Order usage/lot queries and return row construction."""
from sqlalchemy import case


class SqlAlchemyInventoryReturnRepository:
    def __init__(self, session, Order, Usage, Lot):
        self.session,self.Order,self.Usage,self.Lot=session,Order,Usage,Lot

    def lock_order(self, order_id):
        if not self.session.query(self.Order).filter_by(id=order_id).with_for_update().first():
            raise ValueError('Order not found.')

    def usage_rows(self, order_id, warehouse_id, item_id):
        return self.session.query(self.Usage).filter_by(order_id=order_id,warehouse_id=warehouse_id,item_id=item_id).order_by(self.Usage.id).all()

    def locked_lots(self, ids, warehouse_id, item_id):
        L=self.Lot
        return self.session.query(L).filter(L.id.in_(ids),L.warehouse_id==warehouse_id,L.item_id==item_id).order_by(case((L.expiry_date.is_(None),1),else_=0),L.expiry_date,L.id).populate_existing().with_for_update().all()

    def create_usage(self, **values): return self.Usage(**values)
    def add(self, usage): self.session.add(usage)
