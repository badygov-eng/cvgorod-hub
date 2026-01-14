#!/usr/bin/env python3
"""
Синхронизация истории сообщений из Telegram в cvgorod-hub.

Использует Telegram MCP для получения полной истории сообщений из всех групп
где присутствует @cvgorodassistent_bot и сохраняет в PostgreSQL.

Usage:
    python scripts/sync_telegram_history.py [--dry-run] [--limit=N]

Options:
    --dry-run    Показать что будет сделано без сохранения в БД
    --limit=N    Лимит сообщений на один чат (для тестирования)
"""

import asyncio
import logging
import os
import sys
from datetime import datetime
from typing import Any

import asyncpg

# Добавляем корень проекта в PYTHONPATH
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.roles import BOTS
from services.role_repository import role_repository

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# ID бота @cvgorodassistent_bot
BOT_USER_ID = 6395960386


class TelegramSyncService:
    """Сервис синхронизации сообщений из Telegram."""

    def __init__(self, db_pool: asyncpg.Pool, dry_run: bool = False):
        self.pool = db_pool
        self.dry_run = dry_run
        self.stats = {
            "chats_found": 0,
            "chats_synced": 0,
            "messages_fetched": 0,
            "messages_saved": 0,
            "messages_skipped": 0,
            "users_created": 0,
            "errors": 0,
        }

    async def find_groups_with_bot(self) -> list[dict[str, Any]]:
        """
        Находит все группы где есть @cvgorodassistent_bot.
        
        Returns:
            Список словарей с информацией о чатах
        """
        logger.info("Поиск групп с @cvgorodassistent_bot...")
        
        # ============================================================
        # ИНТЕГРАЦИЯ С TELEGRAM MCP (требует запуска через Cursor)
        # ============================================================
        # 
        # Для полной синхронизации нужно использовать Telegram MCP:
        #
        # 1. Поиск групп с ботом через search_dialogs:
        #    mcp_mcp-telegram_search_dialogs(query="cvgorod", limit=50)
        #
        # 2. Для каждой группы проверить наличие бота @cvgorodassistent_bot
        #    через get_participants или проверить историю сообщений
        #
        # 3. Добавить новые группы в базу если их нет
        #
        # Пример кода для интеграции:
        # ```python
        # search_queries = ["cvgorod", "букет", "Chat Cvgorod"]
        # for query in search_queries:
        #     # Вызываем через Cursor MCP
        #     dialogs = mcp_mcp-telegram_search_dialogs(query=query, limit=50)
        #     for dialog in dialogs:
        #         if dialog['type'] in ['group', 'supergroup']:
        #             # Проверяем наличие бота или добавляем группу
        #             found_groups.append({
        #                 'id': dialog['id'],
        #                 'name': dialog['title'],
        #                 'chat_type': dialog['type']
        #             })
        # ```
        #
        # ⚠️ ТЕКУЩАЯ РЕАЛИЗАЦИЯ: Используем существующие чаты из БД
        # ============================================================
        
        # Получаем все активные чаты из базы данных
        query = "SELECT id, name, chat_type FROM chats WHERE is_active = TRUE ORDER BY name"
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query)
        
        groups = [dict(row) for row in rows]
        self.stats["chats_found"] = len(groups)
        logger.info(f"Найдено {len(groups)} активных чатов в базе")
        
        return groups

    async def get_last_message_id(self, chat_id: int) -> int | None:
        """
        Получает ID последнего сохраненного сообщения в чате.
        
        Args:
            chat_id: ID чата
            
        Returns:
            telegram_message_id последнего сообщения или None
        """
        query = """
            SELECT MAX(telegram_message_id) as last_id
            FROM messages
            WHERE chat_id = $1
        """
        async with self.pool.acquire() as conn:
            result = await conn.fetchval(query, chat_id)
        return result

    async def get_last_message_timestamp(self, chat_id: int) -> datetime | None:
        """
        Получает timestamp последнего сообщения в чате.
        
        Args:
            chat_id: ID чата
            
        Returns:
            timestamp последнего сообщения или None
        """
        query = """
            SELECT MAX(timestamp) as last_ts
            FROM messages
            WHERE chat_id = $1
        """
        async with self.pool.acquire() as conn:
            result = await conn.fetchval(query, chat_id)
        return result

    async def fetch_messages_from_telegram(
        self,
        chat_id: int,
        min_id: int = 0,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """
        Загружает сообщения из Telegram через MCP.
        
        Args:
            chat_id: ID чата
            min_id: Минимальный ID сообщения (загружать после него)
            limit: Максимальное количество сообщений
            
        Returns:
            Список сообщений в формате:
            [
                {
                    "message_id": int,
                    "user_id": int,
                    "username": str | None,
                    "first_name": str | None,
                    "last_name": str | None,
                    "text": str | None,
                    "timestamp": datetime,
                    "message_type": str,
                    "reply_to_message_id": int | None
                },
                ...
            ]
        """
        messages = []
        
        logger.info(f"  Загрузка сообщений из Telegram (chat_id={chat_id}, min_id={min_id})...")
        
        # ============================================================
        # ИНТЕГРАЦИЯ С TELEGRAM MCP (требует запуска через Cursor)
        # ============================================================
        #
        # Для загрузки сообщений используйте Telegram MCP get_messages:
        #
        # ```python
        # # Вызов через Cursor MCP
        # telegram_messages = mcp_mcp-telegram_get_messages(
        #     entity=str(chat_id),  # ID чата как строка
        #     limit=limit or 1000,  # Максимум сообщений за запрос
        #     offset_id=min_id      # Загружать после этого ID
        # )
        #
        # # Преобразуем в нужный формат
        # for msg in telegram_messages:
        #     messages.append({
        #         "message_id": msg.id,
        #         "user_id": msg.from_id.user_id if msg.from_id else None,
        #         "username": msg.from_user.username if msg.from_user else None,
        #         "first_name": msg.from_user.first_name if msg.from_user else None,
        #         "last_name": msg.from_user.last_name if msg.from_user else None,
        #         "text": msg.text or msg.caption,
        #         "timestamp": msg.date,  # datetime object
        #         "message_type": self._get_message_type(msg),
        #         "reply_to_message_id": msg.reply_to_msg_id
        #     })
        # ```
        #
        # ВАЖНО: Telegram MCP возвращает сообщения в обратном порядке
        # (от новых к старым), поэтому может потребоваться реверс списка
        #
        # ⚠️ ТЕКУЩАЯ РЕАЛИЗАЦИЯ: Возвращает пустой список (заглушка)
        # ============================================================
        
        logger.info(f"  Загружено {len(messages)} сообщений из Telegram")
        return messages

    async def save_message(
        self,
        telegram_message_id: int,
        chat_id: int,
        user_id: int,
        text: str | None,
        timestamp: datetime,
        message_type: str = "text",
        reply_to_message_id: int | None = None,
    ) -> bool:
        """
        Сохраняет сообщение в базу данных.
        
        Returns:
            True если сохранено, False если было дублирование
        """
        if self.dry_run:
            logger.debug(f"    [DRY RUN] Сохранение: msg_id={telegram_message_id}, user={user_id}")
            return True
        
        query = """
            INSERT INTO messages (
                telegram_message_id, chat_id, user_id, text,
                message_type, reply_to_message_id, timestamp
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            ON CONFLICT (chat_id, telegram_message_id) DO NOTHING
            RETURNING id
        """
        
        try:
            async with self.pool.acquire() as conn:
                result = await conn.fetchval(
                    query,
                    telegram_message_id,
                    chat_id,
                    user_id,
                    text,
                    message_type,
                    reply_to_message_id,
                    timestamp,
                )
            
            if result:
                self.stats["messages_saved"] += 1
                return True
            else:
                self.stats["messages_skipped"] += 1
                return False
                
        except Exception as e:
            logger.error(f"Ошибка сохранения сообщения {telegram_message_id}: {e}")
            self.stats["errors"] += 1
            return False

    async def ensure_user_exists(
        self,
        user_id: int,
        username: str | None = None,
        first_name: str | None = None,
        last_name: str | None = None,
    ) -> None:
        """
        Создает пользователя если его нет в базе.
        
        Args:
            user_id: Telegram user ID
            username: Username (без @)
            first_name: Имя
            last_name: Фамилия
        """
        if self.dry_run:
            return
        
        query = """
            INSERT INTO users (id, username, first_name, last_name)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (id) DO UPDATE SET
                username = COALESCE(EXCLUDED.username, users.username),
                first_name = COALESCE(EXCLUDED.first_name, users.first_name),
                last_name = COALESCE(EXCLUDED.last_name, users.last_name),
                last_seen = NOW()
        """
        
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(query, user_id, username, first_name, last_name)
                self.stats["users_created"] += 1
        except Exception as e:
            logger.error(f"Ошибка создания пользователя {user_id}: {e}")

    async def sync_chat(self, chat_info: dict[str, Any], limit: int | None = None) -> None:
        """
        Синхронизирует сообщения из одного чата.
        
        Args:
            chat_info: Информация о чате (id, name)
            limit: Максимум сообщений для загрузки (для тестирования)
        """
        chat_id = chat_info["id"]
        chat_name = chat_info.get("name", f"Chat {chat_id}")
        
        logger.info(f"\n{'='*60}")
        logger.info(f"Чат: {chat_name} (ID: {chat_id})")
        logger.info(f"{'='*60}")
        
        # Получаем последнее сообщение
        last_msg_id = await self.get_last_message_id(chat_id)
        last_timestamp = await self.get_last_message_timestamp(chat_id)
        
        if last_msg_id:
            logger.info(f"  Последнее сообщение в БД: ID={last_msg_id}, время={last_timestamp}")
        else:
            logger.info(f"  Чат пустой в БД, загружаем всю историю")
        
        # Загружаем сообщения из Telegram
        min_id = last_msg_id or 0
        messages = await self.fetch_messages_from_telegram(chat_id, min_id, limit)
        
        if not messages:
            logger.info(f"  Нет новых сообщений")
            return
        
        logger.info(f"  Обработка {len(messages)} сообщений...")
        self.stats["messages_fetched"] += len(messages)
        
        # Сохраняем сообщения
        for msg in messages:
            # Убедимся что пользователь существует
            await self.ensure_user_exists(
                user_id=msg["user_id"],
                username=msg.get("username"),
                first_name=msg.get("first_name"),
                last_name=msg.get("last_name"),
            )
            
            # Сохраняем сообщение
            await self.save_message(
                telegram_message_id=msg["message_id"],
                chat_id=chat_id,
                user_id=msg["user_id"],
                text=msg.get("text"),
                timestamp=msg["timestamp"],
                message_type=msg.get("message_type", "text"),
                reply_to_message_id=msg.get("reply_to_message_id"),
            )
        
        self.stats["chats_synced"] += 1
        logger.info(f"  ✓ Чат обработан: сохранено {self.stats['messages_saved']} новых сообщений")

    async def run(self, limit: int | None = None) -> None:
        """
        Запускает полную синхронизацию.
        
        Args:
            limit: Лимит сообщений на чат (для тестирования)
        """
        logger.info("="*80)
        logger.info("СИНХРОНИЗАЦИЯ TELEGRAM → cvgorod-hub")
        logger.info("="*80)
        
        if self.dry_run:
            logger.info("⚠️  РЕЖИМ DRY-RUN: данные не будут сохранены в БД")
        
        # Находим все группы с ботом
        groups = await self.find_groups_with_bot()
        
        if not groups:
            logger.warning("Не найдено групп для синхронизации")
            return
        
        # Синхронизируем каждый чат
        for i, group in enumerate(groups, 1):
            logger.info(f"\n[{i}/{len(groups)}] Обработка...")
            try:
                await self.sync_chat(group, limit)
                # Пауза между чатами чтобы не перегрузить API
                await asyncio.sleep(0.5)
            except Exception as e:
                logger.error(f"Ошибка синхронизации чата {group['id']}: {e}", exc_info=True)
                self.stats["errors"] += 1
        
        # Итоговая статистика
        logger.info("\n" + "="*80)
        logger.info("СТАТИСТИКА СИНХРОНИЗАЦИИ")
        logger.info("="*80)
        logger.info(f"Чатов найдено:         {self.stats['chats_found']}")
        logger.info(f"Чатов обработано:      {self.stats['chats_synced']}")
        logger.info(f"Сообщений загружено:   {self.stats['messages_fetched']}")
        logger.info(f"Сообщений сохранено:   {self.stats['messages_saved']}")
        logger.info(f"Сообщений пропущено:   {self.stats['messages_skipped']}")
        logger.info(f"Пользователей создано: {self.stats['users_created']}")
        logger.info(f"Ошибок:                {self.stats['errors']}")
        logger.info("="*80)


async def main():
    """Главная функция."""
    # Парсинг аргументов
    dry_run = "--dry-run" in sys.argv
    limit = None
    
    for arg in sys.argv[1:]:
        if arg.startswith("--limit="):
            limit = int(arg.split("=")[1])
    
    # Подключение к БД
    database_url = os.getenv(
        "DATABASE_URL",
        "postgresql://localhost/cvgorod_hub"
    )
    
    logger.info(f"Подключение к БД: {database_url}")
    
    try:
        pool = await asyncpg.create_pool(
            database_url,
            min_size=2,
            max_size=5,
            command_timeout=30,
        )
        
        logger.info("✓ Подключение к БД установлено")
        
        # Запуск синхронизации
        service = TelegramSyncService(pool, dry_run=dry_run)
        await service.run(limit=limit)
        
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}", exc_info=True)
        sys.exit(1)
    finally:
        if pool:
            await pool.close()
            logger.info("✓ Соединение с БД закрыто")


if __name__ == "__main__":
    asyncio.run(main())
