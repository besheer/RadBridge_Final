#!/usr/bin/env bash
set -u
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

FAIL=0

echo "====================================="
echo " RIS v5.15.1 FULL WORKFLOW QA"
echo "====================================="

echo
echo "===== 1. SOURCE / TEMPLATE ====="
python3 -m py_compile app.py workflow_engine.py || FAIL=1

python3 - <<'PY' || FAIL=1
from pathlib import Path
from jinja2 import Environment,FileSystemLoader
env=Environment(loader=FileSystemLoader("templates"))
for f in Path("templates").glob("*.html"):
    env.parse(f.read_text(encoding="utf-8"))
print("JINJA: PASS")
PY

echo
echo "===== 2. PYTEST ====="
if command -v pytest >/dev/null 2>&1; then
  pytest -q tests || FAIL=1
else
  echo "pytest not installed on host - trying staging container"
  if docker compose -f docker-compose.staging.yml ps --status running 2>/dev/null | grep -q ris-web-test; then
    docker compose -f docker-compose.staging.yml exec -T ris-web-test python -m pytest -q tests || FAIL=1
  else
    echo "No staging container available - PYTEST SKIPPED"
    FAIL=1
  fi
fi

echo
echo "===== 3. LIVE WORKFLOW SMOKE ====="
if [ -n "${TEST_BASE_URL:-}" ]; then
  python3 scripts/full-workflow-smoke.py || FAIL=1
else
  echo "TEST_BASE_URL not set - SKIP"
fi

echo
echo "===== 4. DICOM TCP ====="
if [ -n "${DICOM_HOST:-}" ]; then
  python3 scripts/dicom-smoke.py || FAIL=1
else
  echo "DICOM_HOST not set - SKIP"
fi

echo
echo "===== 5. STAGING LOG ERRORS ====="
if docker compose -f docker-compose.staging.yml ps --status running 2>/dev/null | grep -q ris-web-test; then
  ERRORS="$(docker compose -f docker-compose.staging.yml logs --since 5m ris-web-test 2>&1 | grep -E 'Traceback|UndefinedColumn|TemplateSyntaxError|InternalError' || true)"
  if [ -n "$ERRORS" ]; then
    echo "$ERRORS"
    FAIL=1
  else
    echo "NO CRITICAL ERRORS"
  fi
else
  echo "Staging not running - SKIP"
fi

echo
echo "====================================="
if [ "$FAIL" -eq 0 ]; then
  echo "FULL WORKFLOW QA: PASS"
else
  echo "FULL WORKFLOW QA: FAIL"
fi
echo "====================================="
exit "$FAIL"
