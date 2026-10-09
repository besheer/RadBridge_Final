
def test_inventory_models_present():
    import app as m
    for name in ["InventoryBatch","StockMovement","ERPItemMapping","ERPSyncQueue"]:
        assert hasattr(m,name)

def test_default_catalog_has_unique_codes():
    import app as m
    codes=[x["code"] for x in m.DEFAULT_CONSUMABLE_CATALOG]
    assert len(codes)==len(set(codes))
    assert "CON-001" in codes
    assert "US-001" in codes

def test_inventory_routes_present():
    import app as m
    rules={r.rule for r in m.app.url_map.iter_rules()}
    for route in [
        "/admin/inventory/export/<fmt>",
        "/admin/inventory/import-template",
        "/admin/inventory/import",
        "/admin/inventory/movements",
        "/admin/inventory/batches",
        "/admin/erp"
    ]:
        assert route in rules
