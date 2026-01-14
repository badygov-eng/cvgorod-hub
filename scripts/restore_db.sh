#!/bin/bash
# Восстановление PostgreSQL базы данных cvgorod-hub из бэкапа
# Использование: ./scripts/restore_db.sh [backup_file.sql.gz]

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BACKUP_DIR="${PROJECT_DIR}/backups"

# Если файл не указан — показываем доступные
if [ -z "$1" ]; then
    echo "📁 Доступные бэкапы:"
    echo ""
    ls -lh "$BACKUP_DIR"/backup_*.sql.gz 2>/dev/null || echo "   Бэкапы не найдены"
    echo ""
    echo "Использование: $0 <backup_file.sql.gz>"
    exit 1
fi

BACKUP_FILE="$1"

# Проверяем существование файла
if [ ! -f "$BACKUP_FILE" ]; then
    # Пробуем в директории backups
    if [ -f "${BACKUP_DIR}/${BACKUP_FILE}" ]; then
        BACKUP_FILE="${BACKUP_DIR}/${BACKUP_FILE}"
    else
        echo "❌ Файл не найден: $BACKUP_FILE"
        exit 1
    fi
fi

echo "⚠️  ВНИМАНИЕ: Это действие ПЕРЕЗАПИШЕТ текущую базу данных!"
echo "   Файл: $BACKUP_FILE"
echo ""
read -p "Введите 'YES' для подтверждения: " CONFIRM

if [ "$CONFIRM" != "YES" ]; then
    echo "❌ Отменено"
    exit 1
fi

# Определяем контейнер
if docker ps --format '{{.Names}}' | grep -q "cvgorod-hub-postgres"; then
    CONTAINER="cvgorod-hub-postgres"
    DB_USER="cvgorod"
    DB_NAME="cvgorod_hub"
    echo "📦 Используем Docker контейнер: ${CONTAINER}"
else
    DB_USER="${PGUSER:-cvgorod}"
    DB_NAME="${PGDATABASE:-cvgorod_hub}"
    DB_HOST="${PGHOST:-127.0.0.1}"
    DB_PORT="${PGPORT:-5433}"
    echo "💻 Используем локальную БД: ${DB_HOST}:${DB_PORT}"
fi

echo ""
echo "🔄 Восстанавливаю базу данных..."

# Распаковываем если gzip
TEMP_FILE=""
if [[ "$BACKUP_FILE" == *.gz ]]; then
    TEMP_FILE=$(mktemp)
    gunzip -c "$BACKUP_FILE" > "$TEMP_FILE"
    RESTORE_FILE="$TEMP_FILE"
else
    RESTORE_FILE="$BACKUP_FILE"
fi

if [ -n "$CONTAINER" ]; then
    # Docker restore
    docker compose -f "${PROJECT_DIR}/docker-compose.yml" exec -T postgres \
        psql -U "$DB_USER" -d "$DB_NAME" -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
    
    cat "$RESTORE_FILE" | docker compose -f "${PROJECT_DIR}/docker-compose.yml" exec -T postgres \
        psql -U "$DB_USER" -d "$DB_NAME"
else
    # Локальный restore (PGPASSWORD должен быть установлен!)
    if [ -z "$PGPASSWORD" ]; then
        echo "ERROR: PGPASSWORD не установлен. Установите: export PGPASSWORD=<password>"
        exit 1
    fi
    PGPASSWORD="$PGPASSWORD" psql \
        -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" \
        -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
    
    PGPASSWORD="$PGPASSWORD" psql \
        -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" \
        < "$RESTORE_FILE"
fi

# Удаляем временный файл
[ -n "$TEMP_FILE" ] && rm -f "$TEMP_FILE"

echo ""
echo "✅ База данных восстановлена из: $(basename $BACKUP_FILE)"
echo "✨ Готово!"
