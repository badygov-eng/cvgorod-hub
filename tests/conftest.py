"""
Pytest fixtures for cvgorod-hub tests.
Includes MCP shared fixtures for consistent testing across projects.
"""

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# Add path to project root
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_settings():
    """Mock settings for testing (все значения должны быть строками для os.environ)."""
    return {
        "HUB_API_KEY": "test-api-key-12345",
        "HUB_API_HOST": "127.0.0.1",
        "HUB_API_PORT": "8000",
        "TELEGRAM_BOT_TOKEN": "test-telegram-token",
        "DATABASE_URL": "postgresql://localhost/cvgorod_hub_test",
        "REDIS_URL": "redis://localhost:6379",
        "DEEPSEEK_API_KEY": "test-deepseek-key",
        "DEEPSEEK_MODEL": "deepseek-chat",
        "INTENT_CLASSIFIER_BATCH_TIMEOUT": "5.0",
        "INTENT_CLASSIFIER_BATCH_SIZE": "10",
        "SANDBOX_ENABLED": "true",
        "ADMIN_IDS": "123456789",
    }


@pytest.fixture
def mock_database():
    """Create a properly mocked database instance."""
    # Create mock instance
    mock_db = MagicMock()
    
    # Mock async methods
    mock_db.connect = AsyncMock()
    mock_db.close = AsyncMock()
    mock_db.fetch = AsyncMock(return_value=[])
    mock_db.fetchrow = AsyncMock(return_value=None)
    mock_db.fetchval = AsyncMock(return_value=None)
    mock_db.execute = AsyncMock(return_value="OK")
    
    # Mock pool property
    mock_pool = MagicMock()
    mock_db.pool = mock_pool
    
    # Mock acquire context manager
    mock_ctx = MagicMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_ctx)
    mock_ctx.__aexit__ = AsyncMock(return_value=None)
    mock_db.acquire = MagicMock(return_value=mock_ctx)
    
    # Mock database methods used in routes
    mock_db.get_messages = AsyncMock(return_value=[])
    mock_db.get_users = AsyncMock(return_value=[])
    mock_db.get_all_managers = AsyncMock(return_value=[])
    mock_db.get_user = AsyncMock(return_value=None)
    mock_db.get_user_statistics = AsyncMock(return_value={})
    mock_db.update_user_role = AsyncMock(return_value=True)
    mock_db.get_conversation_analytics = AsyncMock(return_value={})
    mock_db.get_unanswered_questions = AsyncMock(return_value=[])
    mock_db.get_mailing_campaigns = AsyncMock(return_value=[])
    mock_db.get_chat = AsyncMock(return_value=None)
    mock_db.get_chat_participants = AsyncMock(return_value=[])
    mock_db.get_message_count = AsyncMock(return_value=0)
    mock_db.get_all_non_client_ids = AsyncMock(return_value=[])
    mock_db.get_all_staff_ids = AsyncMock(return_value=[])
    mock_db.get_all_bot_ids = AsyncMock(return_value=[])
    
    return mock_db


@pytest.fixture
def mock_deepseek_response():
    """Mock DeepSeek API response."""
    return {
        "choices": [
            {
                "message": {
                    "content": '{"intent": "question", "sentiment": "neutral", "entities": {}, "confidence": 0.9}'
                }
            }
        ],
        "usage": {
            "prompt_tokens": 50,
            "completion_tokens": 30,
        }
    }


@pytest.fixture
def client(mock_settings, mock_database):
    """FastAPI test client with mocked dependencies."""
    with patch.dict("os.environ", mock_settings, clear=False):
        # Patch settings module to use test API key
        with patch("config.settings.HUB_API_KEY", mock_settings["HUB_API_KEY"]):
            # Patch the Database class singleton
            with patch("services.database.Database") as MockDatabase:
                MockDatabase.return_value = mock_database
                
                # Also patch the module-level db instance
                with patch("services.database.db", mock_database):
                    # Force reimport of modules that use db
                    from fastapi.testclient import TestClient
                    from api.main import app
                    
                    with TestClient(app) as c:
                        yield c


@pytest.fixture
def api_key():
    """Test API key."""
    return "test-api-key-12345"


@pytest.fixture
def auth_headers(api_key):
    """Headers with API key."""
    return {"X-API-Key": api_key}


@pytest.fixture
def authorized_client(client, auth_headers):
    """Test client with authentication."""
    client.headers.update(auth_headers)
    return client
