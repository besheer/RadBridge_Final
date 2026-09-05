
def test_v5273_routes_and_security():
 import app as m
 rules={r.rule for r in m.app.url_map.iter_rules()}
 for r in ['/admin/data-management','/admin/data-management/export-patient',
           '/admin/data-management/anonymize-patient','/admin/data-management/delete-patient',
           '/admin/data-management/reset-module']:
  assert r in rules
 for p in ['backup.view','backup.create','data.export','data.anonymize','data.delete.patient','data.reset']:
  assert p in m.ALL_PERMISSIONS
 assert hasattr(m,'WarehouseStockMovement')
 assert hasattr(m,'StockMovement')
 assert m.WarehouseStockMovement.__tablename__=='warehouse_stock_movement'
 assert m.StockMovement.__tablename__=='stock_movement'
