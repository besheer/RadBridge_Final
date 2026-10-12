from web.source_contract import read_source as _read_source
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(rel):
    return _read_source(ROOT / rel, encoding="utf-8", errors="ignore")


def test_v5464_identity():
    app = read("app.py")
    assert "APP_VERSION = '5.46.9'" in app
    assert "BUILD_NAME = 'fresh-schema-runtime-hardening'" in app


def test_operations_dashboard_requires_orders_view():
    app = read("app.py")
    assert """@app.get('/operations/dashboard')
@require_perm('orders.view')
def operations_dashboard():""" in app


def test_operations_journey_requires_orders_view():
    app = read("app.py")
    assert """@app.get('/operations/journey')
@require_perm('orders.view')
def operations_journey():""" in app


def test_booking_board_requires_appointments_manage():
    app = read("app.py")
    assert """@app.get('/operations/booking-board')
@require_perm('appointments.manage')
def operations_booking_board():""" in app


def test_admin_home_has_backend_gate():
    app = read("app.py")
    assert "admin_perms = (" in app
    assert "if not has_perm('*') and not any(" in app


def test_import_export_get_is_protected():
    app = read("app.py")
    assert "has_perm('import.manage')" in app
    assert "has_perm('export.view')" in app


def test_nav_operations_gates():
    base = read("templates/base.html")

    assert (
        '{% if has_perm("orders.view") %}'
        '<a class="nav-link" '
        'href="{{url_for(\'operations_dashboard\')}}"'
    ) in base

    assert (
        '{% if has_perm("orders.view") %}'
        '<a class="nav-link" '
        'href="{{url_for(\'operations_journey\')}}"'
    ) in base

    assert (
        '{% if has_perm("appointments.manage") %}'
        '<a class="nav-link" '
        'href="{{url_for(\'operations_booking_board\')}}"'
    ) in base


def test_scheduler_remains_manage_only():
    base = read("templates/base.html")

    assert (
        'has_perm("appointments.manage")'
        in base
    )

    app = read("app.py")

    assert """@app.route('/schedule/calendar')
@require_perm('appointments.manage')""" in app
