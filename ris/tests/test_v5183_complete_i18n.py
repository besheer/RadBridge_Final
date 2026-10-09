
def test_v5183_dictionary():
    import app as m
    keys={x[0] for x in m.DEFAULT_UI_DICTIONARY}
    required={
      "nav.assignment","nav.calendar","patient.select","patient.worklist_name",
      "branch.select","exam.select_branch_first","priority.ROUTINE",
      "clinical.attachment_category","payment.no_payment",
      "registration.validation_notice"
    }
    assert required <= keys

def test_core_routes_preserved():
    import app as m
    rules={r.rule for r in m.app.url_map.iter_rules()}
    required={
      "/orders/new","/cashier","/payments/<int:payment_id>/refund",
      "/schedule/v2","/admin/booking-control","/admin/booking-availability",
      "/admin/dictionary","/my/profile",
      "/orders/<int:order_id>/clinical-notes",
      "/pacs/tracking","/pacs/reconciliation"
    }
    assert required <= rules
