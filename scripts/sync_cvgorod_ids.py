#!/usr/bin/env python3
"""
Синхронизация cvgorod_chat_id из CVGorod API в БД cvgorod-hub.

Скрипт:
1. Загружает данные из data/cvgorod_chats.json (дамп CVGorod API)
2. Добавляет колонку cvgorod_chat_id в таблицу chats (если нет)
3. Обновляет cvgorod_chat_id для всех чатов по telegram_chat_id

Usage:
    python scripts/sync_cvgorod_ids.py [--dry-run] [--update-json]
    
Options:
    --dry-run       Показать что будет сделано без изменений в БД
    --update-json   Обновить cvgorod_chats.json из API перед синхронизацией

Примеры:
    # Синхронизация из локального JSON
    python scripts/sync_cvgorod_ids.py
    
    # Только показать что будет обновлено
    python scripts/sync_cvgorod_ids.py --dry-run
"""

import argparse
import asyncio
import json
import logging
import os
import sys
from pathlib import Path

# Добавляем корень проекта в PYTHONPATH
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncpg

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Путь к файлу с данными CVGorod API
CVGOROD_CHATS_JSON = Path(__file__).parent.parent / "data" / "cvgorod_chats.json"


async def get_db_connection() -> asyncpg.Connection:
    """Получить подключение к БД."""
    database_url = os.getenv(
        "DATABASE_URL",
        "postgresql://cvgorod:cvgorod@localhost:5433/cvgorod_hub"
    )
    return await asyncpg.connect(database_url)


async def ensure_cvgorod_chat_id_column(conn: asyncpg.Connection, dry_run: bool = False) -> tuple[bool, bool]:
    """
    Добавить колонку cvgorod_chat_id в таблицу chats если её нет.
    
    Returns:
        (column_was_added, column_exists)
    """
    # Проверяем существует ли колонка
    exists = await conn.fetchval("""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.columns 
            WHERE table_name = 'chats' AND column_name = 'cvgorod_chat_id'
        )
    """)
    
    if exists:
        logger.info("✓ Колонка cvgorod_chat_id уже существует в таблице chats")
        return False, True
    
    if dry_run:
        logger.info("[DRY RUN] Будет добавлена колонка cvgorod_chat_id в таблицу chats")
        return True, False  # column_exists = False в dry-run
    
    # Добавляем колонку
    await conn.execute("""
        ALTER TABLE chats ADD COLUMN cvgorod_chat_id INTEGER;
        CREATE INDEX IF NOT EXISTS idx_chats_cvgorod_id ON chats(cvgorod_chat_id);
    """)
    logger.info("✓ Добавлена колонка cvgorod_chat_id в таблицу chats")
    return True, True


def load_cvgorod_api_data() -> list[dict]:
    """Загрузить данные из JSON файла."""
    if not CVGOROD_CHATS_JSON.exists():
        logger.error(f"Файл не найден: {CVGOROD_CHATS_JSON}")
        logger.info("Скачайте данные из CVGorod API: GET /api/Chats")
        sys.exit(1)
    
    with open(CVGOROD_CHATS_JSON) as f:
        data = json.load(f)
    
    logger.info(f"Загружено {len(data)} чатов из {CVGOROD_CHATS_JSON.name}")
    return data


