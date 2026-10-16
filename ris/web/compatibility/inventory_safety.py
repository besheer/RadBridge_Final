"""Compatibility composition for quantity validation and case stock returns."""
from domain.inventory.return_policy import quantity
from application.services.inventory.return_service import return_to_original_lots as _return
from infrastructure.adapters.inventory.return_repository import SqlAlchemyInventoryReturnRepository


def _repository(m):
    return SqlAlchemyInventoryReturnRepository(m.db.session,m.Order,m.OrderConsumableUsage,m.InventoryLot)


def lock_order(order, *, runtime):
    """Lock the owning order using runtime dependencies from composition."""
    return _repository(runtime).lock_order(order.id)


def return_to_original_lots(order,item,qty,warehouse=None,reason='',user=None,*,runtime):
    m=runtime
    return _return(_repository(m),m.default_warehouse_for_order,m.current_user,m.inventory_move,
                   order,item,qty,warehouse=warehouse,reason=reason,user=user)
