
ROLE_MATRIX={
    "RECEPTION":{
        "allow":["dashboard.view","patients.view","orders.view"],
        "deny":["users.manage","financial.admin"]
    },
    "TECHNICIAN":{
        "allow":["technician.worklist","orders.view","orders.status"],
        "deny":["users.manage","reports.finalize"]
    },
    "NURSING":{
        "allow":["nursing.worklist","consumables.use"],
        "deny":["users.manage","reports.finalize"]
    },
    "RADIOLOGIST":{
        "allow":["reports.view","reports.edit"],
        "deny":["users.manage"]
    },
    "SUPER_ADMIN":{"allow":["*"],"deny":[]},
}

def test_required_roles_documented():
    for role in ["RECEPTION","TECHNICIAN","NURSING","RADIOLOGIST","SUPER_ADMIN"]:
        assert role in ROLE_MATRIX

def test_technician_cannot_admin():
    assert "users.manage" in ROLE_MATRIX["TECHNICIAN"]["deny"]

def test_nursing_cannot_finalize_report():
    assert "reports.finalize" in ROLE_MATRIX["NURSING"]["deny"]
