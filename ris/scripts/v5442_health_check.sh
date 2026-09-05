#!/bin/sh
set -eu
CONTAINER="${1:-ris-web}"
EXPECTED_IMAGE="${EXPECTED_IMAGE:-radbridge-ris:v5.44.2-production-stabilization}"
URL="${RIS_HEALTH_URL:-http://127.0.0.1:8090}"

image=$(docker inspect "$CONTAINER" --format '{{.Config.Image}}')
status=$(docker inspect "$CONTAINER" --format '{{.State.Status}}')
[ "$status" = running ] || { echo "FAIL: $CONTAINER status=$status"; exit 1; }
[ "$image" = "$EXPECTED_IMAGE" ] || { echo "FAIL: image=$image expected=$EXPECTED_IMAGE"; exit 1; }

code=$(curl -sS -o /dev/null -w '%{http_code}' "$URL/")
case "$code" in
  200|302) ;;
  *) echo "FAIL: HTTP $code from $URL/"; exit 1;;
esac

docker exec "$CONTAINER" python - <<'PY'
import app
assert app.APP_VERSION == '5.44.2'
assert app.BUILD_NAME == 'production-stabilization'
print('PASS: application metadata')
PY

echo 'HEALTH=PASS'
