"""
Settings for cvgorod-hub.
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv


def _setup_mcp_path() -> None:
    """Add MCP shared modules to Python path."""
    mcp_path = Path("/Users/danielbadygov/MCP")
    if mcp_path.exists() and str(mcp_path) not in sys.path:
        sys.path.insert(0, str(mcp_path))


def _load_secrets() -> None:
    """Загрузка секретов из централизованного хранилища ~/.secrets/."""
    # Сначала настраиваем путь к MCP
    _setup_mcp_path()

    # Пытаемся использовать centralized loader из MCP
    try:
        from MCP.shared.secrets_loader import load_project_secrets

        # Загружаем секреты для проекта cvgorod-hub
        load_project_secrets("cvgorod-hub")
        return
    except ImportError:
        # Fallback: ручная загрузка если MCP недоступен
        pass

    # Ручная загрузка (fallback)
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

    # Загружаем environment-specific .env файл
    env = os.getenv("ENVIRONMENT", "development")
    env_file = f".env.{env}" if env != "development" else ".env"
    env_path = Path(env_file)
    if env_path.exists():
        load_dotenv(env_path, override=True)
    else:
        # Fallback на базовый .env
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

# =============================================================================
# Yandex Tracker Settings
# =============================================================================
TRACKER_ENABLED = os.getenv("TRACKER_ENABLED", "true").lower() == "true"
TRACKER_TOKEN = os.getenv("TRACKER_TOKEN")
TRACKER_ORG_ID = os.getenv("TRACKER_ORG_ID")
TRACKER_QUEUE = os.getenv("TRACKER_QUEUE", "TGBOTCG")

# =============================================================================
# Perplexity Settings (AI Search)
# =============================================================================
PERPLEXITY_API_KEY = os.getenv("PERPLEXITY_API_KEY")
PERPLEXITY_MODEL = os.getenv("PERPLEXITY_MODEL", "sonar")
