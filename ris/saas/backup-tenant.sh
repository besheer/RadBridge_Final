#!/usr/bin/env bash
set -euo pipefail
ID="${1:?tenant id required}"
DIR="tenants/$ID"; ENV="$DIR/.env"; COMPOSE="$DIR/compose.yml"
[[ -f "$ENV" ]] || { echo "Tenant not found"; exit 2; }
set -a; source "$ENV"; set +a
STAMP="$(date +%Y%m%d-%H%M%S)"
OUT="tenant-backups/$ID/$STAMP"; mkdir -p "$OUT"; chmod 700 "$OUT"
docker compose --env-file "$ENV" -f "$COMPOSE" -p "radbridge_$ID" exec -T db \
  pg_dump -U "$DB_USER" -d "$DB_NAME" -Fc > "$OUT/database.dump"
for V in reports attachments uploads pacs; do
  VOL="radbridge_${ID}_${V}"
  docker run --rm -v "$VOL:/src:ro" -v "$(pwd)/$OUT:/backup" alpine \
    sh -c "cd /src && tar -czf /backup/${V}.tar.gz ."
done
cp "$ENV" "$OUT/tenant.env"
chmod 600 "$OUT/tenant.env"
(cd "$OUT" && sha256sum database.dump *.tar.gz > SHA256SUMS)
echo "$OUT"
