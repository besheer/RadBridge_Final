"""Check actual import boundaries, not directory names alone."""
import ast
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1] / "ris"


def violations():
    issues = []
    contracts=json.loads((ROOT / 'application/port_contracts.json').read_text(encoding='utf-8'))
    for entry in contracts['services']:
        for key in ('module','repository','composition'):
            owner=ROOT / (entry[key].replace('.','/')+'.py')
            if not owner.is_file():
                issues.append(f"port contract missing {key}: {entry[key]}")
    modules=[entry['module'] for entry in contracts['services']]+contracts.get('helpers',[])
    for path in sorted((ROOT / 'application/services').rglob('*.py')):
        tree=ast.parse(path.read_text(encoding='utf-8-sig'))
        for node in ast.walk(tree):
            imports=[alias.name for alias in node.names] if isinstance(node,ast.Import) else [node.module or ''] if isinstance(node,ast.ImportFrom) else []
            for name in imports:
                if name.split('.')[0]=='flask':
                    issues.append(f"{path.relative_to(ROOT)}:{node.lineno}: application service imports HTTP framework {name}")
    for module in modules:
        path=ROOT / (module.replace('.','/')+'.py')
        if not path.is_file():
            issues.append(f"explicit boundary missing module: {module}")
        if not path.is_file():continue
        tree=ast.parse(path.read_text(encoding='utf-8-sig'))
        for node in ast.walk(tree):
            imports=[a.name for a in node.names] if isinstance(node,ast.Import) else [node.module or ''] if isinstance(node,ast.ImportFrom) else []
            for name in imports:
                if name.split('.')[0] in {'app','web','infrastructure','flask','sqlalchemy','requests'} or name=='application.legacy_runtime':
                    issues.append(f"{path.relative_to(ROOT)}:{node.lineno}: explicit boundary imports {name}")
    for path in sorted((ROOT / "domain").rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8-sig"))
        for node in ast.walk(tree):
            imports = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module or ""] if isinstance(node, ast.ImportFrom) else []
            for name in imports:
                head = name.split(".")[0]
                if head and head not in sys.stdlib_module_names and head != "domain":
                    issues.append(f"{path.relative_to(ROOT)}:{node.lineno}: domain imports {name}")
    for path in sorted((ROOT / "infrastructure" / "models").rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8-sig"))
        for node in ast.walk(tree):
            imports = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module or ""] if isinstance(node, ast.ImportFrom) else []
            for name in imports:
                if name.split(".")[0] in {"app", "web", "application", "requests", "flask"}:
                    issues.append(f"{path.relative_to(ROOT)}:{node.lineno}: schema imports {name}")
    for package in ("application/components", "application/services", "web/routes", "web/components", "web/extensions", "web/compatibility", "infrastructure/adapters"):
        for path in sorted((ROOT / package).rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8-sig"))
            for node in ast.walk(tree):
                imports = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module or ""] if isinstance(node, ast.ImportFrom) else []
                if "app" in imports:
                    issues.append(f"{path.relative_to(ROOT)}:{node.lineno}: component imports composition root")
    return issues


if __name__ == "__main__":
    errors = violations()
    print("\n".join(errors) if errors else "Domain, persistence and component import boundaries pass")
    raise SystemExit(bool(errors))
