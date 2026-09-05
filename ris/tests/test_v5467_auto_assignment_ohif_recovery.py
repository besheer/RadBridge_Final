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
    assert (
        "BUILD_NAME = 'fresh-schema-runtime-hardening'"
        in app
    )


def test_strategy_simulator_visible():
    base = read("templates/base.html")

    assert (
        "url_for('admin_assignment_strategy_simulate_ui')"
        in base
    )


def test_strategy_simulator_permission_gate():
    base = read("templates/base.html")

    pos = base.find(
        "url_for('admin_assignment_strategy_simulate_ui')"
    )

    assert pos > 0

    section = base[max(0, pos - 400):pos]

    assert 'has_perm("assignment.manage")' in section


def test_ohif_recovered_dist_exists():
    dist = ROOT / "ohif-recovered" / "dist"

    assert dist.exists()
    assert (dist / "index.html").exists()


def test_ohif_recovered_contains_reporting_bundle():
    dist = ROOT / "ohif-recovered" / "dist"

    found = False

    for p in dist.glob("*.js"):
        text = p.read_text(
            encoding="utf-8",
            errors="ignore"
        )

        if (
            "RadBridge Reporting" in text
            and "/radbridge-api/api/ohif/report" in text
        ):
            found = True
            break

    assert found


def test_ohif_recovered_contains_word_workflow():
    dist = ROOT / "ohif-recovered" / "dist"

    all_text = ""

    for p in dist.glob("*.js"):
        all_text += p.read_text(
            encoding="utf-8",
            errors="ignore"
        )

    assert "Open in Microsoft Word" in all_text
    assert "Download Word Template" in all_text
    assert "Upload Word Draft" in all_text
