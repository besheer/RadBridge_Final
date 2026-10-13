from web.source_contract import read_source as _read_source
from datetime import date
from pathlib import Path
import importlib.util

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from werkzeug.datastructures import MultiDict

from patient_demographics import resolve_patient_dob


ROOT = Path(__file__).resolve().parents[1]


def test_exact_date_is_preserved():
    result = resolve_patient_dob(
        {"new_dob": "1980-05-17"},
        today=date(2026, 9, 8),
    )
    assert result.dob == "19800517"
    assert result.estimated is False


def test_future_exact_date_is_rejected():
    with pytest.raises(ValueError, match="future"):
        resolve_patient_dob(
            {"new_dob": "2026-09-09"},
            today=date(2026, 9, 8),
        )


@pytest.mark.parametrize(
    ("age", "unit", "today", "expected"),
    [
        ("50", "YEARS", date(2026, 9, 8), "19760908"),
        ("1", "YEARS", date(2024, 2, 29), "20230228"),
        ("7", "MONTHS", date(2026, 9, 30), "20260228"),
        ("10", "DAYS", date(2026, 1, 5), "20251226"),
        ("0", "DAYS", date(2026, 9, 8), "20260908"),
    ],
)
def test_age_derives_approximate_dob(age, unit, today, expected):
    result = resolve_patient_dob(
        {
            "new_age_value": age,
            "new_age_unit": unit,
            "new_dob_estimated": "1",
        },
        today=today,
    )
    assert result.dob == expected
    assert result.estimated is True
    assert result.age_value == int(age)
    assert result.age_unit == unit


def test_server_recomputes_browser_generated_estimate():
    result = resolve_patient_dob(
        {
            "new_dob": "1900-01-01",
            "new_age_value": "12",
            "new_age_unit": "YEARS",
            "new_dob_estimated": "1",
        },
        today=date(2026, 9, 8),
    )
    assert result.dob == "20140908"
    assert result.estimated is True


def test_manually_entered_exact_date_wins_over_age():
    result = resolve_patient_dob(
        {
            "new_dob": "2010-03-04",
            "new_age_value": "12",
            "new_age_unit": "YEARS",
        },
        today=date(2026, 9, 8),
    )
    assert result.dob == "20100304"
    assert result.estimated is False


@pytest.mark.parametrize(
    "values",
    [
        {"new_age_value": "2.5", "new_age_unit": "YEARS"},
        {"new_age_value": "-1", "new_age_unit": "YEARS"},
        {"new_age_value": "151", "new_age_unit": "YEARS"},
        {"new_age_value": "3", "new_age_unit": "WEEKS"},
        {"new_dob": "not-a-date"},
    ],
)
def test_invalid_age_or_date_is_rejected(values):
    with pytest.raises(ValueError):
        resolve_patient_dob(values, today=date(2026, 9, 8))


def test_blank_age_and_date_remain_optional():
    result = resolve_patient_dob({}, today=date(2026, 9, 8))
    assert result.dob == ""
    assert result.estimated is False


def test_registration_helper_persists_estimated_marker(app_ctx, monkeypatch):
    m = app_ctx
    monkeypatch.setattr(m, "audit", lambda *args, **kwargs: None)
    monkeypatch.setattr(m, "generate_patient_id", lambda patient: "AGE00001")
    patient = m._rb_registration_v2_create_patient(
        MultiDict(
            {
                "new_first_name": "Age",
                "new_middle_name": "Contract",
                "new_age_value": "6",
                "new_age_unit": "MONTHS",
                "new_dob_estimated": "1",
            }
        )
    )
    assert patient.dob_estimated is True
    assert len(patient.dob) == 8
    assert patient.patient_id == "AGE00001"
    m.db.session.rollback()


def test_active_registration_templates_offer_writable_age_and_units():
    partial = _read_source(ROOT / "templates" / "_patient_age_dob_fields.html")
    assert 'name="{{age_prefix}}age_value"' in partial
    assert "readonly" not in partial
    assert 'value="YEARS"' in partial
    assert 'value="MONTHS"' in partial
    assert 'value="DAYS"' in partial
    for relative in (
        "templates/order_form.html",
        "templates/order_form_classic.html",
        "templates/schedule_calendar.html",
        "templates/patient_form.html",
    ):
        assert "_patient_age_dob_fields.html" in _read_source(ROOT / relative)


def test_browser_sync_and_estimated_notice_are_present():
    source = _read_source(ROOT / "static" / "patient-age-dob.js")
    assert "ageToDob" in source
    assert "dobToAge" in source
    assert "estimated.checked = true" in source
    base = _read_source(ROOT / "templates" / "base.html")
    assert "patient-age-dob.js" in base


def test_patient_model_and_migration_track_estimated_dob(app_ctx):
    m = app_ctx
    assert hasattr(m.Patient, "dob_estimated")
    migration = _read_source(ROOT
        / "migrations"
        / "versions"
        / "20260908_001_patient_estimated_dob.py")
    assert 'down_revision = "20260904_001"' in migration
    assert '"dob_estimated"' in migration
    assert "server_default=sa.false()" in migration


def test_estimated_dob_migration_upgrades_and_downgrades_sqlite():
    migration_path = (
        ROOT
        / "migrations"
        / "versions"
        / "20260908_001_patient_estimated_dob.py"
    )
    spec = importlib.util.spec_from_file_location("patient_dob_migration", migration_path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)

    engine = sa.create_engine("sqlite:///:memory:")
    with engine.begin() as connection:
        connection.execute(sa.text("CREATE TABLE patient (id INTEGER PRIMARY KEY)"))
        migration.op = Operations(MigrationContext.configure(connection))
        migration.upgrade()
        columns = {item["name"]: item for item in sa.inspect(connection).get_columns("patient")}
        assert columns["dob_estimated"]["nullable"] is False
        migration.downgrade()
        columns = {item["name"] for item in sa.inspect(connection).get_columns("patient")}
        assert "dob_estimated" not in columns
