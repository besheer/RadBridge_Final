"""Check actual import boundaries, not directory names alone."""
import ast
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1] / "ris"


def violations():
    issues = []
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
    return issues


if __name__ == "__main__":
    errors = violations()
    print("\n".join(errors) if errors else "Domain and persistence import boundaries pass")
    raise SystemExit(bool(errors))
