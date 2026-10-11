"""Clinical scope queries and predicates with explicit session/model dependencies."""
from sqlalchemy import and_, false, func, or_, select

def scope_predicate(scope, *, model, Device, Branch):
    if not scope or scope.get('invalid'):
        return false()
    clauses = []
    if scope['modalities']:
        clauses.append(func.upper(model.modality).in_(scope['modalities']))
    d = Device.__table__
    b = Branch.__table__
    if scope['device_keys']:
        pairs = [v.split('/', 1) for v in scope['device_keys'] if '/' in v]
        ids = select(d.c.id).join(b, b.c.id == d.c.branch_id).where(or_(
            *[and_(b.c.code == branch, d.c.ae_title == ae) for branch, ae in pairs]) if pairs else false())
        ids = ids.where(d.c.id.in_(scope.get('device_ids', [])))
        clauses.append(model.device_id.in_(ids))
    if scope['room_keys']:
        pairs = [v.split('/', 1) for v in scope['room_keys'] if '/' in v]
        ids = select(d.c.id).join(b, b.c.id == d.c.branch_id).where(or_(
            *[and_(b.c.code == branch, d.c.room == room) for branch, room in pairs]) if pairs else false())
        clauses.append(model.device_id.in_(ids))
    return and_(*clauses) if clauses else false()


class SqlAlchemyClinicalScopeRepository:
    def __init__(self, *, session, Order, Device, Branch, Profile, Procedure, settings_reader, predicate=None):
        self.session, self.Order, self.Device, self.Branch = session, Order, Device, Branch
        self.Profile, self.Procedure, self.settings_reader = Profile, Procedure, settings_reader
        self.predicate = predicate

    def raw_scope(self, user_id):
        profile = self.session.query(self.Profile).filter_by(user_id=user_id).first() if user_id else None
        return self.settings_reader(profile).get('clinical_scope') if profile else None

    def order_matches(self, order_id, scope):
        condition = (self.predicate(scope) if self.predicate else
                     scope_predicate(scope, model=self.Order, Device=self.Device, Branch=self.Branch))
        return self.session.query(self.Order.id).filter(self.Order.id == order_id, condition).first() is not None

    def catalog(self):
        devices = self.session.query(self.Device).order_by(self.Device.branch_id, self.Device.modality, self.Device.name).all()
        device_keys = {}
        rooms = {}
        modalities = set()
        for device in devices:
            modality = str(device.modality or '').upper()
            modalities.add(modality)
            key = '%s/%s' % (device.branch.code, device.ae_title)
            device_keys.setdefault(key, []).append(device)
            if device.room:
                rooms['%s/%s' % (device.branch.code, device.room)] = (device.branch_id, device.room)
        modalities.update(str(p.modality or '').upper() for p in self.session.query(self.Procedure).all())
        modalities.discard('')
        return modalities, device_keys, rooms
