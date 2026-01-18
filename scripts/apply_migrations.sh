#!/bin/bash
# ============================================================
# Скрипт применения миграций и проверки схемы БД
# Запускать после восстановления из бэкапа или при деплое
# ============================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DB_CONTAINER="${DB_CONTAINER:-cvgorod-hub-postgres}"
DB_USER="${DB_USER:-cvgorod}"
DB_NAME="${DB_NAME:-cvgorod_hub}"

echo "=== Применение миграций cvgorod-hub ==="
echo "Container: $DB_CONTAINER"
echo "Database: $DB_NAME"
echo ""

# Список миграций в порядке применения
MIGRATIONS=(
    "migrate_add_roles.sql"
    "migrate_add_patterns.sql"
    "migrate_add_sentiment.sql"
    "migrate_add_customers.sql"
    "migrate_add_unique_message_index.sql"
    "migrate_add_cvgorod_chat_id.sql"
)

for migration in "${MIGRATIONS[@]}"; do
    migration_file="$SCRIPT_DIR/$migration"
    if [ -f "$migration_file" ]; then
        echo "Applying: $migration"
        docker cp "$migration_file" "$DB_CONTAINER:/tmp/$migration"
        docker exec "$DB_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -f "/tmp/$migration" 2>&1 | grep -v "^NOTICE:" || true
        echo "  ✓ Done"
    else
        echo "  ⚠ Not found: $migration (skipping)"
    fi
done

echo ""
echo "=== Проверка схемы БД ==="
docker cp "$SCRIPT_DIR/check_db_schema.sql" "$DB_CONTAINER:/tmp/check_db_schema.sql"
docker exec "$DB_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -f "/tmp/check_db_schema.sql"

echo ""
echo "=== Миграции применены успешно ==="
