from web.source_contract import get_source as _get_source

def test_executive_route_preserved():
 import app as m
 assert 'analytics.executive.view' in m.ALL_PERMISSIONS
 assert '/analytics/executive' in {r.rule for r in m.app.url_map.iter_rules()}

def test_stock_ledger_fix_preserved():
 import app as m,inspect
 src=_get_source(m.inventory_ledger)
 assert 'WarehouseStockMovement.id.desc()' in src
