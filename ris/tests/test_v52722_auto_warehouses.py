
def test_auto_warehouse_routes_and_helpers():
 import app as m
 assert hasattr(m,'ensure_main_warehouse')
 assert hasattr(m,'ensure_branch_warehouses')
 rules={r.rule for r in m.app.url_map.iter_rules()}
 assert '/inventory/warehouses/auto-create' in rules
 assert '/inventory/warehouses/create-for-branch/<int:branch_id>' in rules

def test_golden_inventory_preserved():
 import app as m,inspect
 for n in ['Warehouse','InventoryItem','InventoryLot','StockTransfer','DiscountPolicy','StudioShortcut']:
  assert hasattr(m,n)
 assert hasattr(m,'next_patient_id')
 assert 'CaseReadiness=CaseReadiness' in inspect.getsource(m.advanced_search)
 assert 'active=True' not in inspect.getsource(m.device_booking_reason)
