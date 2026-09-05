#!/bin/sh
set -eu

PYTHON_BIN="${PYTHON_BIN:-python3}"

if ! "$PYTHON_BIN" -m pytest --version >/dev/null 2>&1; then
    if [ -x /opt/ris-pacs/test-envs/v5432/bin/python ]; then
        PYTHON_BIN=/opt/ris-pacs/test-envs/v5432/bin/python
    else
        echo "[FAIL] pytest is not available"
        exit 1
    fi
fi

echo "[1/5] Python syntax"
"$PYTHON_BIN" -m py_compile \
    app.py \
    radbridge_ocr.py \
    radbridge_intake.py \
    workflow_engine.py \
    procedure_catalog.py \
    pacs_worker.py

echo "[2/5] Stabilization contract tests"
"$PYTHON_BIN" -m pytest -q tests/test_v5442_stabilization_contract.py

echo "[3/5] Full regression suite"
"$PYTHON_BIN" -m pytest -q tests/

echo "[4/5] Version"
"$PYTHON_BIN" - <<'PY'
import app
assert app.APP_VERSION == "5.44.2", app.APP_VERSION
print("APP_VERSION =", app.APP_VERSION)
PY

echo "[5/5] Source checks"
test -f templates/order_form.html
test -f workflow_engine.py
test -f pacs_worker.py
test -f procedure_catalog.py

echo
echo "V5.44.2 PREFLIGHT PASSED"
