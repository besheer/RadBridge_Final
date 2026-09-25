"""Unit contracts for lease preflight using a private FK-enforced SQLite DB.

The application's real scanner/preflight functions are called unchanged.
The database adapter is replaced only for this test, not the shared app_ctx DB.
These tests do not claim PostgreSQL or destructive end-to-end acceptance.
"""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session


@pytest.fixture
def lease_env(app_ctx, monkeypatch):
    m = app_ctx
    engine = create_engine("sqlite+pysqlite:///:memory:")
    with engine.begin() as connection:
        connection.exec_driver_sql("PRAGMA foreign_keys=ON")
        connection.exec_driver_sql('CREATE TABLE "order" (id INTEGER PRIMARY KEY)')
        connection.exec_driver_sql('CREATE TABLE "user" (id INTEGER PRIMARY KEY)')
        connection.exec_driver_sql(
            'CREATE TABLE report (id INTEGER PRIMARY KEY, '
            'order_id INTEGER NOT NULL REFERENCES "order"(id))'
        )
        connection.exec_driver_sql('''
            CREATE TABLE report_edit_lease (
                id INTEGER PRIMARY KEY,
                order_id INTEGER NOT NULL UNIQUE REFERENCES "order"(id),
                report_id INTEGER NOT NULL REFERENCES report(id),
                user_id INTEGER NOT NULL REFERENCES "user"(id),
                editor_type VARCHAR(32) NOT NULL,
                lease_token_hash VARCHAR(80) NOT NULL,
                acquired_at DATETIME NOT NULL,
                renewed_at DATETIME NOT NULL,
                expires_at DATETIME NOT NULL
            )
        ''')
        connection.exec_driver_sql('INSERT INTO "order" (id) VALUES (44)')
        connection.exec_driver_sql('INSERT INTO "user" (id) VALUES (1)')
        connection.exec_driver_sql('INSERT INTO report (id, order_id) VALUES (23, 44)')
    session = Session(engine)
    original_db = m.db
    adapter = SimpleNamespace(engine=engine, session=session)
    order = SimpleNamespace(id=44, status="CANCELLED", accession="LEASE-UNIT-44")
    env = SimpleNamespace(m=m, db=adapter, order=order)
    with monkeypatch.context() as patch:
        patch.setattr(m, "db", adapter)
        try:
            assert session.execute(text("PRAGMA foreign_keys")).scalar_one() == 1
            fks = inspect(session.connection()).get_foreign_keys("report_edit_lease")
            assert any(
                fk["constrained_columns"] == ["order_id"]
                and fk["referred_table"] == "order"
                and fk["referred_columns"] == ["id"]
                for fk in fks
            )
            yield env
        finally:
            session.rollback()
            session.close()
            engine.dispose()
    assert m.db is original_db


def _insert(env, expires):
    now = datetime.now(timezone.utc).replace(tzinfo=None).isoformat(" ")
    if isinstance(expires, datetime):
        expires = expires.isoformat(" ")
    env.db.session.execute(text('''
        INSERT INTO report_edit_lease (
            id,order_id,report_id,user_id,editor_type,lease_token_hash,
            acquired_at,renewed_at,expires_at
        ) VALUES (1,44,23,1,'ONLYOFFICE','isolated-unit-test',:now,:now,:expires)
    '''), {"now": now, "expires": expires})
    env.db.session.commit()


def _rows(env):
    return env.m._ris_case_only_dependency_rows(env.order)


def _lease_row(rows):
    matches = [r for r in rows if (r.get("table"), r.get("column"))
               == ("report_edit_lease", "order_id")]
    assert len(matches) == 1
    return matches[0]


def _preview(env, rows=None):
    return env.m.granular_delete_ris_case_only_execution_preview_snapshot(
        env.order, _rows(env) if rows is None else rows,
        [{"id": 23, "status": "DRAFT"}],
    )


def test_ris_case_preview_expired_report_lease_is_cleanup_owned(lease_env):
    env = lease_env
    _insert(env, datetime.now(timezone.utc) - timedelta(minutes=10))
    rows = _rows(env)
    assert _lease_row(rows)["count"] == 1  # Physical count must not be hidden.
    before = env.db.session.execute(text("SELECT * FROM report_edit_lease")).all()
    preview = _preview(env, rows)
    assert preview["lease"] == {"verified": True, "active_count": 0, "expired_count": 1}
    assert preview["blockers"] == ["DELETE_REPORTS_FIRST: report.order_id"]
    assert preview["unknown_active_dependencies"] == []
    assert "EXPIRED_REPORT_EDIT_LEASE_PRESENT" in preview["warnings"]
    assert not any(r["table"] == "report_edit_lease" for r in preview["rows"])
    assert env.db.session.execute(text("SELECT * FROM report_edit_lease")).all() == before
    assert _lease_row(_rows(env))["count"] == 1


def test_ris_case_preview_active_report_lease_remains_fail_closed(lease_env):
    env = lease_env
    _insert(env, datetime.now(timezone.utc) + timedelta(minutes=10))
    preview = _preview(env)
    assert _lease_row(_rows(env))["count"] == 1
    assert preview["can_prepare_execution"] is False
    assert "ACTIVE_REPORT_EDIT_LEASE" in preview["blockers"]
    assert "report_edit_lease.order_id" not in preview["unknown_active_dependencies"]
    assert preview["lease"] == {"verified": True, "active_count": 1, "expired_count": 0}


