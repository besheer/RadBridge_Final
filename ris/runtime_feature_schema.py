"""Create runtime feature tables omitted from the ORM metadata.

The SQL migration is an exact schema-only extraction from the production
PostgreSQL database. It contains no patient or operational records.
"""

from pathlib import Path

from sqlalchemy import inspect


REQUIRED_RUNTIME_TABLES = frozenset({
    "complaint_ticket",
    "conference_invitation",
    "conference_room",
    "public_chat_message",
    "public_chat_session",
    "public_contact_attachment",
    "public_contact_request",
    "telephony_agent_state",
    "voice_caller_control",
    "voice_intake_review",
    "voice_storage_settings",
})


class RuntimeFeatureSchemaError(RuntimeError):
    """Raised when the runtime feature schema cannot be applied safely."""


def _migration_sql():
    path = (
        Path(__file__).resolve().parent
        / "migrations"
        / "sql"
        / "v5469_runtime_feature_schema.sql"
    )

    sql = path.read_text(encoding="utf-8")

    if "\\" in sql:
        raise RuntimeFeatureSchemaError(
            "psql meta-commands are forbidden in runtime migration SQL"
        )

    return sql


def ensure_runtime_feature_schema(db, logger=None):
    """Install all missing runtime tables atomically on PostgreSQL.

    Existing complete schemas are left untouched. A partially present schema
    stops startup so it can be inspected rather than silently modified.
    Non-PostgreSQL test databases are skipped because the migration preserves
    the exact PostgreSQL production schema.
    """

    engine = db.engine
    dialect = engine.dialect.name

    if dialect != "postgresql":
        if logger:
            logger.info(
                "v5.46.9 PostgreSQL runtime schema skipped for dialect %s",
                dialect,
            )
        return sorted(REQUIRED_RUNTIME_TABLES)

    inspector = inspect(engine)
    existing = set(inspector.get_table_names(schema="public"))
    missing = REQUIRED_RUNTIME_TABLES - existing

    if not missing:
        return []

    present = REQUIRED_RUNTIME_TABLES & existing

    if present:
        raise RuntimeFeatureSchemaError(
            "Partial runtime feature schema detected. Present: "
            + ", ".join(sorted(present))
            + "; missing: "
            + ", ".join(sorted(missing))
        )

    sql = _migration_sql()
    connection = engine.raw_connection()

    try:
        cursor = connection.cursor()
        try:
            cursor.execute(sql)
        finally:
            cursor.close()

        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()

    remaining = (
        REQUIRED_RUNTIME_TABLES
        - set(
            inspect(engine).get_table_names(schema="public")
        )
    )

    if remaining:
        raise RuntimeFeatureSchemaError(
            "Runtime migration completed with missing tables: "
            + ", ".join(sorted(remaining))
        )

    if logger:
        logger.info(
            "v5.46.9 runtime feature schema installed: %s",
            ", ".join(sorted(REQUIRED_RUNTIME_TABLES)),
        )

    return sorted(REQUIRED_RUNTIME_TABLES)
