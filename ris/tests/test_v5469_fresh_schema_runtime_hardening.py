from pathlib import Path

from runtime_feature_schema import REQUIRED_RUNTIME_TABLES


ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.py").read_text(encoding="utf-8")
SQL = (
    ROOT
    / "migrations"
    / "sql"
    / "v5469_runtime_feature_schema.sql"
).read_text(encoding="utf-8")


def test_v5469_release_identity():
    assert "APP_VERSION = '5.46.9'" in APP
    assert (
        "BUILD_NAME = 'fresh-schema-runtime-hardening'"
        in APP
    )


def test_all_runtime_tables_have_exact_migration_definitions():
    assert len(REQUIRED_RUNTIME_TABLES) == 11

    for table_name in REQUIRED_RUNTIME_TABLES:
        assert (
            f"CREATE TABLE public.{table_name} "
            in SQL
        )

    assert SQL.count("CREATE TABLE public.") == 11
    assert "\nCOPY " not in SQL
    assert "\nINSERT INTO " not in SQL
    assert "\\restrict" not in SQL
    assert "\\unrestrict" not in SQL


def test_bootstrap_calls_runtime_schema_inside_context():
    context_pos = APP.index("with app.app_context():")
    create_pos = APP.index("db.create_all()", context_pos)
    schema_pos = APP.index(
        "ensure_runtime_feature_schema(db, app.logger)",
        create_pos,
    )
    seed_pos = APP.index("seed_quality_defaults()", schema_pos)

    assert context_pos < create_pos < schema_pos < seed_pos


def test_data_management_get_does_not_create_backup_directory():
    assert "def admin_backup_dir(create=True):" in APP
    assert "backup_dir=admin_backup_dir(create=False)" in APP
    assert "os.getenv('BACKUP_DIR')" in APP
