"""
Config __init__ for cvgorod-hub.
"""

from .settings import (
    ADMIN_IDS,
    DATABASE_URL,
    DEEPSEEK_API_KEY,
    HUB_API_HOST,
    HUB_API_KEY,
    HUB_API_PORT,
    REDIS_URL,
    TELEGRAM_BOT_TOKEN,
)

__all__ = [
    "HUB_API_KEY",
    "HUB_API_HOST",
    "HUB_API_PORT",
    "TELEGRAM_BOT_TOKEN",
    "DATABASE_URL",
    "REDIS_URL",
    "DEEPSEEK_API_KEY",
    "ADMIN_IDS",
]
