#!/bin/bash
# =============================================================
# Cron скрипт для синхронизации UUID маппинга из УЗ API
# Запускается ежедневно в 04:00 (после бэкапа БД в 03:00)
# =============================================================

LOG_DIR="$HOME/logs"
LOG_FILE="$LOG_DIR/cvgorod-hub-sync.log"
mkdir -p "$LOG_DIR"

# Загружаем секреты
source ~/.secrets/cvgorod/hub_api.env

echo "$(date '+%Y-%m-%d %H:%M:%S') - Starting UUID mapping sync..." >> "$LOG_FILE"

# Вызываем API для синхронизации
RESPONSE=$(curl -s -w "\n%{http_code}" \
    -X POST "http://127.0.0.1:8300/api/v1/mapping/sync" \
    -H "Authorization: Bearer $HUB_API_KEY" \
    -H "Content-Type: application/json")

HTTP_CODE=$(echo "$RESPONSE" | tail -n1)
BODY=$(echo "$RESPONSE" | head -n-1)

if [ "$HTTP_CODE" -eq 200 ]; then
    echo "$(date '+%Y-%m-%d %H:%M:%S') - Sync SUCCESS: $BODY" >> "$LOG_FILE"
else
    echo "$(date '+%Y-%m-%d %H:%M:%S') - Sync FAILED (HTTP $HTTP_CODE): $BODY" >> "$LOG_FILE"
fi

# Получаем статистику
STATS=$(curl -s "http://127.0.0.1:8300/api/v1/mapping/stats" \
    -H "Authorization: Bearer $HUB_API_KEY")

echo "$(date '+%Y-%m-%d %H:%M:%S') - Stats: $STATS" >> "$LOG_FILE"
echo "---" >> "$LOG_FILE"
