#!/bin/bash
# ============================================================
# Синхронизация cvgorod_chat_id из CVGorod API
# 
# Использование:
#   ./scripts/sync_cvgorod_ids.sh [--dry-run]
#
# Перед запуском убедитесь что:
#   1. data/cvgorod_chats.json содержит актуальные данные из CVGorod API
#   2. Docker контейнеры запущены (или DATABASE_URL указан)
# ============================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Определяем DATABASE_URL
if [ -z "$DATABASE_URL" ]; then
    # Пробуем загрузить из .env
    if [ -f "$PROJECT_DIR/.env" ]; then
        export $(grep -E '^DATABASE_URL=' "$PROJECT_DIR/.env" | xargs)
    fi
    
    # Если всё ещё пусто, используем дефолт для локального Docker
    if [ -z "$DATABASE_URL" ]; then
        export DATABASE_URL="postgresql://cvgorod:cvgorod@localhost:5433/cvgorod_hub"
    fi
fi

echo "=== Синхронизация cvgorod_chat_id ==="
echo "Project: $PROJECT_DIR"
echo ""

# Проверяем наличие JSON файла
if [ ! -f "$PROJECT_DIR/data/cvgorod_chats.json" ]; then
    echo "❌ Файл data/cvgorod_chats.json не найден!"
    echo "   Скачайте данные из CVGorod API: GET /api/Chats"
    exit 1
fi

# Запускаем Python скрипт
cd "$PROJECT_DIR"
python3 scripts/sync_cvgorod_ids.py "$@"

echo ""
echo "✅ Готово!"
