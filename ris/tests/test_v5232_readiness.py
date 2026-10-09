
def test_v5232_models_and_routes():
    import app as m
    for n in ["ProcedureQualityRule","CaseReadiness","CaseWorkflowEvent","CaseReturnReason","TATPolicy","RISNotification","NotificationEscalationRule"]:
        assert hasattr(m,n)
    rules={r.rule for r in m.app.url_map.iter_rules()}
    for r in ["/operations/case-readiness","/operations/tat","/notifications","/operations/escalations","/admin/procedure-quality-rules"]:
        assert r in rules

def test_auto_assign_has_readiness_gate():
    import app as m,inspect
    src = inspect.getsource(m.offer_next_doctor)
    assert "assignment_readiness_decision(order)" in src
    assert "decision.get('allowed')" in src

def test_previous_features_preserved():
    import app as m,inspect
    rules={r.rule for r in m.app.url_map.iter_rules()}
    assert "/reports/<int:order_id>/imaging-ai" in rules
    assert "/assignment/offers" in rules
    assert "/studio" in rules
    assert "active=True" not in inspect.getsource(m.device_booking_reason)
