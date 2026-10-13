from web.source_contract import get_source as _get_source

def test_critical_routes_preserved():
    import app as m
    rules={r.rule for r in m.app.url_map.iter_rules()}
    required={
      "/orders/new","/cashier","/payments/<int:payment_id>/refund",
      "/schedule/v2","/admin/booking-control","/admin/booking-availability",
      "/admin/dictionary","/my/profile",
      "/orders/<int:order_id>/clinical-notes",
      "/pacs/tracking","/pacs/reconciliation",
      "/my/ribbon","/admin/ribbon-designer"
    }
    assert required <= rules

def test_language_is_unified():
    import app as m, inspect
    src=_get_source(m.set_language)
    assert "ui_language" in src
    assert "session['ui_lang']" in src

def test_ribbon_models_preserved():
    import app as m
    assert hasattr(m,"RibbonAction")
    assert hasattr(m,"UserRibbonAction")
    assert callable(m.ribbon_actions_for_user)
