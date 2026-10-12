"""Fresh bootstrap contract for report_edit_lease.

Fresh RadBridge schema creation uses db.create_all().  The lease table must
therefore be present in SQLAlchemy metadata, while remaining schema-compatible
with migration 20260901_001.
"""
from web.source_contract import read_source as _read_source

from sqlalchemy import UniqueConstraint


def test_report_edit_lease_registered_for_fresh_create_all(app_ctx):
    table = app_ctx.db.metadata.tables.get("report_edit_lease")

    assert table is not None

    assert list(table.columns.keys()) == [
        "id",
        "order_id",
        "report_id",
        "user_id",
        "editor_type",
        "lease_token_hash",
        "acquired_at",
        "renewed_at",
        "expires_at",
    ]

    assert table.c.id.primary_key is True

    for name in (
        "order_id",
        "report_id",
        "user_id",
        "editor_type",
        "lease_token_hash",
        "acquired_at",
        "renewed_at",
        "expires_at",
    ):
        assert table.c[name].nullable is False

    assert {
        fk.target_fullname
        for fk in table.c.order_id.foreign_keys
    } == {"order.id"}

    assert {
        fk.target_fullname
        for fk in table.c.report_id.foreign_keys
    } == {"report.id"}

    assert {
        fk.target_fullname
        for fk in table.c.user_id.foreign_keys
    } == {"user.id"}

    assert table.c.editor_type.type.length == 32
    assert table.c.lease_token_hash.type.length == 80

    assert table.c.acquired_at.type.timezone is True
    assert table.c.renewed_at.type.timezone is True
    assert table.c.expires_at.type.timezone is True

    unique_constraints = {
        constraint.name: tuple(
            column.name
            for column in constraint.columns
        )
        for constraint in table.constraints
        if isinstance(
            constraint,
            UniqueConstraint,
        )
    }

    assert unique_constraints[
        "uq_report_edit_lease_order_id"
    ] == ("order_id",)

    indexes = {
        index.name: tuple(
            column.name
            for column in index.columns
        )
        for index in table.indexes
    }

    assert indexes[
        "ix_report_edit_lease_expires_at"
    ] == ("expires_at",)


def test_fresh_bootstrap_still_uses_create_all(app_ctx):
    from pathlib import Path

    bootstrap = _read_source(Path(__file__).resolve().parents[1]
        / "bootstrap_db.py", encoding="utf-8")

    assert "db.create_all()" in bootstrap


def test_finalization_audit_contract_is_unchanged(app_ctx):
    from pathlib import Path

    source = _read_source(Path(__file__).resolve().parents[1]
        / "app.py", encoding="utf-8")

    assert "'REPORT_FINALIZED'" in source
    assert "def api_ohif_onlyoffice_finalize" in source
