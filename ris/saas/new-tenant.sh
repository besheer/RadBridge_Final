#!/usr/bin/env bash
set -euo pipefail
TENANT_ID="${1:-}"
TENANT_NAME="${2:-}"
LOCAL_PORT="${3:-}"
DOMAIN="${4:-}"
if [[ ! "$TENANT_ID" =~ ^[a-z0-9][a-z0-9-]{2,31}$ ]]; then
  echo "Usage: $0 tenant-id 'Tenant Name' local-port domain"; exit 2
fi
[[ -n "$TENANT_NAME" && "$LOCAL_PORT" =~ ^[0-9]+$ && -n "$DOMAIN" ]] || { echo "Missing arguments"; exit 2; }
umask 077
DIR="tenants/$TENANT_ID"
mkdir -p "$DIR"
openssl rand -hex 32 > "$DIR/.dbpass"
openssl rand -hex 48 > "$DIR/.secret"
openssl rand -hex 32 > "$DIR/.pacspass"
DBPASS="$(cat "$DIR/.dbpass")"; SECRET="$(cat "$DIR/.secret")"; PACSPASS="$(cat "$DIR/.pacspass")"
AET="$(echo "$TENANT_ID" | tr '[:lower:]-' '[:upper:]_' | cut -c1-16)"
cat > "$DIR/.env" <<EOF
TENANT_ID=$TENANT_ID
TENANT_NAME=$TENANT_NAME
RIS_LOCAL_PORT=$LOCAL_PORT
RIS_PUBLIC_URL=https://$DOMAIN
DB_NAME=ris
DB_USER=ris
DB_PASSWORD=$DBPASS
SECRET_KEY=$SECRET
PACS_AET=$AET
PACS_USER=orthanc
PACS_PASSWORD=$PACSPASS
PACS_BIND_IP=127.0.0.1
PACS_DICOM_PORT=$((LOCAL_PORT+1000))
ORTHANC_PUBLIC_URL=
EOF
rm -f "$DIR/.dbpass" "$DIR/.secret" "$DIR/.pacspass"
cp saas/docker-compose.tenant.yml "$DIR/compose.yml"
chmod 600 "$DIR/.env"
echo "Created isolated tenant: $DIR"
echo "Deploy: docker compose --env-file $DIR/.env -f $DIR/compose.yml -p radbridge_$TENANT_ID up -d --build"
