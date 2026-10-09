#!/usr/bin/env bash
set -u
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

FAIL=0
echo "===== RIS v5.15 REGRESSION ====="

echo "===== 1. PYTHON ====="
python3 -m py_compile app.py workflow_engine.py || FAIL=1

echo "===== 2. JINJA ====="
python3 - <<'PY' || exit 1
from jinja2 import Environment,FileSystemLoader
from pathlib import Path
env=Environment(loader=FileSystemLoader("templates"))
for f in Path("templates").glob("*.html"):
    env.parse(f.read_text(encoding="utf-8"))
print("JINJA: PASS")
PY

echo "===== 3. PYTEST ====="
if command -v pytest >/dev/null 2>&1; then
  pytest -q tests || FAIL=1
else
  echo "pytest not installed - SKIP"
fi

echo "===== 4. LIVE HEALTH ====="
if [ -n "${TEST_BASE_URL:-}" ]; then
  curl -fsS "${TEST_BASE_URL%/}/api/reporting/health" || FAIL=1
  echo
else
  echo "TEST_BASE_URL not set - SKIP"
fi

echo "===== 5. DICOM TCP ====="
if [ -n "${DICOM_HOST:-}" ]; then
  python3 scripts/dicom-smoke.py || FAIL=1
else
  echo "DICOM_HOST not set - SKIP"
fi

echo "===== RESULT ====="
if [ "$FAIL" -eq 0 ]; then
  echo "RIS REGRESSION: PASS"
else
  echo "RIS REGRESSION: FAIL"
fi
exit "$FAIL"
