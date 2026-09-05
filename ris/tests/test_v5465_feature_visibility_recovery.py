from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return (ROOT / path).read_text(
        encoding="utf-8",
        errors="ignore"
    )


def test_release_identity():
    app = read("app.py")
    assert "APP_VERSION = '5.46.9'" in app
    assert "BUILD_NAME = 'fresh-schema-runtime-hardening'" in app


def test_studio_backend_exists():
    app = read("app.py")

    assert "@app.route('/studio')" in app
    assert "def studio_home" in app

    assert (
        "@app.route('/studio/templates/<template_type>'"
        in app
    )

    assert "def studio_templates" in app
    assert "def studio_shortcuts" in app


def test_studio_templates_exist():
    for f in (
        "studio_home.html",
        "studio_templates.html",
        "studio_template_preview.html",
        "studio_shortcuts.html",
    ):
        assert (ROOT / "templates" / f).exists()


def test_studio_visible_in_navigator():
    base = read("templates/base.html")

    assert "url_for('studio_home')" in base

    assert (
        "url_for('studio_templates',template_type='FORM')"
        in base
    )

    assert (
        "url_for('studio_templates',template_type='RECEIPT')"
        in base
    )

    assert (
        "url_for('studio_templates',template_type='REPORT')"
        in base
    )

    assert "url_for('studio_shortcuts')" in base


def test_studio_nav_is_permission_gated():
    base = read("templates/base.html")

    marker = '{% if has_perm("users.view") %}'
    pos = base.find("url_for('studio_home')")

    assert pos > 0
    assert marker in base[max(0, pos-500):pos]


def test_finance_links_preserved():
    base = read("templates/base.html")

    for endpoint in (
        "financial_center",
        "receivables",
        "financial_entries",
        "accounting_reports",
        "doctor_earnings_report",
    ):
        assert f"url_for('{endpoint}')" in base


def test_reporting_links_preserved():
    base = read("templates/base.html")

    assert "url_for('doctor_workspace')" in base
    assert "url_for('reports_portal')" in base


def test_management_links_preserved():
    base = read("templates/base.html")

    for endpoint in (
        "management_dashboard",
        "analytics",
        "executive_analytics",
        "referral_analytics",
        "assignment_reports",
    ):
        assert f"url_for('{endpoint}')" in base
