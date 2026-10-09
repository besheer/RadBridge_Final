#!/usr/bin/env bash
set -euo pipefail
ID="${1:?tenant id required}"; BACKUP="${2:?backup directory required}"
DIR="tenants/$ID"; ENV="$DIR/.env"; COMPOSE="$DIR/compose.yml"
[[ -f "$ENV" && -f "$BACKUP/database.dump" ]] || { echo "Missing tenant or backup"; exit 2; }
(cd "$BACKUP" && sha256sum -c SHA256SUMS)
set -a; source "$ENV"; set +a
docker compose --env-file "$ENV" -f "$COMPOSE" -p "radbridge_$ID" up -d db pacs
sleep 5
docker compose --env-file "$ENV" -f "$COMPOSE" -p "radbridge_$ID" exec -T db \
  pg_restore -U "$DB_USER" -d "$DB_NAME" --clean --if-exists < "$BACKUP/database.dump"
for V in reports attachments uploads pacs; do
  VOL="radbridge_${ID}_${V}"
  docker run --rm -v "$VOL:/dst" -v "$(pwd)/$BACKUP:/backup:ro" alpine \
    sh -c "rm -rf /dst/* && tar -xzf /backup/${V}.tar.gz -C /dst"
done
docker compose --env-file "$ENV" -f "$COMPOSE" -p "radbridge_$ID" up -d --build
echo "Restore complete for $ID"
