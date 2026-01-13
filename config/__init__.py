"""
Config __init__ for cvgorod-hub.
"""

from .settings import (
    HUB_API_KEY,
    HUB_API_HOST,
    HUB_API_PORT,
    TELEGRAM_BOT_TOKEN,
    DATABASE_URL,
    REDIS_URL,
    DEEPSEEK_API_KEY,
)

__all__ = [
    "HUB_API_KEY",
    "HUB_API_HOST", 
    "HUB_API_PORT",
    "TELEGRAM_BOT_TOKEN",
    "DATABASE_URL",
    "REDIS_URL",
    "DEEPSEEK_API_KEY",
]
