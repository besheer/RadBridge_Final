"""Legacy imports must reference the actual owned module, including patch state."""
import ast
import importlib
import json
from pathlib import Path

from infrastructure.resources import RIS_ROOT


def test_facades_preserve_module_and_exception_identity(app_ctx):
    entries = json.loads((RIS_ROOT / 'application/module_manifest.json').read_text())
    assert len(entries) == 76
    for entry in entries:
        # Workers are explicit CLI entry points; importing them can start work.
        if entry['canonical'].startswith('workers.'):
            continue
        legacy = importlib.import_module(entry['legacy'])
        owned = importlib.import_module(entry['canonical'])
        assert legacy is owned, entry['legacy']
        assert Path(owned.__file__).resolve() == (RIS_ROOT / (entry['canonical'].replace('.', '/') + '.py')).resolve()


def test_services_and_adapters_use_only_the_declared_legacy_runtime_seam():
    for package in ('application/services', 'infrastructure/adapters', 'web/extensions'):
        for path in (RIS_ROOT / package).rglob('*.py'):
            tree = ast.parse(path.read_text(encoding='utf-8'))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    assert all(alias.name != 'app' for alias in node.names), path
                elif isinstance(node, ast.ImportFrom):
                    assert node.module != 'app', path


def test_resource_location_survives_adapter_and_extension_moves():
    import ui_localization
    assert ui_localization.CATALOG
    assert (RIS_ROOT / 'assets/fonts/Amiri-Regular.ttf').is_file()
    assert (RIS_ROOT / 'client_tools/RadiAntBridge').is_dir()
    assert (RIS_ROOT / 'migrations').is_dir()
