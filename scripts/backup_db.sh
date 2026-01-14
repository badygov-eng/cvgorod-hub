#!/bin/bash
# Бэкап PostgreSQL базы данных cvgorod-hub
# Использование: ./scripts/backup_db.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BACKUP_DIR="${PROJECT_DIR}/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Определяем контейнер (Docker или локальный)
if docker ps --format '{{.Names}}' | grep -q "cvgorod-hub-postgres"; then
    CONTAINER="cvgorod-hub-postgres"
    DB_USER="cvgorod"
    DB_NAME="cvgorod_hub"
    echo "📦 Используем Docker контейнер: ${CONTAINER}"
else
    # Локальная БД
    DB_USER="${PGUSER:-cvgorod}"
    DB_NAME="${PGDATABASE:-cvgorod_hub}"
    DB_HOST="${PGHOST:-127.0.0.1}"
    DB_PORT="${PGPORT:-5433}"
    echo "💻 Используем локальную БД: ${DB_HOST}:${DB_PORT}"
fi

# Создаём директорию для бэкапов
mkdir -p "$BACKUP_DIR"

BACKUP_FILE="${BACKUP_DIR}/backup_${TIMESTAMP}.sql"

echo "🔄 Создаю бэкап базы данных cvgorod_hub..."

if [ -n "$CONTAINER" ]; then
    # Docker бэкап
    docker compose -f "${PROJECT_DIR}/docker-compose.yml" exec -T postgres \
        pg_dump -U "$DB_USER" -d "$DB_NAME" --no-owner --no-acl \
        > "$BACKUP_FILE"
else
    # Локальный бэкап (PGPASSWORD должен быть установлен!)
    if [ -z "$PGPASSWORD" ]; then
        echo "ERROR: PGPASSWORD не установлен. Установите: export PGPASSWORD=<password>"
        exit 1
    fi
    PGPASSWORD="$PGPASSWORD" pg_dump \
        -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" \
        --no-owner --no-acl \
        > "$BACKUP_FILE"
fi

# Сжимаем
gzip "$BACKUP_FILE"
BACKUP_FILE="${BACKUP_FILE}.gz"

# Статистика
SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
echo ""
echo "✅ Бэкап создан:"
echo "   📁 ${BACKUP_FILE}"
echo "   📊 Размер: ${SIZE}"

# Очистка старых бэкапов (старше 30 дней)
echo ""
echo "🧹 Очистка бэкапов старше 30 дней..."
find "$BACKUP_DIR" -name "backup_*.sql.gz" -mtime +30 -delete 2>/dev/null || true
BACKUP_COUNT=$(ls -1 "$BACKUP_DIR"/backup_*.sql.gz 2>/dev/null | wc -l)
echo "   📁 Бэкапов в хранилище: ${BACKUP_COUNT}"

echo ""
echo "✨ Готово!"
