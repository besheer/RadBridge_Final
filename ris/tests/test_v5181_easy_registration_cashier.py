
def test_easy_registration_routes():
    import app as m
    rules={r.rule for r in m.app.url_map.iter_rules()}
    assert "/orders/new" in rules
    assert "/api/registration/procedures" in rules

def test_cashier_routes():
    import app as m
    rules={r.rule for r in m.app.url_map.iter_rules()}
    assert "/cashier" in rules
    assert "/payments/<int:payment_id>/refund" in rules

def test_refund_model():
    import app as m
    assert hasattr(m,"PaymentRefund")

def test_cashier_permissions_source():
    import app as m
    assert "payments.refund" in m.ROLE_PERMS["CASHIER"]
    assert "cashier.workstation" in m.ROLE_PERMS["CASHIER"]
