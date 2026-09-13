from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
APP=(ROOT/'app.py').read_text()
DASH=(ROOT/'templates'/'assignment_dashboard.html').read_text()
REPORT=(ROOT/'templates'/'assignment_reports.html').read_text()


def test_assignment_rows_use_only_active_assignment():
    body=APP.split('def assignment_report_rows(',1)[1].split(
        'SMART_DOCUMENT_TYPES=',1
    )[0]
    assert ".filter_by(order_id=o.id,active=True)" in body


def test_return_state_is_shared_and_resolution_aware():
    assert 'def case_return_snapshot(order_id):' in APP
    assert "['RESOLVED','READY_FOR_REREVIEW']" in APP
    assert "return case_return_snapshot(order_id)['open']" in APP


def test_dashboard_counts_only_open_returns():
    body=APP.split('def assignment_dashboard():',1)[1].split(
        "@app.get('/operations/assignment-report.csv')",1
    )[0]
    assert "sum(1 for x in all_rows if x['return_open'])" in body
    assert "request.args.get('state')" in body
    assert "request.args.get('owner')" in body


def test_return_queue_uses_canonical_open_state():
    body=APP.split('def returned_cases_queue():',1)[1].split(
        "@app.post('/returned-cases/<int:event_id>/resolve')",1
    )[0]
    assert 'state=case_return_snapshot(ev.order_id)' in body
    assert "if not state['open']" in body
    assert 'seen_orders=set()' in body


def test_dashboard_exposes_process_and_return_filters():
    for marker in (
        'name="state"',
        'name="owner"',
        'Returned / Action Required',
        'x.process_state',
        'x.process_owner',
        'x.return_reason',
        "url_for('returned_cases_queue')",
    ):
        assert marker in DASH


def test_assignment_report_uses_unified_state():
    for marker in (
        'x.process_state',
        'x.process_owner',
        'x.return_reason',
        "url_for('returned_cases_queue')",
    ):
        assert marker in REPORT

def test_open_return_has_priority_over_finalized_state():
    body=APP.split('def assignment_report_rows(',1)[1].split(
        'SMART_DOCUMENT_TYPES=',1
    )[0]
    assert body.index("if return_state['open']") < body.index(
        "elif rp and str(rp.status or '').upper()=='FINAL'"
    )
