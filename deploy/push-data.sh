#!/bin/bash
# =============================================================================
# cvgorod-hub Push Data Script
# =============================================================================
# Upload local data to production environment
# Usage: ./deploy/push-data.sh [--db <file>|--redis <file>|--all]
# =============================================================================

set -e

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

PROJECT_DIR="/Users/danielbadygov/cvgorod-hub"
SERVER="158.160.153.14"
SSH_KEY="~/.ssh/yandex_vm_key"
REMOTE_DIR="/home/badygovdaniil/cvgorod-hub"
LOCAL_BACKUPS_DIR="$PROJECT_DIR/backups"

echo_step() {
    echo -e "${GREEN}[PUSH]${NC} $1"
}

echo_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

echo_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# =============================================================================
# Push Database
# =============================================================================

push_db() {
    local DB_FILE="$1"

    if [[ -z "$DB_FILE" ]]; then
        # Find latest backup
        DB_FILE=$(ls -1t "$LOCAL_BACKUPS_DIR"/db_backup_*.sql.gz 2>/dev/null | head -1)
        if [[ -z "$DB_FILE" ]]; then
            echo_error "No database backup found in $LOCAL_BACKUPS_DIR"
            echo "Usage: $0 --db <backup_file.sql.gz>"
            exit 1
        fi
        echo_step "Using latest backup: $DB_FILE"
    fi

    if [[ ! -f "$DB_FILE" ]]; then
        echo_error "File not found: $DB_FILE"
        exit 1
    fi

    echo_step "Pushing database..."
    echo "  File: $DB_FILE"
    echo "  Size: $(du -h "$DB_FILE" | cut -f1)"

    # Create remote backup first
    TIMESTAMP=$(date +%Y%m%d_%H%M%S)
    ssh -i "$SSH_KEY" badygovdaniil@$SERVER "
        cd $REMOTE_DIR
        docker compose exec -T postgres pg_dump -U cvgorod cvgorod_hub | gzip > /tmp/pre_push_backup_$TIMESTAMP.sql.gz
    "

    # Upload and restore
    cat "$DB_FILE" | gzip | ssh -i "$SSH_KEY" badygovdaniil@$SERVER "
        cd $REMOTE_DIR
        gunzip | docker compose exec -T postgres psql -U cvgorod -d cvgorod_hub
    "

    echo -e "${GREEN}[OK]${NC} Database restored successfully"
}

# =============================================================================
# Push Redis
# =============================================================================

push_redis() {
    local REDIS_FILE="$1"

    if [[ -z "$REDIS_FILE" ]]; then
        # Find latest backup
        REDIS_FILE=$(ls -1t "$PROJECT_DIR"/data/redis_backup_*.rdb 2>/dev/null | head -1)
        if [[ -z "$REDIS_FILE" ]]; then
            echo_error "No Redis backup found in $PROJECT_DIR/data"
            echo "Usage: $0 --redis <backup_file.rdb>"
            exit 1
        fi
        echo_step "Using latest backup: $REDIS_FILE"
    fi

    if [[ ! -f "$REDIS_FILE" ]]; then
        echo_error "File not found: $REDIS_FILE"
        exit 1
    fi

    echo_step "Pushing Redis data..."
    echo "  File: $REDIS_FILE"
    echo "  Size: $(du -h "$REDIS_FILE" | cut -f1)"

    # Upload RDB file
    scp -i "$SSH_KEY" "$REDIS_FILE" badygovdaniil@$SERVER:/tmp/dump.rdb

    # Restore to container
    ssh -i "$SSH_KEY" badygovdaniil@$SERVER "
        docker cp /tmp/dump.rdb cvgorod-hub-redis:/data/dump.rdb
        rm /tmp/dump.rdb
        docker restart cvgorod-hub-redis
    "

    echo -e "${GREEN}[OK]${NC} Redis data restored successfully"
}

# =============================================================================
# Main
# =============================================================================

DB_FILE=""
REDIS_FILE=""
PUSH_ALL=false

# Parse arguments
for arg in "$@"; do
    case $arg in
        --db)
            NEXT_ARG=false
            for a in "$@"; do
                if [[ "$NEXT_ARG" == "true" ]]; then
                    DB_FILE="$a"
                    break
                fi
                if [[ "$a" == "--db" ]]; then
                    NEXT_ARG="true"
                fi
            done
            ;;
        --redis)
            NEXT_ARG=false
            for a in "$@"; do
                if [[ "$NEXT_ARG" == "true" ]]; then
                    REDIS_FILE="$a"
                    break
                fi
                if [[ "$a" == "--redis" ]]; then
                    NEXT_ARG="true"
                fi
            done
            ;;
        --all)
            PUSH_ALL=true
            ;;
        --help|-h)
            echo "Usage: $0 [--db <file>] [--redis <file>] [--all]"
            echo ""
            echo "Options:"
            echo "  --db <file>    Push database backup to production"
            echo "  --redis <file> Push Redis RDB file to production"
            echo "  --all          Push all data (db + redis)"
            echo "  --help         Show this help"
            exit 0
            ;;
    esac
done

echo_step "Starting data push to production..."
echo "  Server: $SERVER"
echo "  Remote dir: $REMOTE_DIR"
echo ""

# Confirmation
if [[ "$PUSH_ALL" == "true" ]] || [[ -n "$DB_FILE" ]] || [[ -n "$REDIS_FILE" ]]; then
    echo_warn "This will overwrite production data!"
    echo -n "Continue? [y/N]: "
    read -r confirm
    if [[ "$confirm" != "y" ]] && [[ "$confirm" != "Y" ]]; then
        echo "Aborted."
        exit 0
    fi
fi

if [[ "$PUSH_ALL" == "true" ]]; then
    push_db ""
    echo ""
    push_redis ""
elif [[ -n "$DB_FILE" ]]; then
    push_db "$DB_FILE"
elif [[ -n "$REDIS_FILE" ]]; then
    push_redis "$REDIS_FILE"
else
    echo_error "No action specified"
    echo "Use --help for usage information"
    exit 1
fi

echo ""
echo -e "${GREEN}[DONE]${NC} Data push completed!"
