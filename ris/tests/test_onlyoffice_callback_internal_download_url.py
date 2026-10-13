from web.source_contract import read_source as _read_source
import importlib.util
from pathlib import Path


APP_PATH = Path(__file__).resolve().parents[1] / "app.py"


def _source():
    return _read_source(APP_PATH, encoding="utf-8")


def test_onlyoffice_callback_never_fetches_callback_supplied_host():
    src = _source()

    assert "RB_ONLYOFFICE_TRUSTED_INTERNAL_DOWNLOAD_URL_V1" in src

    callback_start = src.index(
        "def api_ohif_onlyoffice_callback(order_id):"
    )

    callback = src[callback_start:]

    assert "internal_edited_url" in callback
    assert "ONLYOFFICE_INTERNAL_URL" in callback
    assert "urlsplit(edited_url)" in callback
    assert "edited_path.startswith('/cache/files/')" in callback

    assert """requests.get(
            edited_url,
            timeout=60
        )""" not in callback


def test_onlyoffice_callback_rejects_non_cache_download_paths():
    src = _source()

    callback_start = src.index(
        "def api_ohif_onlyoffice_callback(order_id):"
    )

    callback = src[callback_start:]

    assert "untrusted document download path" in callback
    assert "'..' in edited_path.split('/')" in callback
    assert "return jsonify({'error': 1}), 400" in callback


def test_onlyoffice_normal_close_statuses_remain_noop():
    src = _source()

    callback_start = src.index(
        "def api_ohif_onlyoffice_callback(order_id):"
    )

    callback = src[callback_start:]

    assert "if status in (1, 4):" in callback
    assert "# 2 = ready for save" in callback
    assert "# 6 = forcesave" in callback
