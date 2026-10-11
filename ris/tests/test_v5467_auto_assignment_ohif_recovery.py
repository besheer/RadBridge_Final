from web.source_contract import read_source as _read_source
from pathlib import Path

import pytest

from tools.validate_ohif_runtime_dist import OhifContractError, validate_dist

ROOT = Path(__file__).resolve().parents[1]


def read(rel):
    return _read_source(ROOT / rel, encoding="utf-8", errors="ignore")


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


def _runtime_fixture(tmp_path, reporting_text):
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "assets" / "radbridge-favicon.svg").write_text("<svg/>")
    (dist / "index.html").write_text(
        '<title>RadBridge | Diagnostic Imaging</title>'
        '<link href="/assets/radbridge-favicon.svg">'
        '<script src="/app.bundle.js"></script>'
    )
    (dist / "app-config.js").write_text(
        "const names = ['RadBridge PACS', 'RadBridge Orthanc'];"
    )
    (dist / "app.bundle.js").write_text("application shell")
    (dist / "reporting.bundle.js").write_text(reporting_text)
    return dist


def test_rebranded_ohif_onlyoffice_runtime_contract(tmp_path):
    from tools.validate_ohif_runtime_dist import REPORTING_MARKERS

    dist = _runtime_fixture(tmp_path, "\n".join(REPORTING_MARKERS))
    result = validate_dist(dist)
    assert result["ok"] is True
    assert result["reporting_bundle"] == "reporting.bundle.js"
    assert result["reporting_marker_count"] == len(REPORTING_MARKERS)


def test_runtime_contract_rejects_legacy_word_only_bundle(tmp_path):
    dist = _runtime_fixture(
        tmp_path,
        "RadBridge Reporting Workspace\n"
        "/radbridge-api/api/ohif/report\n"
        "Open in Microsoft Word\nDownload Word Template\nUpload Word Draft",
    )
    with pytest.raises(OhifContractError, match="REPORTING_CONTRACT_MISSING"):
        validate_dist(dist)


def test_ris_source_owns_onlyoffice_clinical_workflow():
    app = read("app.py")
    for marker in (
        "RADBRIDGE ONLYOFFICE INTEGRATION",
        "ONLYOFFICE callback remains WORKING COPY ONLY",
        "ONLYOFFICE explicit commit layer",
        "INVALID_ONLYOFFICE_COMMIT_STATUS",
        "ONLYOFFICE_SAVE_BLOCKED",
        "REPORT_EDIT_LOCKED",
    ):
        assert marker in app
