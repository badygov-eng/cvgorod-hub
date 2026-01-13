"""
Pytest fixtures for cvgorod-hub tests.
"""

import pytest
import asyncio
from fastapi.testclient import TestClient

# Добавляем путь к корню проекта
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def client():
    """FastAPI test client."""
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
