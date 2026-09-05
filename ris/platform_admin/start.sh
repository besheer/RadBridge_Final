#!/bin/sh
set -e
python - <<'PY'
from radbridge_platform import app,bootstrap
with app.app_context(): bootstrap()
print("RadBridge Platform DB bootstrap: PASS")
PY
exec gunicorn -b 0.0.0.0:9000 -w 2 --threads 4 radbridge_platform:app
