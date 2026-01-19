#!/usr/bin/env python3
"""
Синхронизация customer_uuid маппинга из УЗ API.

Запуск:
    python scripts/sync_uz_mapping.py

Cron (раз в сутки в 4 утра):
    0 4 * * * cd /home/badygovdaniil/cvgorod-hub && python scripts/sync_uz_mapping.py

Что делает:
1. Получает список чатов из УЗ API (/Messages/ChatBots)
2. Для каждого находит telegram_chat_id в таблице chats
3. Сохраняет/обновляет в customer_uuid_mapping
"""

import asyncio
import logging
import os
import sys
from datetime import datetime, UTC
from pathlib import Path

# Добавляем корень проекта в PYTHONPATH
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Загружаем .env
from dotenv import load_dotenv
load_dotenv(project_root / ".env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


async def sync_uz_mapping() -> dict:
    """
    Синхронизация маппинга из УЗ API.
    
    Returns:
        dict с результатами: total, synced, with_telegram, errors
    """
    from services.database import db
    from services.uz_api import uz_api

    await db.connect()
    
    start_time = datetime.now(UTC)
    result = {
        "total": 0,
        "synced": 0,
        "with_telegram": 0,
        "without_telegram": 0,
        "errors": [],
    }

    try:
        # 1. Получаем чаты из УЗ API
        logger.info("Fetching chatbots from UZ API...")
        chatbots = await uz_api.get_chatbots()
        
        if not chatbots:
            result["errors"].append("No chatbots received from UZ API")
            return result
        
        result["total"] = len(chatbots)
        logger.info("Received %d chatbots from UZ API", len(chatbots))

        # 2. Обрабатываем каждый чат
        for chat in chatbots:
            try:
                # Находим telegram_chat_id и sync_id в наших данных
                row = await db.fetchrow("""
                    SELECT 
                        c.id as telegram_chat_id,
                        cu.sync_id
                    FROM chats c
                    LEFT JOIN customers cu ON c.customer_id = cu.id
                    WHERE c.cvgorod_chat_id = $1
                """, chat.id)

                telegram_chat_id = row["telegram_chat_id"] if row else None
                sync_id = row["sync_id"] if row else None

                if telegram_chat_id:
                    result["with_telegram"] += 1
                else:
                    result["without_telegram"] += 1

                # Upsert в маппинг
                await db.execute("""
                    INSERT INTO customer_uuid_mapping 
                        (customer_uuid, cvgorod_chat_id, chat_id, customer_name, sync_id, updated_at)
                    VALUES ($1, $2, $3, $4, $5, NOW())
                    ON CONFLICT (customer_uuid) DO UPDATE SET
                        cvgorod_chat_id = EXCLUDED.cvgorod_chat_id,
                        chat_id = EXCLUDED.chat_id,
                        customer_name = EXCLUDED.customer_name,
                        sync_id = EXCLUDED.sync_id,
                        updated_at = NOW()
                """, 
                    chat.customer_id,
                    chat.id,
                    telegram_chat_id,
                    chat.name,
                    sync_id,
                )
                
                result["synced"] += 1

            except Exception as e:
                error_msg = f"Error processing chat {chat.id}: {e}"
                logger.error(error_msg)
                result["errors"].append(error_msg)

        duration = (datetime.now(UTC) - start_time).total_seconds()
        result["duration_seconds"] = duration
        
        logger.info(
            "Sync completed: %d/%d synced, %d with telegram, %.2fs",
            result["synced"], result["total"], result["with_telegram"], duration
        )

        return result

    except Exception as e:
        logger.exception("Sync failed: %s", e)
        result["errors"].append(str(e))
        return result

    finally:
        await db.disconnect()


async def main():
    """Главная функция."""
    logger.info("=" * 60)
    logger.info("Starting UZ mapping sync")
    logger.info("=" * 60)

    result = await sync_uz_mapping()

    logger.info("-" * 40)
    logger.info("Results:")
    logger.info("  Total chatbots: %d", result["total"])
    logger.info("  Synced: %d", result["synced"])
    logger.info("  With Telegram ID: %d", result["with_telegram"])
    logger.info("  Without Telegram ID: %d", result["without_telegram"])
    
    if result.get("errors"):
        logger.error("  Errors: %d", len(result["errors"]))
        for err in result["errors"][:5]:
            logger.error("    - %s", err)

    logger.info("=" * 60)
    
    return 0 if not result.get("errors") else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
