from web.source_contract import get_source as _get_source

def test_studio_shortcut_model_routes_and_golden():
 import app as m,inspect
 assert hasattr(m,"StudioShortcut")
 assert hasattr(m,"studio_shortcuts_for")
 rules={r.rule for r in m.app.url_map.iter_rules()}
 for r in ["/studio/shortcuts","/studio/shortcuts/<int:shortcut_id>/toggle",
           "/studio/shortcuts/<int:shortcut_id>/delete","/studio/shortcuts/reorder",
           "/admin/printer-profiles","/my/registration-defaults","/orders/<int:order_id>/actions"]:
  assert r in rules
 assert hasattr(m,"next_patient_id")
 assert "CaseReadiness=CaseReadiness" in _get_source(m.advanced_search)
 assert "active=True" not in _get_source(m.device_booking_reason)

def test_shortcut_templates():
 from pathlib import Path
 root=Path(__file__).parents[1]/"templates"
 s=(root/"studio_shortcuts.html").read_text()
 for x in ["{order_id}","{patient_id}","Choose Icon","Placement","Permission"]:
  assert x in s
 assert (root/"_studio_shortcuts.html").exists()
