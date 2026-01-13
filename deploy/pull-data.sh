#!/bin/bash
# =============================================================================
# cvgorod-hub Pull Data Script
# =============================================================================
# Download production data to local environment
# Usage: ./deploy/pull-data.sh [--db|--redis|--all]
# =============================================================================

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

PROJECT_DIR="/Users/danielbadygov/cvgorod-hub"
SERVER="158.160.153.14"
SSH_KEY="~/.ssh/yandex_vm_key"
REMOTE_DIR="/home/badygovdaniil/cvgorod-hub"
LOCAL_DATA_DIR="$PROJECT_DIR/data"
LOCAL_BACKUPS_DIR="$PROJECT_DIR/backups"

# Default: sync all
SYNC_DB=false
SYNC_REDIS=false
SYNC_ALL=true

# Parse arguments
for arg in "$@"; do
    case $arg in
        --db)
            SYNC_DB=true
            SYNC_ALL=false
            ;;
        --redis)
            SYNC_REDIS=true
            SYNC_ALL=false
            ;;
        --all)
            SYNC_ALL=true
            ;;
    esac
done

echo_step() {
    echo -e "${GREEN}[PULL]${NC} $1"
}

echo_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

# =============================================================================
# Pull Database
# =============================================================================

pull_db() {
    echo_step "Pulling PostgreSQL database..."

    TIMESTAMP=$(date +%Y%m%d_%H%M%S)
    BACKUP_FILE="$LOCAL_BACKUPS_DIR/db_backup_$TIMESTAMP.sql"

    # Create local backup directory
    mkdir -p "$LOCAL_BACKUPS_DIR"

    # Dump remote database and download (decompress locally)
    ssh -i "$SSH_KEY" badygovdaniil@$SERVER "
        cd $REMOTE_DIR
        docker compose exec -T postgres pg_dump -U cvgorod cvgorod_hub | gzip
    " | gzip -d > "$BACKUP_FILE"

    echo -e "${GREEN}[OK]${NC} Database saved to: $BACKUP_FILE"
    echo "  Size: $(du -h "$BACKUP_FILE" | cut -f1)"
}

# =============================================================================
# Pull Redis
# =============================================================================

pull_redis() {
    echo_step "Pulling Redis data..."

    TIMESTAMP=$(date +%Y%m%d_%H%M%S)
    BACKUP_FILE="$LOCAL_DATA_DIR/redis_backup_$TIMESTAMP.rdb"

    # Create local data directory
    mkdir -p "$LOCAL_DATA_DIR"

    # Copy Redis RDB file
    scp -i "$SSH_KEY" badygovdaniil@$SERVER:"$REMOTE_DIR/redis_data/dump.rdb" "$BACKUP_FILE" 2>/dev/null || \
    ssh -i "$SSH_KEY" badygovdaniil@$SERVER "
        docker cp cvgorod-hub-redis:/data/dump.rdb /tmp/dump.rdb
    " && \
    scp -i "$SSH_KEY" badygovdaniil@$SERVER:/tmp/dump.rdb "$BACKUP_FILE" && \
    ssh -i "$SSH_KEY" badygovdaniil@$SERVER "rm /tmp/dump.rdb"

    if [[ -f "$BACKUP_FILE" ]]; then
        echo -e "${GREEN}[OK]${NC} Redis data saved to: $BACKUP_FILE"
        echo "  Size: $(du -h "$BACKUP_FILE" | cut -f1)"
    else
        echo_warn "Could not pull Redis data (RDB file may not exist)"
    fi
}

# =============================================================================
# Main
# =============================================================================

echo_step "Starting data pull from production..."
echo "  Server: $SERVER"
echo "  Remote dir: $REMOTE_DIR"
echo ""

if [[ "$SYNC_ALL" == "true" ]] || [[ "$SYNC_DB" == "true" ]]; then
    pull_db
    echo ""
fi

if [[ "$SYNC_ALL" == "true" ]] || [[ "$SYNC_REDIS" == "true" ]]; then
    pull_redis
    echo ""
fi

echo -e "${GREEN}[DONE]${NC} Data pull completed!"
