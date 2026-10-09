
def test_smart_scheduling_routes():
    import app as m
    rules={r.rule for r in m.app.url_map.iter_rules()}
    assert "/schedule/calendar" in rules
    assert "/schedule/book" in rules
    assert "/appointments/<int:appointment_id>/reschedule" in rules
    assert "/schedule/maintenance" in rules

def test_status_palette():
    import app as m
    for x in ["WAITING","BOOKED","CONFIRMED","ARRIVED","IN_PROGRESS","FINAL","CANCELLED","NO_SHOW"]:
        assert x in m.APPOINTMENT_STATUS_COLORS

def test_mwl_uses_tags_envelope():
    import app as m, inspect
    src=inspect.getsource(m.send_mwl)
    assert "'Tags':tags" in src
    assert "ScheduledProcedureStepSequence" in src

def test_overlap_helper_present():
    import app as m
    assert callable(m.appointment_overlap)
