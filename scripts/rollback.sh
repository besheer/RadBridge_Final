#!/bin/bash
set -e

REPO_DIR="/home/rispacs/RadBridge_Final"
cd "$REPO_DIR"

echo "=========================================================="
echo "  AirScan RIS/PACS - Rollback & Recovery Utility"
echo "=========================================================="

TARGET="$1"

if [ -z "$TARGET" ]; then
    echo "Recent Checkpoints (Tags):"
    git tag -l 'checkpoint-*' --sort=-creatordate | head -n 8 | while read -r tag; do
        commit=$(git rev-parse --short "$tag")
        desc=$(git tag -n1 -l "$tag" | sed "s/$tag[[:space:]]*//")
        echo "  🏷️  $tag ($commit) -> $desc"
    done
    echo ""
    echo "Recent Commits:"
    git log -n 8 --pretty=format:"  📌 %h | %ad | %s" --date=short
    echo ""
    echo "----------------------------------------------------------"
    read -p "Enter Commit Hash or Tag to rollback to (or 'q' to cancel): " TARGET
    if [ "$TARGET" = "q" ] || [ -z "$TARGET" ]; then
        echo "Rollback cancelled."
        exit 0
    fi
fi

# Validate target
if ! git rev-parse --verify "$TARGET" >/dev/null 2>&1; then
    echo "❌ Error: Target '$TARGET' is not a valid commit or tag!"
    exit 1
fi

TARGET_COMMIT=$(git rev-parse --short "$TARGET")
TARGET_MSG=$(git log -1 --pretty=format:"%s" "$TARGET")
CURRENT_COMMIT=$(git rev-parse --short HEAD)

if [ "$TARGET_COMMIT" = "$CURRENT_COMMIT" ]; then
    echo "ℹ️  System is already at target commit $TARGET_COMMIT: $TARGET_MSG"
    exit 0
fi

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_BRANCH="backup-before-rollback-$TIMESTAMP"

echo ""
echo "[1/4] Creating safety backup branch: $BACKUP_BRANCH..."
git branch "$BACKUP_BRANCH" HEAD
echo "      Safety branch '$BACKUP_BRANCH' created at commit $CURRENT_COMMIT."

echo "[2/4] Rolling back code to $TARGET ($TARGET_COMMIT)..."
git reset --hard "$TARGET"

echo "[3/4] Restarting ris-web container..."
docker restart ris-web >/dev/null
sleep 3

echo "[4/4] Verifying system health check..."
STATUS=$(docker exec ris-web python -c "
import app
with app.app.test_request_context():
    client = app.app.test_client()
    resp = client.get('/login')
    print(resp.status_code)
" 2>/dev/null || echo "FAILED")

if [ "$STATUS" = "200" ]; then
    echo "      System health check: 200 OK (Healthy)"
else
    echo "      System health check: $STATUS"
fi

echo ""
echo "=========================================================="
echo "✅ Rollback successfully completed!"
echo "   Current Active Commit: $TARGET_COMMIT ($TARGET_MSG)"
echo ""
echo "ℹ️  If you ever want to UNDO this rollback, simply run:"
echo "   /home/rispacs/RadBridge_Final/scripts/rollback.sh $BACKUP_BRANCH"
echo "=========================================================="