async def sync_cvgorod_ids(
    conn: asyncpg.Connection,
    cvgorod_data: list[dict],
    dry_run: bool = False,
    column_exists: bool = True
) -> dict:
    """Синхронизировать cvgorod_chat_id в БД."""
    stats = {
        "total_api": len(cvgorod_data),
        "matched": 0,
        "updated": 0,
        "not_found": 0,
        "already_set": 0,
    }
    
    # Создаём маппинг telegram_id -> cvgorod_id
    tg_to_cvgorod = {}
    for chat in cvgorod_data:
        tg_id = chat.get("messengerChatId")
        cvgorod_id = chat.get("id")
        if tg_id and cvgorod_id:
            tg_to_cvgorod[str(tg_id)] = cvgorod_id
    
    logger.info(f"Создан маппинг: {len(tg_to_cvgorod)} telegram_id -> cvgorod_id")
    
    # Получаем все чаты из нашей БД
    if column_exists:
        our_chats = await conn.fetch("SELECT id, name, cvgorod_chat_id FROM chats")
    else:
        # Колонка ещё не создана - получаем без неё
        rows = await conn.fetch("SELECT id, name FROM chats")
        our_chats = [{"id": r["id"], "name": r["name"], "cvgorod_chat_id": None} for r in rows]
    logger.info(f"Чатов в БД: {len(our_chats)}")
    
    updates = []
    not_found = []
    
    for chat in our_chats:
        tg_id = str(chat["id"])
        current_cvgorod_id = chat["cvgorod_chat_id"]
        
        if tg_id in tg_to_cvgorod:
            new_cvgorod_id = tg_to_cvgorod[tg_id]
            stats["matched"] += 1
            
            if current_cvgorod_id == new_cvgorod_id:
                stats["already_set"] += 1
            else:
                updates.append({
                    "tg_id": int(tg_id),
                    "cvgorod_id": new_cvgorod_id,
                    "name": chat["name"],
                    "old_cvgorod_id": current_cvgorod_id,
                })
        else:
            stats["not_found"] += 1
            not_found.append({
                "tg_id": tg_id,
                "name": chat["name"],
            })
    
    # Показываем что будет обновлено
    if updates:
        logger.info(f"\nБудет обновлено {len(updates)} чатов:")
        for u in updates[:10]:
            old = u["old_cvgorod_id"] or "NULL"
            logger.info(f"  {u['name'][:40]}: {old} -> {u['cvgorod_id']}")
        if len(updates) > 10:
            logger.info(f"  ... и ещё {len(updates) - 10}")
    
    # Выполняем обновление
    if not dry_run and updates:
        for u in updates:
            await conn.execute(
                "UPDATE chats SET cvgorod_chat_id = $1 WHERE id = $2",
                u["cvgorod_id"], u["tg_id"]
            )
        stats["updated"] = len(updates)
        logger.info(f"✓ Обновлено {len(updates)} записей")
    elif dry_run and updates:
        logger.info(f"[DRY RUN] Было бы обновлено {len(updates)} записей")
    
    # Показываем чаты без cvgorod_id
    if not_found and len(not_found) <= 20:
        logger.info(f"\nЧаты без cvgorod_id ({len(not_found)} шт):")
        for nf in not_found:
            logger.info(f"  {nf['tg_id']}: {nf['name'][:50]}")
    elif not_found:
        logger.info(f"\nЧатов без cvgorod_id: {len(not_found)}")
    
    return stats


async def main():
    parser = argparse.ArgumentParser(description="Sync cvgorod_chat_id from CVGorod API")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done")
    parser.add_argument("--update-json", action="store_true", help="Update JSON from API first")
    args = parser.parse_args()
    
    logger.info("=" * 60)
    logger.info("Синхронизация cvgorod_chat_id")
    logger.info("=" * 60)
    
    if args.update_json:
        logger.warning("--update-json не реализован. Обновите вручную из CVGorod API.")
    
    # Загружаем данные из JSON
    cvgorod_data = load_cvgorod_api_data()
    
    # Подключаемся к БД
    try:
        conn = await get_db_connection()
        logger.info("✓ Подключено к БД")
    except Exception as e:
        logger.error(f"Ошибка подключения к БД: {e}")
        sys.exit(1)
    
    try:
        # Добавляем колонку если нужно
        _, column_exists = await ensure_cvgorod_chat_id_column(conn, args.dry_run)
        
        # Синхронизируем ID
        stats = await sync_cvgorod_ids(conn, cvgorod_data, args.dry_run, column_exists)
        
        # Итог
        logger.info("\n" + "=" * 60)
        logger.info("ИТОГ:")
        logger.info(f"  Чатов в CVGorod API: {stats['total_api']}")
        logger.info(f"  Найдено совпадений: {stats['matched']}")
        logger.info(f"  Уже установлено: {stats['already_set']}")
        logger.info(f"  Обновлено: {stats['updated']}")
        logger.info(f"  Не найдено в API: {stats['not_found']}")
        logger.info("=" * 60)
        
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
