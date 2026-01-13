"""
Pytest fixtures for cvgorod-hub tests.
Includes MCP shared fixtures for consistent testing across projects.
"""

import pytest
import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

# Добавляем путь к корню проекта и MCP
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Попытка добавить MCP path для shared fixtures
mcp_path = Path("/Users/danielbadygov/MCP")
if mcp_path.exists() and str(mcp_path) not in sys.path:
    sys.path.insert(0, str(mcp_path))


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_settings():
    """Mock settings for testing."""
    return {
        "HUB_API_KEY": "test-api-key-12345",
        "HUB_API_HOST": "127.0.0.1",
        "HUB_API_PORT": 8000,
        "TELEGRAM_BOT_TOKEN": "test-telegram-token",
        "DATABASE_URL": "postgresql://localhost/cvgorod_hub_test",
        "REDIS_URL": "redis://localhost:6379",
        "DEEPSEEK_API_KEY": "test-deepseek-key",
        "DEEPSEEK_MODEL": "deepseek-chat",
        "INTENT_CLASSIFIER_BATCH_TIMEOUT": 5.0,
        "INTENT_CLASSIFIER_BATCH_SIZE": 10,
        "SANDBOX_ENABLED": True,
        "ADMIN_IDS": [123456789],
    }


@pytest.fixture
def mock_database():
    """Mock database connection."""
    mock_db = MagicMock()
    mock_db.connect = AsyncMock()
    mock_db.close = AsyncMock()
    mock_db.pool = MagicMock()

    # Mock async context manager
    mock_ctx = MagicMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_ctx)
    mock_ctx.__aexit__ = AsyncMock()
    mock_db.acquire.return_value = mock_ctx

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
    with patch.dict("os.environ", mock_settings):
        with patch("services.database.db", mock_database):
            from api.main import app
            from fastapi.testclient import TestClient

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


# =============================================================================
# MCP Shared Fixtures (when available)
# =============================================================================

try:
    from MCP.tests.conftest import (
        mcp_test_client,
        mcp_mock_httpx,
        mcp_captured_logs,
    )

    @pytest.fixture
    def mcp_client(mcp_test_client):
        """MCP test client fixture."""
        return mcp_test_client

except ImportError:
    """MCP fixtures not available - using local fixtures."""
    pass
