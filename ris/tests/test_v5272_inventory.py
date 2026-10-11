from web.source_contract import get_source as _get_source

def test_inventory_models_routes_permissions():
 import app as m,inspect
 for n in ['Warehouse','InventoryItem','InventoryLot','WarehouseStockPolicy','ProcedureConsumableDefault',
           'OrderConsumableUsage','StockMovement','StockTransfer','StockTransferLine']:
  assert hasattr(m,n)
 for p in ['inventory.view','inventory.consume','inventory.add_extra_consumable','inventory.waste',
           'inventory.return','inventory.transfer.request','inventory.transfer.approve',
           'inventory.transfer.dispatch','inventory.transfer.receive','inventory.manage','inventory.reports']:
  assert p in m.ALL_PERMISSIONS
 rules={r.rule for r in m.app.url_map.iter_rules()}
 for r in ['/inventory/warehouses','/inventory/items','/inventory/stock','/inventory/transfers',
           '/inventory/ledger','/inventory/consumption-report',
           '/inventory/procedure-defaults','/orders/<int:order_id>/consumables']:
  assert r in rules

def test_golden_finance_and_ris_preserved():
 import app as m,inspect
 for n in ['DiscountPolicy','PerformingDoctorShareRule','ReferralCommissionRule','StudioShortcut','PrinterProfile','RegistrationDefault']:
  assert hasattr(m,n)
 assert hasattr(m,'next_patient_id')
 assert 'CaseReadiness=CaseReadiness' in _get_source(m.advanced_search)
 assert 'active=True' not in _get_source(m.device_booking_reason)
