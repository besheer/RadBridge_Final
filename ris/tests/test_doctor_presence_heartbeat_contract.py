from web.source_contract import read_source as _read_source
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = _read_source(ROOT / "app.py")
TEMPLATE = _read_source(ROOT / "templates" / "doctor_workspace.html")


def heartbeat_route_source():
    return APP.split("def doctor_presence_heartbeat():", 1)[1].split(
        "@app.route('/doctor')", 1
    )[0]


def test_doctor_heartbeat_route_is_unique_and_authenticated():
    assert APP.count("def doctor_presence_heartbeat():") == 1
    prefix = APP.split("def doctor_presence_heartbeat():", 1)[0][-180:]
    assert "@app.post('/api/doctor/presence/heartbeat')" in prefix
    assert "@login_required" in prefix


def test_doctor_heartbeat_restricts_roles():
    route = heartbeat_route_source()
    assert "('RADIOLOGIST','DOCTOR')" in route
    assert "abort(403)" in route


def test_doctor_heartbeat_updates_presence_without_overwriting_busy_or_away():
    route = heartbeat_route_source()
    assert "row=doctor_availability(u)" in route
    assert "row.last_seen_at=datetime.utcnow()" in route
    assert "if row.state=='OFFLINE':" in route
    assert "row.state='AVAILABLE'" in route
    assert "db.session.commit()" in route
    assert "row.state in ('BUSY','AWAY')" not in route


def test_doctor_workspace_sends_same_origin_heartbeat_every_minute():
    assert TEMPLATE.count('id="rbDoctorPresenceHeartbeat"') == 1
    assert "url_for('doctor_presence_heartbeat')" in TEMPLATE
    assert "credentials: 'same-origin'" in TEMPLATE
    assert "window.setInterval(heartbeat, 60000)" in TEMPLATE
    assert "document.visibilityState === 'visible'" in TEMPLATE
