"""Compatibility composition for quantity validation and case stock returns."""
from domain.inventory.return_policy import quantity
from application.services.inventory.return_service import return_to_original_lots as _return
from infrastructure.adapters.inventory.return_repository import SqlAlchemyInventoryReturnRepository


def _repository(m):
    return SqlAlchemyInventoryReturnRepository(m.db.session,m.Order,m.OrderConsumableUsage,m.InventoryLot)


def lock_order(order):
    from application.legacy_runtime import resolve_runtime
    return _repository(resolve_runtime()).lock_order(order.id)


def return_to_original_lots(order,item,qty,warehouse=None,reason='',user=None):
    from application.legacy_runtime import resolve_runtime
    m=resolve_runtime()
    return _return(_repository(m),m.default_warehouse_for_order,m.current_user,m.inventory_move,
                   order,item,qty,warehouse=warehouse,reason=reason,user=user)