@pytest.mark.parametrize("offset_hours,delta_minutes,active", [(3,-10,False),(-5,10,True)])
def test_offset_expiries_use_existing_lease_normalization(lease_env, offset_hours, delta_minutes, active):
    env = lease_env
    expires = (datetime.now(timezone.utc) + timedelta(minutes=delta_minutes)).astimezone(
        timezone(timedelta(hours=offset_hours))
    )
    _insert(env, expires)
    preview = _preview(env)
    assert preview["lease"]["active_count"] == int(active)
    assert preview["lease"]["expired_count"] == int(not active)
    assert ("ACTIVE_REPORT_EDIT_LEASE" in preview["blockers"]) is active
    assert _lease_row(_rows(env))["count"] == 1


def test_malformed_expiry_remains_blocking(lease_env):
    env = lease_env
    _insert(env, "invalid-expiry")
    preview = _preview(env)
    assert preview["can_prepare_execution"] is False
    assert "ACTIVE_REPORT_EDIT_LEASE" in preview["blockers"]
    assert _lease_row(_rows(env))["count"] == 1


def test_lease_query_error_remains_blocking(lease_env, monkeypatch):
    env = lease_env
    _insert(env, datetime.now(timezone.utc) - timedelta(minutes=10))
    rows = _rows(env)
    execute = env.db.session.execute
    def fail_lease_read(statement, *args, **kwargs):
        if "SELECT expires_at FROM report_edit_lease" in str(statement):
            raise RuntimeError("unit-test lease read failure")
        return execute(statement, *args, **kwargs)
    monkeypatch.setattr(env.db.session, "execute", fail_lease_read)
    preview = _preview(env, rows)
    assert preview["lease"]["verified"] is False
    assert "REPORT_LEASE_STATE_UNVERIFIED" in preview["blockers"]
    assert preview["can_prepare_execution"] is False


def test_raw_postcheck_does_not_hide_expired_rows(lease_env):
    env = lease_env
    _insert(env, datetime.now(timezone.utc) - timedelta(days=1))
    preview = _preview(env)
    assert preview["lease"]["expired_count"] == 1
    remaining = [r for r in _rows(env) if r.get("count") is None or int(r["count"]) > 0]
    assert _lease_row(remaining)["count"] == 1


def test_unknown_nonlease_dependency_still_blocks(lease_env):
    env = lease_env
    _insert(env, datetime.now(timezone.utc) - timedelta(days=1))
    env.db.session.execute(text('CREATE TABLE unknown_case_child (id INTEGER PRIMARY KEY, '
                                'order_id INTEGER NOT NULL REFERENCES "order"(id))'))
    env.db.session.execute(text('INSERT INTO unknown_case_child VALUES (1,44)'))
    env.db.session.commit()
    preview = _preview(env)
    assert "UNKNOWN_DEPENDENCY: unknown_case_child.order_id" in preview["blockers"]
    assert preview["can_prepare_execution"] is False


def test_unverified_lease_dependency_count_is_not_ignored(lease_env):
    env = lease_env
    rows = _rows(env)
    _lease_row(rows)["count"] = None
    preview = _preview(env, rows)
    assert "COMPOSITE_FK_REVIEW: report_edit_lease.order_id" in preview["blockers"]
    assert preview["can_prepare_execution"] is False


def test_disappeared_lease_table_requires_review(lease_env):
    env = lease_env
    _insert(env, datetime.now(timezone.utc) - timedelta(minutes=10))
    rows = _rows(env)
    env.db.session.execute(text("DROP TABLE report_edit_lease"))
    env.db.session.commit()
    preview = _preview(env, rows)
    assert "REPORT_LEASE_STATE_UNVERIFIED" in preview["blockers"]
    assert preview["can_prepare_execution"] is False


def test_no_lease_still_preserves_report_delete_first_gate(lease_env):
    env = lease_env
    assert _lease_row(_rows(env))["count"] == 0
    preview = _preview(env)
    assert preview["lease"] == {"verified": True, "active_count": 0, "expired_count": 0}
    assert preview["blockers"] == ["DELETE_REPORTS_FIRST: report.order_id"]


def test_create_if_not_exists_does_not_upgrade_a_no_fk_test_table():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    try:
        with engine.begin() as connection:
            connection.exec_driver_sql('CREATE TABLE "order" (id INTEGER PRIMARY KEY)')
            connection.exec_driver_sql('CREATE TABLE report_edit_lease '
                                       '(id INTEGER PRIMARY KEY, order_id INTEGER NOT NULL UNIQUE)')
            connection.exec_driver_sql('CREATE TABLE IF NOT EXISTS report_edit_lease '
                                       '(id INTEGER PRIMARY KEY, order_id INTEGER NOT NULL '
                                       'REFERENCES "order"(id))')
            assert inspect(connection).get_foreign_keys("report_edit_lease") == []
    finally:
        engine.dispose()
