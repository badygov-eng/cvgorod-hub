"""
Settings for cvgorod-hub.
"""

import os
from pathlib import Path
from dotenv import load_dotenv


def _load_secrets() -> None:
    """Загрузка секретов из централизованного хранилища ~/.secrets/."""
    secrets_base = Path(os.getenv("SECRETS_PATH", str(Path.home() / '.secrets')))
    
    secret_files = [
        secrets_base / 'telegram' / 'cvgorod.env',
        secrets_base / 'cvgorod' / 'hub_api.env',
        secrets_base / 'cloud' / 'deepseek.env',
    ]
    
    loaded = []
    for secret_file in secret_files:
        if secret_file.exists():
            load_dotenv(secret_file, override=False)
            loaded.append(secret_file.name)
    
    # Локальные настройки
    load_dotenv('.env', override=False)


_load_secrets()

# Hub API
HUB_API_KEY = os.getenv("HUB_API_KEY")
HUB_API_HOST = os.getenv("HUB_API_HOST", "0.0.0.0")
HUB_API_PORT = int(os.getenv("HUB_API_PORT", "8000"))

# Telegram Bot
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Database
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://localhost/cvgorod_hub"
)

# Redis
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

# DeepSeek for intent classification
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

# Intent Classifier settings
INTENT_CLASSIFIER_BATCH_TIMEOUT = float(os.getenv("INTENT_CLASSIFIER_BATCH_TIMEOUT", "5.0"))
INTENT_CLASSIFIER_BATCH_SIZE = int(os.getenv("INTENT_CLASSIFIER_BATCH_SIZE", "10"))

# Sandbox settings
SANDBOX_ENABLED = os.getenv("SANDBOX_ENABLED", "true").lower() == "true"
ADMIN_IDS = [int(_id) for _id in os.getenv("ADMIN_IDS", "").split(",") if _id.strip().isdigit()]
