from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(rel):
    return (ROOT / rel).read_text(
        encoding="utf-8",
        errors="ignore"
    )


def test_release_identity():
    app = read("app.py")

    assert "APP_VERSION = '5.46.9'" in app
    assert "BUILD_NAME = 'fresh-schema-runtime-hardening'" in app


def test_workspace_recovery():
    base = read("templates/base.html")

    assert "url_for('advanced_search')" in base


def test_finance_admin_recovery():
    base = read("templates/base.html")

    for ep in (
        "admin_discount_policies",
        "admin_doctor_share_rules",
        "admin_referral_commissions",
    ):
        assert f"url_for('{ep}')" in base


def test_inventory_recovery():
    base = read("templates/base.html")

    for ep in (
        "admin_inventory_movements",
        "admin_inventory_batches",
        "inventory_stock_policies",
        "admin_erp",
    ):
        assert f"url_for('{ep}')" in base


def test_assignment_admin_recovery():
    base = read("templates/base.html")

    for ep in (
        "admin_assignment",
        "admin_assignment_offers",
        "admin_assignment_strategies",
    ):
        assert f"url_for('{ep}')" in base


def test_admin_configuration_recovery():
    base = read("templates/base.html")

    for ep in (
        "admin_dictionary",
        "admin_field_rules",
        "admin_procedure_quality_rules",
        "admin_registration_defaults",
    ):
        assert f"url_for('{ep}')" in base


def test_personal_tools_recovery():
    base = read("templates/base.html")

    for ep in (
        "my_quick_actions",
        "my_registration_defaults",
        "my_assignment_offers",
        "change_password",
    ):
        assert f"url_for('{ep}')" in base


def test_legacy_scheduler_not_added_to_main_nav():
    base = read("templates/base.html")

    assert "url_for('schedule_v2')" not in base
    assert "url_for('schedule_v2_book_form')" not in base


def test_reporting_demo_not_added_to_main_nav():
    base = read("templates/base.html")

    assert "url_for('admin_reporting_demo')" not in base


def test_existing_major_features_preserved():
    base = read("templates/base.html")

    for ep in (
        "schedule_calendar",
        "studio_home",
        "financial_center",
        "accounting_reports",
        "reports_portal",
        "management_dashboard",
        "pacs_tracking",
    ):
        assert f"url_for('{ep}')" in base
