"""
Role Repository - работа с ролями пользователей в PostgreSQL.

Предоставляет async методы для:
- Получения роли пользователя по ID
- Получения всех ID сотрудников/ботов
- Проверки является ли пользователь сотрудником/клиентом
- Получения паттернов сообщений

Фоллбек на статический конфиг из config/roles.py если БД недоступна.
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Set, List, Dict, Any

from services.database import db

logger = logging.getLogger(__name__)


class UserRole(str, Enum):
    """Роли пользователей в системе."""
    ADMIN = "admin"
    DIRECTOR = "director"
    MANAGER = "manager"
    BROADCAST_BOT = "broadcast_bot"
    ASSISTANT_BOT = "assistant_bot"
    CLIENT = "client"


@dataclass
class RoleInfo:
    """Информация о роли."""
    id: int
    role_name: str
    display_name: str
    description: Optional[str]
    is_staff: bool
    is_bot: bool
    exclude_from_analytics: bool


class RoleRepository:
    """
    Репозиторий для работы с ролями пользователей.

    Использует PostgreSQL как основной источник данных,
    с fallback на статический конфиг из config/roles.py.
    """

    # Кэш для статического конфига (fallback)
    _static_role_cache: Optional[Dict[int, RoleInfo]] = None

    def __init__(self):
        self._db_initialized = False

    async def _ensure_db(self) -> bool:
        """Проверяет доступность БД."""
        if self._db_initialized:
            return True
        try:
            if db.pool is None:
                await db.connect()
            self._db_initialized = True
            return True
        except Exception as e:
            logger.warning(f"Database not available, using static config: {e}")
            self._db_initialized = False
            return False

    def _get_static_role_info(self, user_id: int) -> Optional[RoleInfo]:
        """
        Возвращает информацию о роли из статического конфига.

        Используется как fallback если БД недоступна.
        """
        from config.roles import (
            ADMIN, DIRECTORS, MANAGERS, BOTS, get_all_staff_ids, get_all_bot_ids
        )

        # Админ
        if user_id == ADMIN.user_id:
            return RoleInfo(
                id=1,
                role_name=UserRole.ADMIN.value,
                display_name="Администратор",
                description="Администратор системы",
                is_staff=True,
                is_bot=False,
                exclude_from_analytics=True
            )

        # Директора
        for director in DIRECTORS:
            if user_id == director.user_id:
                return RoleInfo(
                    id=2,
                    role_name=UserRole.DIRECTOR.value,
                    display_name="Директор",
                    description="Директор по продажам",
                    is_staff=True,
                    is_bot=False,
                    exclude_from_analytics=True
                )

        # Менеджеры
        for manager in MANAGERS:
            if user_id == manager.user_id:
                return RoleInfo(
                    id=3,
                    role_name=UserRole.MANAGER.value,
                    display_name="Менеджер",
                    description="Менеджер по продажам",
                    is_staff=True,
                    is_bot=False,
                    exclude_from_analytics=True
                )

        # Боты
        for bot in BOTS:
            if user_id == bot.user_id:
                if "assistent" in (bot.username or "").lower():
                    return RoleInfo(
                        id=5,
                        role_name=UserRole.ASSISTANT_BOT.value,
                        display_name="AI Ассистент",
                        description="AI-ассистент для ответов",
                        is_staff=False,
                        is_bot=True,
                        exclude_from_analytics=True
                    )
                return RoleInfo(
                    id=4,
                    role_name=UserRole.BROADCAST_BOT.value,
                    display_name="Бот рассылки",
                    description="Бот для автоматических рассылок",
                    is_staff=False,
                    is_bot=True,
                    exclude_from_analytics=True
                )

        return None

    async def get_user_role(self, user_id: int) -> RoleInfo:
        """
        Возвращает информацию о роли пользователя.

        Сначала пытается получить из БД, затем fallback на статический конфиг.

        Args:
            user_id: ID пользователя в Telegram

        Returns:
            RoleInfo с информацией о роли
        """
        # Пробуем из БД
        if await self._ensure_db():
            try:
                query = """
                    SELECT 
                        ur.id, ur.role_name, ur.display_name, ur.description,
                        ur.is_staff, ur.is_bot, ur.exclude_from_analytics
                    FROM users u
                    JOIN user_roles ur ON u.role_id = ur.id
                    WHERE u.id = $1
                """
                row = await db.fetchrow(query, user_id)
                if row:
                    return RoleInfo(
                        id=row["id"],
                        role_name=row["role_name"],
                        display_name=row["display_name"],
                        description=row["description"],
                        is_staff=row["is_staff"],
                        is_bot=row["is_bot"],
                        exclude_from_analytics=row["exclude_from_analytics"]
                    )
            except Exception as e:
                logger.warning(f"Failed to get role from DB: {e}")

        # Fallback на статический конфиг
        static_role = self._get_static_role_info(user_id)
        if static_role:
            return static_role

        # По умолчанию - клиент
        return RoleInfo(
            id=6,
            role_name=UserRole.CLIENT.value,
            display_name="Клиент",
            description="Клиент компании",
            is_staff=False,
            is_bot=False,
            exclude_from_analytics=False
        )

    async def get_role_by_id(self, role_id: int) -> Optional[RoleInfo]:
        """
        Возвращает информацию о роли по ID.

        Args:
            role_id: ID роли в таблице user_roles

        Returns:
            RoleInfo или None если не найдено
        """
        if await self._ensure_db():
            try:
                query = """
                    SELECT 
                        id, role_name, display_name, description,
                        is_staff, is_bot, exclude_from_analytics
                    FROM user_roles
                    WHERE id = $1
                """
                row = await db.fetchrow(query, role_id)
                if row:
                    return RoleInfo(
                        id=row["id"],
                        role_name=row["role_name"],
                        display_name=row["display_name"],
                        description=row["description"],
                        is_staff=row["is_staff"],
                        is_bot=row["is_bot"],
                        exclude_from_analytics=row["exclude_from_analytics"]
                    )
            except Exception as e:
                logger.warning(f"Failed to get role by ID from DB: {e}")

        return None

    async def get_all_staff_ids(self) -> Set[int]:
        """
        Возвращает множество ID всех сотрудников (админ + директора + менеджеры).

        Returns:
            Множество user_id сотрудников
        """
        staff_ids: Set[int] = set()

        # Пробуем из БД
        if await self._ensure_db():
            try:
                query = """
                    SELECT DISTINCT u.id
                    FROM users u
                    JOIN user_roles ur ON u.role_id = ur.id
                    WHERE ur.is_staff = TRUE
                """
                rows = await db.fetch(query)
                staff_ids = {row["id"] for row in rows}
                logger.info(f"Loaded {len(staff_ids)} staff IDs from database")
                return staff_ids
            except Exception as e:
                logger.warning(f"Failed to get staff IDs from DB: {e}")

        # Fallback на статический конфиг
        from config.roles import get_all_staff_ids
        staff_ids = get_all_staff_ids()
        logger.info(f"Using {len(staff_ids)} staff IDs from static config")
        return staff_ids

    async def get_all_bot_ids(self) -> Set[int]:
        """
        Возвращает множество ID всех ботов.

        Returns:
            Множество user_id ботов
        """
        bot_ids: Set[int] = set()

        # Пробуем из БД
        if await self._ensure_db():
            try:
                query = """
                    SELECT DISTINCT u.id
                    FROM users u
                    JOIN user_roles ur ON u.role_id = ur.id
                    WHERE ur.is_bot = TRUE
                """
                rows = await db.fetch(query)
                bot_ids = {row["id"] for row in rows}
                logger.info(f"Loaded {len(bot_ids)} bot IDs from database")
                return bot_ids
            except Exception as e:
                logger.warning(f"Failed to get bot IDs from DB: {e}")

        # Fallback на статический конфиг
        from config.roles import get_all_bot_ids
        bot_ids = get_all_bot_ids()
        logger.info(f"Using {len(bot_ids)} bot IDs from static config")
        return bot_ids

    async def get_all_non_client_ids(self) -> Set[int]:
        """
        Возвращает множество ID всех НЕ-клиентов (сотрудники + боты).

        Returns:
            Множество user_id не-клиентов
        """
        non_client_ids: Set[int] = set()

        # Пробуем из БД
        if await self._ensure_db():
            try:
                query = """
                    SELECT DISTINCT u.id
                    FROM users u
                    JOIN user_roles ur ON u.role_id = ur.id
                    WHERE ur.exclude_from_analytics = TRUE
                """
                rows = await db.fetch(query)
                non_client_ids = {row["id"] for row in rows}
                logger.info(f"Loaded {len(non_client_ids)} non-client IDs from database")
                return non_client_ids
            except Exception as e:
                logger.warning(f"Failed to get non-client IDs from DB: {e}")

        # Fallback на статический конфиг
        from config.roles import get_all_non_client_ids
        non_client_ids = get_all_non_client_ids()
        logger.info(f"Using {len(non_client_ids)} non-client IDs from static config")
        return non_client_ids

    async def is_staff(self, user_id: int) -> bool:
        """
        Проверяет, является ли пользователь сотрудником.

        Args:
            user_id: ID пользователя

        Returns:
            True если сотрудник, False иначе
        """
        role = await self.get_user_role(user_id)
        return role.is_staff

    async def is_bot(self, user_id: int) -> bool:
        """
        Проверяет, является ли пользователь ботом.

        Args:
            user_id: ID пользователя

        Returns:
            True если бот, False иначе
        """
        role = await self.get_user_role(user_id)
        return role.is_bot

    async def is_client(self, user_id: int) -> bool:
        """
        Проверяет, является ли пользователь клиентом.

        Args:
            user_id: ID пользователя

        Returns:
            True если клиент, False иначе
        """
        role = await self.get_user_role(user_id)
        return not role.is_staff and not role.is_bot

    async def get_patterns_by_type(self, pattern_type: str) -> List[Dict[str, Any]]:
        """
        Возвращает паттерны сообщений по типу.

        Args:
            pattern_type: Тип паттерна (broadcast, question, order, complaint, confirmation)

        Returns:
            Список словарей с информацией о паттернах
        """
        if await self._ensure_db():
            try:
                query = """
                    SELECT 
                        id, pattern_name, pattern_type, keyword_patterns,
                        regex_pattern, sender_role_id, min_text_length,
                        auto_classify, priority, description
                    FROM message_patterns
                    WHERE pattern_type = $1 AND auto_classify = TRUE
                    ORDER BY priority ASC
                """
                rows = await db.fetch(query, pattern_type)
                return [dict(row) for row in rows]
            except Exception as e:
                logger.warning(f"Failed to get patterns from DB: {e}")

        return []

    async def classify_message(self, text: str, user_id: int) -> Optional[int]:
        """
        Классифицирует сообщение по тексту и роли отправителя.

        Args:
            text: Текст сообщения
            user_id: ID отправителя

        Returns:
            ID паттерна или None если не классифицировано
        """
        if await self._ensure_db():
            try:
                return await db.fetchval(
                    "SELECT classify_message($1, $2)",
                    text, user_id
                )
            except Exception as e:
                logger.warning(f"Failed to classify message: {e}")

        return None

    async def get_role_id_by_name(self, role_name: str) -> Optional[int]:
        """
        Возвращает ID роли по имени.

        Args:
            role_name: Имя роли (admin, director, manager, etc.)

        Returns:
            ID роли или None
        """
        if await self._ensure_db():
            try:
                return await db.fetchval(
                    "SELECT id FROM user_roles WHERE role_name = $1",
                    role_name
                )
            except Exception as e:
                logger.warning(f"Failed to get role ID by name: {e}")

        # Fallback mapping
        role_mapping = {
            "admin": 1,
            "director": 2,
            "manager": 3,
            "broadcast_bot": 4,
            "assistant_bot": 5,
            "client": 6
        }
        return role_mapping.get(role_name)


# Глобальный экземпляр
role_repository = RoleRepository()


# Удобные функции для использования в других модулях
async def get_user_role(user_id: int) -> RoleInfo:
    """Возвращает информацию о роли пользователя."""
    return await role_repository.get_user_role(user_id)


async def get_all_staff_ids() -> Set[int]:
    """Возвращает ID всех сотрудников."""
    return await role_repository.get_all_staff_ids()


async def get_all_bot_ids() -> Set[int]:
    """Возвращает ID всех ботов."""
    return await role_repository.get_all_bot_ids()


async def get_all_non_client_ids() -> Set[int]:
    """Возвращает ID всех не-клиентов."""
    return await role_repository.get_all_non_client_ids()


async def is_staff(user_id: int) -> bool:
    """Проверяет является ли пользователь сотрудником."""
    return await role_repository.is_staff(user_id)


async def is_bot(user_id: int) -> bool:
    """Проверяет является ли пользователь ботом."""
    return await role_repository.is_bot(user_id)


async def is_client(user_id: int) -> bool:
    """Проверяет является ли пользователь клиентом."""
    return await role_repository.is_client(user_id)
