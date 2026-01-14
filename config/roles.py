"""
Конфигурация ролей пользователей.

Роли:
- admin: Администратор (получает копии диалогов директора)
- director: Директор (имеет полный доступ к аналитике)
- manager: Менеджер (сотрудник компании)
- bot: Бот рассылки (автоматические сообщения)
- client: Клиент (по умолчанию)
"""

from typing import Set, Optional, List
from dataclasses import dataclass
from enum import Enum


class UserRole(str, Enum):
    """Роли пользователей в системе."""
    ADMIN = "admin"       # Администратор — получает копии диалогов директора
    DIRECTOR = "director"
    MANAGER = "manager"
    BOT = "bot"
    CLIENT = "client"


@dataclass
class UserInfo:
    """Информация о пользователе с ролью."""
    user_id: int
    username: Optional[str]
    phone: Optional[str]
    role: UserRole
    name: Optional[str] = None


# ==================== КОНФИГУРАЦИЯ РОЛЕЙ ====================

# Администратор (получает копии диалогов директора)
ADMIN: UserInfo = UserInfo(
    user_id=6220049362,  # @badygovd
    username="badygovd",
    phone=None,
    role=UserRole.ADMIN,
    name="Даниил (Админ)"
)

# Директора (могут работать с ботом, их диалоги пересылаются админу)
DIRECTORS: List[UserInfo] = [
    UserInfo(
        user_id=5499578931,
        username="Djafar8554",
        phone=None,
        role=UserRole.DIRECTOR,
        name="Джафар"
    ),
    UserInfo(
        user_id=5553511218,
        username="aatlant86",
        phone="+77711761852",
        role=UserRole.DIRECTOR,
        name="Атлант (тестовый директор)"
    ),
]

# Обратная совместимость
DIRECTOR: UserInfo = DIRECTORS[0]

# Менеджеры
MANAGERS: list[UserInfo] = [
    UserInfo(
        user_id=7318158530,
        username="Polad0666",
        phone="+79538884703",
        role=UserRole.MANAGER,
        name="Polad"
    ),
    UserInfo(
        user_id=1062845086,
        username="Seyymur",
        phone="+79237752170",
        role=UserRole.MANAGER,
        name="Сеймур"
    ),
    # Alan_191 - добавить user_id когда появится в системе
]

# Боты (автоматические рассылки, исключаем из аналитики клиентов)
BOTS: list[UserInfo] = [
    UserInfo(
        user_id=8334694002,
        username="Cvgorod1_bot",
        phone=None,
        role=UserRole.BOT,
        name="Бот рассылки"
    ),
    UserInfo(
        user_id=6395960386,
        username="cvgorodassistent_bot",
        phone=None,
        role=UserRole.BOT,
        name="AI Ассистент"
    ),
]


# ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ====================

def get_admin_id() -> int:
    """Возвращает ID администратора для пересылки сообщений."""
    return ADMIN.user_id


def get_director_ids() -> Set[int]:
    """Возвращает ID всех директоров."""
    return {d.user_id for d in DIRECTORS if d.user_id is not None}


def get_all_staff_ids() -> Set[int]:
    """Возвращает ID всех сотрудников (админ + директора + менеджеры)."""
    ids = {ADMIN.user_id}
    ids.update(d.user_id for d in DIRECTORS if d.user_id is not None)
    ids.update(m.user_id for m in MANAGERS)
    return ids


def get_all_bot_ids() -> Set[int]:
    """Возвращает ID всех ботов."""
    return {b.user_id for b in BOTS}


def get_all_non_client_ids() -> Set[int]:
    """Возвращает ID всех НЕ-клиентов (сотрудники + боты)."""
    return get_all_staff_ids() | get_all_bot_ids()


def get_user_role(user_id: int) -> UserRole:
    """Определяет роль пользователя по ID."""
    if user_id == ADMIN.user_id:
        return UserRole.ADMIN
    
    for director in DIRECTORS:
        if director.user_id and user_id == director.user_id:
            return UserRole.DIRECTOR
    
    for manager in MANAGERS:
        if user_id == manager.user_id:
            return UserRole.MANAGER
    
    for bot in BOTS:
        if user_id == bot.user_id:
            return UserRole.BOT
    
    return UserRole.CLIENT


def get_user_role_by_username(username: str) -> UserRole:
    """Определяет роль пользователя по username."""
    user = get_user_by_username(username)
    return user.role if user else UserRole.CLIENT


def get_user_by_username(username: str) -> Optional[UserInfo]:
    """Находит пользователя по username."""
    username_clean = username.lstrip("@").lower()
    
    if ADMIN.username and ADMIN.username.lower() == username_clean:
        return ADMIN
    
    for director in DIRECTORS:
        if director.username and director.username.lower() == username_clean:
            return director
    
    for manager in MANAGERS:
        if manager.username and manager.username.lower() == username_clean:
            return manager
    
    for bot in BOTS:
        if bot.username and bot.username.lower() == username_clean:
            return bot
    
    return None


