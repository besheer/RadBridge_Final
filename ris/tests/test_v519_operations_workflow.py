def test_v519_models():
 import app as m
 for n in ["JourneyEvent","ChatThread","ChatThreadMember","ChatMessage"]: assert hasattr(m,n)
def test_v519_routes():
 import app as m
 rules={r.rule for r in m.app.url_map.iter_rules()}
 assert {"/operations/journey","/operations/booking-board","/operations/dashboard","/chat","/chat/direct","/chat/group","/chat/case/<int:order_id>","/chat/<int:thread_id>"} <= rules
def test_previous_routes():
 import app as m
 rules={r.rule for r in m.app.url_map.iter_rules()}
 assert {"/orders/new","/cashier","/payments/<int:payment_id>/refund","/schedule/v2","/admin/booking-control","/admin/booking-availability","/admin/dictionary","/my/profile","/my/ribbon","/admin/ribbon-designer","/orders/<int:order_id>/clinical-notes","/pacs/tracking","/pacs/reconciliation"} <= rules
