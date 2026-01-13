"""
Async PostgreSQL клиент для CVGorod Message Collector.

Предоставляет асинхронное подключение к PostgreSQL с connection pooling
и удобные методы для работы с сообщениями, чатами и пользователями.
"""

import os
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
from contextlib import asynccontextmanager
from pathlib import Path

import asyncpg
from asyncpg import Pool
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

# Автоматически загружаем .env.local для локальной разработки
def _load_env_local():
    """Загружает переменные окружения из .env.local если существует."""
    env_local = Path(__file__).parent.parent / ".env.local"
    if env_local.exists() and "DATABASE_URL" not in os.environ:
        with open(env_local) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, value = line.partition("=")
                    os.environ.setdefault(key.strip(), value.strip())

_load_env_local()

logger = logging.getLogger(__name__)


class Database:
    """Async PostgreSQL клиент с connection pooling."""

    _instance: Optional["Database"] = None
    _pool: Optional[Pool] = None

    def __new__(cls) -> "Database":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    async def connect(self) -> None:
        """Устанавливает соединение с базой данных с retry логикой."""
        if self._pool is not None:
            return

        # Локально: postgresql://localhost/cvgorod_messages
        # Docker: postgresql://cvgorod:cvgorod_secret_2024@postgres:5432/cvgorod_messages
        database_url = os.getenv(
            "DATABASE_URL",
            "postgresql://localhost/cvgorod_messages"
        )

        try:
            self._pool = await self._connect_with_retry(database_url)
            logger.info("Connected to PostgreSQL database")
        except Exception as e:
            logger.error(f"Failed to connect to PostgreSQL after retries: {e}")
            raise

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(min=2, max=30),
        retry=retry_if_exception_type((asyncpg.PostgresConnectionError, OSError, TimeoutError)),
        reraise=True
    )
    async def _connect_with_retry(self, database_url: str) -> Pool:
        """Подключение с retry при временных сбоях."""
        return await asyncpg.create_pool(
            database_url,
            min_size=5,
            max_size=20,
            command_timeout=30,
        )

    async def close(self) -> None:
        """Закрывает соединение с базой данных."""
        if self._pool:
            await self._pool.close()
            self._pool = None
            logger.info("PostgreSQL connection closed")

    @property
    def pool(self) -> Pool:
        """Возвращает пул соединений."""
        if self._pool is None:
            raise RuntimeError("Database not connected. Call connect() first.")
        return self._pool

    @asynccontextmanager
    async def acquire(self):
        """Контекстный менеджер для получения соединения из пула."""
        async with self.pool.acquire() as conn:
            yield conn

    # ========== ПРЯМЫЕ МЕТОДЫ ЗАПРОСОВ ==========

    async def fetch(self, query: str, *args) -> List[Any]:
        """Выполняет запрос и возвращает все строки."""
        async with self.acquire() as conn:
            return await conn.fetch(query, *args)

    async def fetchval(self, query: str, *args) -> Any:
        """Выполняет запрос и возвращает одно значение."""
        async with self.acquire() as conn:
            return await conn.fetchval(query, *args)

    async def fetchrow(self, query: str, *args) -> Any:
        """Выполняет запрос и возвращает одну строку."""
        async with self.acquire() as conn:
            return await conn.fetchrow(query, *args)

    async def execute(self, query: str, *args) -> str:
        """Выполняет запрос без возврата данных."""
        async with self.acquire() as conn:
            return await conn.execute(query, *args)

    # ========== ЧАТЫ ==========

    async def get_or_create_chat(
        self,
        chat_id: int,
        chat_name: Optional[str] = None,
        chat_type: str = "group",
        folder: Optional[str] = None,
    ) -> int:
        """Получает или создаёт чат. Возвращает chat_id."""
        query = """
            INSERT INTO chats (id, name, chat_type, folder)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (id) DO UPDATE SET
                name = COALESCE(EXCLUDED.name, chats.name),
                chat_type = COALESCE(EXCLUDED.chat_type, chats.chat_type),
                folder = COALESCE(EXCLUDED.folder, chats.folder),
                updated_at = NOW()
            RETURNING id
        """
        async with self.acquire() as conn:
            result = await conn.fetchval(query, chat_id, chat_name, chat_type, folder)
        return result

    async def update_chat_info(
        self,
        chat_id: int,
        members_count: Optional[int] = None,
        name: Optional[str] = None,
    ) -> None:
        """Обновляет информацию о чате."""
        query = """
            UPDATE chats SET
                members_count = COALESCE($2, members_count),
                name = COALESCE($3, name),
                updated_at = NOW()
            WHERE id = $1
        """
        async with self.acquire() as conn:
            await conn.execute(query, chat_id, members_count, name)

    async def get_chat(self, chat_id: int) -> Optional[Dict[str, Any]]:
        """Возвращает информацию о чате."""
        query = "SELECT * FROM chats WHERE id = $1"
        async with self.acquire() as conn:
            row = await conn.fetchrow(query, chat_id)
        return dict(row) if row else None

    async def get_all_chats(self, active_only: bool = True) -> List[Dict[str, Any]]:
        """Возвращает список всех чатов."""
        query = "SELECT * FROM chats"
        if active_only:
            query += " WHERE is_active = TRUE"
        query += " ORDER BY updated_at DESC"

        async with self.acquire() as conn:
            rows = await conn.fetch(query)
        return [dict(row) for row in rows]

    # ========== ПОЛЬЗОВАТЕЛИ ==========

    async def get_or_create_user(
        self,
        user_id: int,
        username: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        is_manager: bool = False,
    ) -> int:
        """Получает или создаёт пользователя. Возвращает user_id."""
        query = """
            INSERT INTO users (id, username, first_name, last_name, is_manager)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (id) DO UPDATE SET
                username = COALESCE(EXCLUDED.username, users.username),
                first_name = COALESCE(EXCLUDED.first_name, users.first_name),
                last_name = COALESCE(EXCLUDED.last_name, users.last_name),
                is_manager = users.is_manager OR EXCLUDED.is_manager,
                last_seen = NOW()
            RETURNING id
        """
        async with self.acquire() as conn:
            result = await conn.fetchval(
                query, user_id, username, first_name, last_name, is_manager
            )
        return result

    async def update_user_seen(self, user_id: int) -> None:
        """Обновляет время последнего seen пользователя."""
        query = "UPDATE users SET last_seen = NOW() WHERE id = $1"
        async with self.acquire() as conn:
            await conn.execute(query, user_id)

    async def get_user(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Возвращает информацию о пользователе."""
        query = "SELECT * FROM users WHERE id = $1"
        async with self.acquire() as conn:
            row = await conn.fetchrow(query, user_id)
        return dict(row) if row else None

    async def get_all_managers(self) -> List[Dict[str, Any]]:
        """Возвращает список всех менеджеров."""
        query = "SELECT * FROM users WHERE is_manager = TRUE ORDER BY first_seen"
        async with self.acquire() as conn:
            rows = await conn.fetch(query)
        return [dict(row) for row in rows]

    # ========== РОЛИ И ПАТТЕРНЫ ==========

    async def get_user_role(self, user_id: int) -> Optional[Dict[str, Any]]:
        """
        Возвращает информацию о роли пользователя.

        Args:
            user_id: ID пользователя

        Returns:
            Словарь с информацией о роли или None
        """
        query = """
            SELECT
                ur.id, ur.role_name, ur.display_name, ur.description,
                ur.is_staff, ur.is_bot, ur.exclude_from_analytics
            FROM users u
            JOIN user_roles ur ON u.role_id = ur.id
            WHERE u.id = $1
        """
        async with self.acquire() as conn:
            row = await conn.fetchrow(query, user_id)
        return dict(row) if row else None

    async def get_all_staff_ids(self) -> List[int]:
        """
        Возвращает ID всех сотрудников (админ + директора + менеджеры).

        Returns:
            Список user_id сотрудников
        """
        query = """
            SELECT DISTINCT u.id
            FROM users u
            JOIN user_roles ur ON u.role_id = ur.id
            WHERE ur.is_staff = TRUE
        """
        async with self.acquire() as conn:
            rows = await conn.fetch(query)
        return [row["id"] for row in rows]

    async def get_all_bot_ids(self) -> List[int]:
        """
        Возвращает ID всех ботов.

        Returns:
            Список user_id ботов
        """
        query = """
            SELECT DISTINCT u.id
            FROM users u
            JOIN user_roles ur ON u.role_id = ur.id
            WHERE ur.is_bot = TRUE
        """
        async with self.acquire() as conn:
            rows = await conn.fetch(query)
        return [row["id"] for row in rows]

    async def get_all_non_client_ids(self) -> List[int]:
        """
        Возвращает ID всех НЕ-клиентов (сотрудники + боты).

        Returns:
            Список user_id не-клиентов
        """
        query = """
            SELECT DISTINCT u.id
            FROM users u
            JOIN user_roles ur ON u.role_id = ur.id
            WHERE ur.exclude_from_analytics = TRUE
        """
        async with self.acquire() as conn:
            rows = await conn.fetch(query)
        return [row["id"] for row in rows]

    async def get_patterns_by_type(self, pattern_type: str) -> List[Dict[str, Any]]:
        """
        Возвращает паттерны сообщений по типу.

        Args:
            pattern_type: Тип паттерна (broadcast, question, order, complaint, confirmation)

        Returns:
            Список словарей с информацией о паттернах
        """
        query = """
            SELECT
                id, pattern_name, pattern_type, keyword_patterns,
                regex_pattern, sender_role_id, min_text_length,
                auto_classify, priority, description
            FROM message_patterns
            WHERE pattern_type = $1 AND auto_classify = TRUE
            ORDER BY priority ASC
        """
        async with self.acquire() as conn:
            rows = await conn.fetch(query, pattern_type)
        return [dict(row) for row in rows]

    async def classify_message(self, text: str, user_id: int) -> Optional[int]:
        """
        Классифицирует сообщение по тексту и роли отправителя.

        Args:
            text: Текст сообщения
            user_id: ID отправителя

        Returns:
            ID паттерна или None если не классифицировано
        """
        async with self.acquire() as conn:
            return await conn.fetchval("SELECT classify_message($1, $2)", text, user_id)

    # ========== СООБЩЕНИЯ ==========

    async def save_message(
        self,
        telegram_message_id: int,
        chat_id: int,
        user_id: int,
        text: str,
        message_type: str = "text",
        reply_to_message_id: Optional[int] = None,
        timestamp: Optional[datetime] = None,
    ) -> int:
        """Сохраняет сообщение в базу данных. Возвращает id записи."""
        if timestamp is None:
            timestamp = datetime.utcnow()
        elif timestamp.tzinfo is not None:
            # БД использует timestamp without time zone, убираем tzinfo
            # Но сначала конвертируем в UTC
            from datetime import timezone as tz
            timestamp = timestamp.astimezone(tz.utc).replace(tzinfo=None)

        query = """
            INSERT INTO messages (
                telegram_message_id, chat_id, user_id, text,
                message_type, reply_to_message_id, timestamp
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            RETURNING id
        """
        async with self.acquire() as conn:
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
        return result

    async def get_messages(
        self,
        chat_id: Optional[int] = None,
        user_id: Optional[int] = None,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        limit: int = 1000,
        offset: int = 0,
        clients_only: bool = False,
    ) -> List[Dict[str, Any]]:
        """Возвращает список сообщений с фильтрами.
        
        Args:
            clients_only: Если True, исключает сообщения ботов и сотрудников.
        """
        conditions = []
        params = []
        param_idx = 1

        if chat_id is not None:
            conditions.append(f"m.chat_id = ${param_idx}")
            params.append(chat_id)
            param_idx += 1

        if user_id is not None:
            conditions.append(f"m.user_id = ${param_idx}")
            params.append(user_id)
            param_idx += 1

        if since is not None:
            # БД использует timestamp without time zone, нужен naive datetime
            if since.tzinfo is not None:
                since = since.replace(tzinfo=None)
            conditions.append(f"m.timestamp >= ${param_idx}")
            params.append(since)
            param_idx += 1

        if until is not None:
            # БД использует timestamp without time zone, нужен naive datetime
            if until.tzinfo is not None:
                until = until.replace(tzinfo=None)
            conditions.append(f"m.timestamp <= ${param_idx}")
            params.append(until)
            param_idx += 1
        
        # Исключаем ботов и сотрудников на уровне SQL
        if clients_only:
            from config.roles import get_all_non_client_ids
            exclude_ids = list(get_all_non_client_ids())
            if exclude_ids:
                placeholders = ", ".join(f"${param_idx + i}" for i in range(len(exclude_ids)))
                conditions.append(f"m.user_id NOT IN ({placeholders})")
                params.extend(exclude_ids)
                param_idx += len(exclude_ids)

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        query = f"""
            SELECT
                m.*,
                u.username,
                u.first_name,
                c.name as chat_name
            FROM messages m
            LEFT JOIN users u ON m.user_id = u.id
            LEFT JOIN chats c ON m.chat_id = c.id
            WHERE {where_clause}
            ORDER BY m.timestamp DESC
            LIMIT ${param_idx} OFFSET ${param_idx + 1}
        """
        params.extend([limit, offset])

        async with self.acquire() as conn:
            rows = await conn.fetch(query, *params)
        return [dict(row) for row in rows]

    async def search_messages(
        self,
        query: str,
        chat_id: Optional[int] = None,
        since: Optional[datetime] = None,
        limit: int = 100,
        exclude_user_ids: Optional[List[int]] = None,
        clients_only: bool = False,
    ) -> List[Dict[str, Any]]:
        """Поиск сообщений по тексту (full-text search для русского).
        
        Если query пустой или '*', возвращает ВСЕ сообщения за период.
        
        Args:
            query: Поисковый запрос
            chat_id: ID чата для фильтрации
            since: Дата начала поиска
            limit: Максимум результатов
            exclude_user_ids: ID пользователей для исключения (боты, сотрудники)
            clients_only: Если True, автоматически исключает ботов и сотрудников
        """
        conditions = []
        params = []
        param_idx = 1
        use_fts = bool(query and query.strip() and query.strip() != "*")
        
        if use_fts:
            # Формируем поисковую строку для tsquery
            # Используем OR (|) вместо AND (&) чтобы найти сообщения с ЛЮБЫМ из слов
            search_terms = " | ".join(query.split())
            search_query = f"to_tsquery('russian', '{search_terms}')"
            conditions.append(f"to_tsvector('russian', COALESCE(m.text, '')) @@ {search_query}")

        if chat_id is not None:
            conditions.append(f"m.chat_id = ${param_idx}")
            params.append(chat_id)
            param_idx += 1

        if since is not None:
            conditions.append(f"m.timestamp >= ${param_idx}")
            params.append(since)
            param_idx += 1
        
        # Исключаем ботов и сотрудников НА УРОВНЕ SQL (эффективнее!)
        if clients_only:
            from config.roles import get_all_non_client_ids
            exclude_user_ids = list(get_all_non_client_ids())
        
        if exclude_user_ids:
            # NOT IN для исключения ботов/сотрудников
            placeholders = ", ".join(f"${param_idx + i}" for i in range(len(exclude_user_ids)))
            conditions.append(f"m.user_id NOT IN ({placeholders})")
            params.extend(exclude_user_ids)
            param_idx += len(exclude_user_ids)
        
        # Только непустые сообщения
        conditions.append("m.text IS NOT NULL AND m.text != ''")

        where_clause = " AND ".join(conditions) if conditions else "1=1"
        
        # Выбираем формат выборки в зависимости от использования FTS
        if use_fts:
            sql = f"""
                SELECT
                    m.*,
                    u.username,
                    u.first_name,
                    c.name as chat_name,
                    ts_headline(
                        'russian',
                        m.text,
                        {search_query},
                        'StartSel=<b>, StopSel=</b>, MaxWords=50, MinWords=10'
                    ) as text_highlight
                FROM messages m
                LEFT JOIN users u ON m.user_id = u.id
                LEFT JOIN chats c ON m.chat_id = c.id
                WHERE {where_clause}
                ORDER BY m.timestamp DESC
                LIMIT ${param_idx}
            """
        else:
            # Без FTS — просто возвращаем все сообщения
            sql = f"""
                SELECT
                    m.*,
                    u.username,
                    u.first_name,
                    c.name as chat_name,
                    m.text as text_highlight
                FROM messages m
                LEFT JOIN users u ON m.user_id = u.id
                LEFT JOIN chats c ON m.chat_id = c.id
                WHERE {where_clause}
                ORDER BY m.timestamp DESC
                LIMIT ${param_idx}
            """
        params.append(limit)

        async with self.acquire() as conn:
            rows = await conn.fetch(sql, *params)
        return [dict(row) for row in rows]

    async def get_message_count(
        self,
        chat_id: Optional[int] = None,
        since: Optional[datetime] = None,
    ) -> int:
        """Возвращает количество сообщений."""
        conditions = []
        params = []
        param_idx = 1

        if chat_id is not None:
            conditions.append(f"chat_id = ${param_idx}")
            params.append(chat_id)
            param_idx += 1

        if since is not None:
            conditions.append(f"timestamp >= ${param_idx}")
            params.append(since)
            param_idx += 1

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        query = f"SELECT COUNT(*) FROM messages WHERE {where_clause}"
        async with self.acquire() as conn:
            result = await conn.fetchval(query, *params)
        return result

    async def get_chat_context(
        self,
        chat_id: int,
        limit: int = 500,
    ) -> str:
        """
        Возвращает контекст переписки для чата в формате строки.
        Используется для передачи в DeepSeek.
        """
        messages = await self.get_messages(chat_id=chat_id, limit=limit)

        context_lines = []
        for msg in messages:
            user_name = msg.get("username") or msg.get("first_name") or "Unknown"
            ts = msg.get("timestamp")
            ts_str = ts.strftime("%Y-%m-%d %H:%M") if ts else ""
            text = (msg.get("text") or "")[:200]  # Ограничиваем длину

            if text:
                context_lines.append(f"[{ts_str}] {user_name}: {text}")

        return "\n".join(reversed(context_lines))

    async def get_all_context(
        self,
        since: Optional[datetime] = None,
        limit_per_chat: int = 50,
    ) -> str:
        """
        Возвращает контекст ВСЕХ чатов для анализа.
        Используется для передачи в DeepSeek.
        """
        chats = await self.get_all_chats(active_only=True)

        context_parts = []
        for chat in chats:
            chat_id = chat["id"]
            chat_name = chat["name"] or f"Chat {chat_id}"

            messages = await self.get_messages(
                chat_id=chat_id,
                since=since,
                limit=limit_per_chat,
            )

            if messages:
                context_parts.append(f"=== {chat_name} ===")
                for msg in messages:
                    user_name = msg.get("username") or msg.get("first_name") or "Unknown"
                    ts = msg.get("timestamp")
                    ts_str = ts.strftime("%m-%d %H:%M") if ts else ""
                    text = (msg.get("text") or "")[:150]

                    if text:
                        context_parts.append(f"[{ts_str}] {user_name}: {text}")

        return "\n".join(context_parts)


# Глобальный экземпляр
db = Database()
