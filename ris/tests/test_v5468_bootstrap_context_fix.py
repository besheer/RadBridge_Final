from web.source_contract import read_source as _read_source
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def source():
    return _read_source(ROOT / "app.py", encoding="utf-8", errors="strict")


def test_v5468_release_identity():
    text = source()
    assert "APP_VERSION = '5.46.9'" in text
    assert "BUILD_NAME = 'fresh-schema-runtime-hardening'" in text


def test_optional_bootstrap_runs_inside_app_context():
    text = source()

    start = text.index(
        "if os.getenv("
        "'RADBRIDGE_BOOTSTRAP_ON_IMPORT','0'"
        ") == '1':"
    )
    end = text.index(
        "# ============================================================",
        start,
    )
    block = text[start:end]

    assert (
        "\n    with app.app_context():\n"
        in block
    )
    assert (
        "\n        try:\n"
        "            ensure_default_procedure_branch_mappings()"
        in block
    )
    assert (
        "\n            db.session.rollback()"
        in block
    )
    assert (
        "\n    try:\n"
        "        ensure_default_procedure_branch_mappings()"
        not in block
    )


def test_no_rollback_outside_bootstrap_context():
    text = source()

    start = text.index(
        "if os.getenv("
        "'RADBRIDGE_BOOTSTRAP_ON_IMPORT','0'"
        ") == '1':"
    )
    end = text.index(
        "# ============================================================",
        start,
    )

    block = text[start:end]

    for line in block.splitlines():
        if "db.session.rollback()" in line:
            assert line.startswith("            ")
