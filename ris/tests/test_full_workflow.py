
import pytest
from datetime import datetime, timedelta

def _role_user(m, code):
    role=m.Role.query.filter_by(code=code).first()
    if not role:
        pytest.skip(f"Role {code} not seeded")
    user=m.User.query.join(m.Role).filter(m.Role.code==code,m.User.active.is_(True)).first()
    if user:
        return user,False
    user=m.User(
        username=f"test-{code.lower().replace('_','-')}",
        full_name=f"Test {role.name}",
        password_hash="test-session-only",
        role_id=role.id,
        active=True,
    )
    m.db.session.add(user)
    m.db.session.commit()
    return user,True

def test_01_reception_patient_order_flow(app_ctx,monkeypatch):
    m=app_ctx
    admin,created=_role_user(m,"SUPER_ADMIN")
    monkeypatch.setattr(m,"orthanc_ok",lambda:False)
    try:
        with m.app.test_client() as c:
            with c.session_transaction() as sess:
                sess["uid"]=admin.id

            # Basic registration and order pages.
            assert c.get("/patients").status_code in (200,302)
            assert c.get("/patients/new").status_code in (200,302)
            assert c.get("/orders").status_code in (200,302)
    finally:
        if created:
            m.db.session.delete(admin)
            m.db.session.commit()

def test_02_technician_forward_only_engine(app_ctx):
    from workflow_engine import can_transition
    assert can_transition("TECHNICIAN","ORDERED","IN_PROGRESS").allowed
    assert can_transition("TECHNICIAN","IN_PROGRESS","EXAM_COMPLETED").allowed
    assert not can_transition("TECHNICIAN","IN_PROGRESS","ORDERED").allowed
    assert not can_transition("TECHNICIAN","EXAM_COMPLETED","IN_PROGRESS").allowed

def test_03_nursing_defaults_models_present(app_ctx):
    m=app_ctx
    assert hasattr(m,"ProcedureConsumable")
    assert hasattr(m,"NursingConsumableEntry")
    assert hasattr(m,"OrderConsumable")

def test_04_pacs_tracking_routes_present(app_ctx):
    rules={r.rule for r in app_ctx.app.url_map.iter_rules()}
    assert "/pacs/tracking" in rules
    assert "/pacs/tracking/refresh" in rules
    assert "/pacs/reconciliation" in rules

def test_05_reporting_routes_present(app_ctx):
    rules={r.rule for r in app_ctx.app.url_map.iter_rules()}
    assert any("/reports" in r for r in rules)
    assert any("report" in r.lower() for r in rules)

def test_06_patient_portal_security_models(app_ctx):
    m=app_ctx
    assert hasattr(m,"PortalAccessToken")
    assert hasattr(m,"NotificationEvent")
    assert hasattr(m,"CompanyProfile")
    assert hasattr(m,"StickerTemplate")

def test_07_finance_routes_present(app_ctx):
    rules={r.rule for r in app_ctx.app.url_map.iter_rules()}
    assert "/accounting/financial-center" in rules
    assert "/accounting/entries" in rules

def test_08_event_outbox_present(app_ctx):
    m=app_ctx
    assert hasattr(m,"EventOutbox")
    assert callable(m.enqueue_event)

def test_09_permissions_superadmin_bypass_source(app_ctx):
    import inspect
    src=inspect.getsource(app_ctx.has_perm)
    assert "SUPER_ADMIN" in src or "'*'" in src or '"*"' in src

def test_10_duplicate_patient_safety_present(app_ctx):
    assert callable(app_ctx.find_duplicate_patients)

def test_11_sticker_routes_present(app_ctx):
    rules={r.rule for r in app_ctx.app.url_map.iter_rules()}
    assert "/orders/<int:order_id>/sticker" in rules
    assert "/admin/sticker-templates" in rules

def test_12_health_endpoint(app_ctx):
    with app_ctx.app.test_client() as c:
        r=c.get("/api/reporting/health")
        assert r.status_code==200
        data=r.get_json()
        assert data["ok"] is True
        assert data["version"] == app_ctx.APP_VERSION
