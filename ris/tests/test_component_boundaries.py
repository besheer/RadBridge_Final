"""Contracts for the live compatibility seam and actual executable components."""
from web.source_contract import read_source as _read_source
import ast
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from application.dependencies import Bindings
from web.source_contract import ROOT, _handler_source, app_source


def test_bindings_keep_live_overrides_and_reject_undeclared_dependencies():
    target = SimpleNamespace(callback=lambda: "first", secret="unlisted")
    port = Bindings(target, ("callback",))
    assert port.callback() == "first"
    target.callback = lambda: "second"
    assert port.callback() == "second"
    with pytest.raises(AttributeError, match="Undeclared"):
        _ = port.secret


def test_every_original_handler_is_present_once_and_preserves_its_source():
    entries = json.loads(_read_source(ROOT / "application/component_manifest.json"))
    assert len(entries) == 949
    assert len({entry["id"] for entry in entries}) == len(entries)
    assert len({entry["symbol"] for entry in entries}) == len(entries)
    composed = ast.parse(app_source())
    functions = {node.name for node in composed.body if isinstance(node, ast.FunctionDef)}
    for entry in entries:
        source = _handler_source(entry)
        assert hashlib.sha256(source.encode()).hexdigest() == entry["original_sha256"], entry["symbol"]
        assert entry["symbol"] in functions


def test_component_files_parse_and_do_not_import_the_composition_root():
    for package in ("application/components", "web/routes"):
        for path in (ROOT / package).glob("*.py"):
            tree = ast.parse(_read_source(path, encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    assert all(alias.name != "app" for alias in node.names), path
                elif isinstance(node, ast.ImportFrom):
                    assert node.module != "app", path