def is_admin(user_id: int) -> bool:
    """Проверяет, является ли пользователь администратором."""
    return user_id == ADMIN.user_id


def is_director(user_id: int) -> bool:
    """Проверяет, является ли пользователь директором."""
    return user_id in get_director_ids()


def is_staff(user_id: int) -> bool:
    """Проверяет, является ли пользователь сотрудником."""
    return user_id in get_all_staff_ids()


def is_bot(user_id: int) -> bool:
    """Проверяет, является ли пользователь ботом."""
    return user_id in get_all_bot_ids()


def is_client(user_id: int) -> bool:
    """Проверяет, является ли пользователь клиентом."""
    return user_id not in get_all_non_client_ids()


def should_forward_to_admin(user_id: int) -> bool:
    """Проверяет, нужно ли пересылать сообщения этого пользователя админу."""
    return is_director(user_id)


# ==================== ASYNC ФУНКЦИИ (с использованием role_repository) ====================
# Эти функции используют PostgreSQL как основной источник данных,
# с fallback на статический конфиг если БД недоступна.

import logging

logger = logging.getLogger(__name__)


async def async_get_user_role(user_id: int):
    """
    Возвращает информацию о роли пользователя из БД.

    Использует role_repository с fallback на статический конфиг.

    Args:
        user_id: ID пользователя в Telegram

    Returns:
        RoleInfo с информацией о роли
    """
    try:
        from services.role_repository import role_repository
        return await role_repository.get_user_role(user_id)
    except Exception as e:
        logger.warning(f"Failed to get role from DB: {e}")
        # Fallback на синхронную функцию
        static_role = get_user_role(user_id)
        return static_role


async def async_get_all_staff_ids() -> Set[int]:
    """
    Возвращает множество ID всех сотрудников из БД.

    Returns:
        Множество user_id сотрудников
    """
    try:
        from services.role_repository import role_repository
        return await role_repository.get_all_staff_ids()
    except Exception as e:
        logger.warning(f"Failed to get staff IDs from DB: {e}")
        return get_all_staff_ids()


async def async_get_all_bot_ids() -> Set[int]:
    """
    Возвращает множество ID всех ботов из БД.

    Returns:
        Множество user_id ботов
    """
    try:
        from services.role_repository import role_repository
        return await role_repository.get_all_bot_ids()
    except Exception as e:
        logger.warning(f"Failed to get bot IDs from DB: {e}")
        return get_all_bot_ids()


async def async_get_all_non_client_ids() -> Set[int]:
    """
    Возвращает множество ID всех НЕ-клиентов из БД.

    Returns:
        Множество user_id не-клиентов
    """
    try:
        from services.role_repository import role_repository
        return await role_repository.get_all_non_client_ids()
    except Exception as e:
        logger.warning(f"Failed to get non-client IDs from DB: {e}")
        return get_all_non_client_ids()


async def async_is_staff(user_id: int) -> bool:
    """
    Проверяет, является ли пользователь сотрудником (из БД).

    Args:
        user_id: ID пользователя

    Returns:
        True если сотрудник, False иначе
    """
    try:
        from services.role_repository import role_repository
        return await role_repository.is_staff(user_id)
    except Exception as e:
        logger.warning(f"Failed to check is_staff from DB: {e}")
        return is_staff(user_id)


async def async_is_bot(user_id: int) -> bool:
    """
    Проверяет, является ли пользователь ботом (из БД).

    Args:
        user_id: ID пользователя

    Returns:
        True если бот, False иначе
    """
    try:
        from services.role_repository import role_repository
        return await role_repository.is_bot(user_id)
    except Exception as e:
        logger.warning(f"Failed to check is_bot from DB: {e}")
        return is_bot(user_id)


async def async_is_client(user_id: int) -> bool:
    """
    Проверяет, является ли пользователь клиентом (из БД).

    Args:
        user_id: ID пользователя

    Returns:
        True если клиент, False иначе
    """
    try:
        from services.role_repository import role_repository
        return await role_repository.is_client(user_id)
    except Exception as e:
        logger.warning(f"Failed to check is_client from DB: {e}")
        return is_client(user_id)


# ==================== ЭКСПОРТ ====================

# Обратная совместимость с MANAGER_NAMES в других модулях
MANAGER_NAMES: Set[str] = {"джафар", "сеймур", "polad", "alan"}
MANAGER_IDS: Set[int] = get_all_staff_ids()
BOT_IDS: Set[int] = get_all_bot_ids()
DIRECTOR_IDS: Set[int] = get_director_ids()
ADMIN_ID: int = get_admin_id()

