
ROLE_EXPECTATIONS={
 "TECHNICIAN":{"technician.worklist","orders.view","orders.status"},
 "NURSING":{"nursing.worklist","consumables.use"},
 "SUPER_ADMIN":{"*"},
}

def test_role_expectations_defined():
    assert "TECHNICIAN" in ROLE_EXPECTATIONS
    assert "NURSING" in ROLE_EXPECTATIONS
    assert "SUPER_ADMIN" in ROLE_EXPECTATIONS
