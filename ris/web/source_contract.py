"""Inspect composed source for legacy static contracts and permission catalogues.

This reads the executable component files. It does not keep or execute a second
copy of clinical handlers. Runtime behavior is validated by the existing suites.
"""
import ast
from functools import lru_cache
import io
import inspect
import json
from pathlib import Path
import re
import tokenize

ROOT = Path(__file__).resolve().parents[1]


@lru_cache(maxsize=None)
def _installer_sources(module):
    path = ROOT / (module.replace(".", "/") + ".py")
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    return source.splitlines(keepends=True), {node.name: node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}


def _handler_source(entry):
    lines, nodes = _installer_sources(entry["module"])
    installer = nodes[entry["installer"]]
    handler = next(node for node in installer.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == entry["symbol"])
    start = min([handler.lineno, *[d.lineno for d in handler.decorator_list]]) - 1
    code = "".join(lines[start:handler.end_lineno])
    interior = set()
    fstrings = []
    for token in tokenize.generate_tokens(io.StringIO(code).readline):
        if token.type == tokenize.STRING:
            interior.update(range(token.start[0] + 1, token.end[0] + 1))
        elif tokenize.tok_name.get(token.type) == 'FSTRING_START':
            fstrings.append(token.start[0])
        elif tokenize.tok_name.get(token.type) == 'FSTRING_END':
            interior.update(range(fstrings.pop() + 1, token.end[0] + 1))
    restored = "".join(line if i in interior or not line.strip() else line[4:] for i, line in enumerate(code.splitlines(keepends=True), 1))
    return restored.replace("_rb.namespace()", "globals()").replace("_rb.", "")


@lru_cache(maxsize=1)
def app_source():
    entries = json.loads((ROOT / "application/component_manifest.json").read_text(encoding="utf-8"))
    index = {entry["id"]: entry for entry in entries}
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    pattern = r"# RB_BIND:(\d{4})\n[^\n]*\n[^\n]*\n"
    return re.sub(pattern, lambda match: _handler_source(index[match[1]]), source)


def read_source(path, *args, **kwargs):
    path = Path(path)
    if path.resolve() == (ROOT / "app.py").resolve():
        return app_source()
    if path.resolve().parent == ROOT and path.suffix == '.py':
        manifest = ROOT / 'application/module_manifest.json'
        if manifest.exists():
            owner = next((entry['canonical'] for entry in json.loads(manifest.read_text(encoding='utf-8'))
                          if entry['legacy'] == path.stem), None)
            if owner:
                return (ROOT / (owner.replace('.', '/') + '.py')).read_text(*args, **kwargs)
    return path.read_text(*args, **kwargs)


def get_source(obj):
    """Inspect the real implementation, normalizing explicit compatibility names."""
    if inspect.ismodule(obj) and Path(obj.__file__).resolve() == (ROOT / 'app.py').resolve():
        return app_source()
    source = inspect.getsource(obj)
    module = getattr(obj, '__module__', '')
    if module.startswith(('application.components.', 'web.routes.')):
        return source.replace('_rb.namespace()', 'globals()').replace('_rb.', '')
    return source
