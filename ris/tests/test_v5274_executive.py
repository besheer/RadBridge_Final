
def test_executive_analytics_route_permission():
 import app as m
 assert 'analytics.executive.view' in m.ALL_PERMISSIONS
 assert hasattr(m,'executive_analytics_payload')
 rules={r.rule for r in m.app.url_map.iter_rules()}
 assert '/analytics/executive' in rules

def test_stock_ledger_fix_preserved():
 import app as m,inspect
 src=inspect.getsource(m.inventory_ledger)
 assert 'WarehouseStockMovement.id.desc()' in src
 assert 'order_by(StockMovement.id.desc())' not in src
