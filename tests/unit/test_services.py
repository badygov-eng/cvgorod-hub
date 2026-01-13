"""
Unit tests for services/database.py
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class TestDatabaseClass:
    """Tests for Database class."""

    def test_database_singleton(self):
        """Database should be a singleton."""
        from services.database import Database

        db1 = Database()
        db2 = Database()
        assert db1 is db2

    @pytest.mark.asyncio
    async def test_connect_creates_pool(self, mock_database):
        """Connect should create connection pool."""
        from services.database import Database

        db = Database()
        db._pool = None

        with patch("services.database.asyncpg.create_pool", new_callable=AsyncMock) as mock_create_pool:
            mock_create_pool.return_value = MagicMock()
            await db.connect()

            mock_create_pool.assert_called_once()
            assert db._pool is not None

    @pytest.mark.asyncio
    async def test_close_closes_pool(self, mock_database):
        """Close should close connection pool."""
        from services.database import Database

        db = Database()
        mock_pool = MagicMock()
        mock_pool.close = AsyncMock()
        db._pool = mock_pool

        await db.close()

        mock_pool.close.assert_called_once()
        assert db._pool is None

    def test_pool_property_raises_when_not_connected(self):
        """Pool property should raise RuntimeError when not connected."""
        from services.database import Database

        db = Database()
        db._pool = None

        with pytest.raises(RuntimeError, match="Database not connected"):
            _ = db.pool

    @pytest.mark.asyncio
    async def test_get_or_create_chat(self, mock_database):
        """Test get_or_create_chat method."""
        from services.database import Database

        db = Database()
        db._pool = mock_database

        mock_conn = AsyncMock()
        mock_conn.fetchval = AsyncMock(return_value=12345)

        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_ctx.__aexit__ = AsyncMock()
        mock_database.acquire.return_value = mock_ctx

        result = await db.get_or_create_chat(
            chat_id=12345,
            chat_name="Test Chat",
            chat_type="group",
            folder="main"
        )

        assert result == 12345
        mock_conn.fetchval.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_or_create_user(self, mock_database):
        """Test get_or_create_user method."""
        from services.database import Database

        db = Database()
        db._pool = mock_database

        mock_conn = AsyncMock()
        mock_conn.fetchval = AsyncMock(return_value=67890)

        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_ctx.__aexit__ = AsyncMock()
        mock_database.acquire.return_value = mock_ctx

        result = await db.get_or_create_user(
            user_id=67890,
            username="testuser",
            first_name="Test",
            last_name="User",
            is_manager=False
        )

        assert result == 67890
        mock_conn.fetchval.assert_called_once()

    @pytest.mark.asyncio
    async def test_save_message(self, mock_database):
        """Test save_message method."""
        from services.database import Database

        db = Database()
        db._pool = mock_database

        mock_conn = AsyncMock()
        mock_conn.fetchval = AsyncMock(return_value=100)

        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_ctx.__aexit__ = AsyncMock()
        mock_database.acquire.return_value = mock_ctx

        result = await db.save_message(
            telegram_message_id=100,
            chat_id=1,
            user_id=1,
            text="Test message",
            message_type="text"
        )

        assert result == 100
        mock_conn.fetchval.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_messages_with_filters(self, mock_database):
        """Test get_messages with filters."""
        from services.database import Database

        db = Database()
        db._pool = mock_database

        mock_rows = [
            {"id": 1, "text": "Message 1", "username": "user1"},
            {"id": 2, "text": "Message 2", "username": "user2"},
        ]

        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=mock_rows)

        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_ctx.__aexit__ = AsyncMock()
        mock_database.acquire.return_value = mock_ctx

        result = await db.get_messages(chat_id=1, limit=10)

        assert len(result) == 2
        assert result[0]["text"] == "Message 1"
        mock_conn.fetch.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_messages_fts(self, mock_database):
        """Test search_messages with full-text search."""
        from services.database import Database

        db = Database()
        db._pool = mock_database

        mock_rows = [
            {"id": 1, "text": "Test message", "text_highlight": "<b>Test</b> message"},
        ]

        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=mock_rows)

        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_ctx.__aexit__ = AsyncMock()
        mock_database.acquire.return_value = mock_ctx

        result = await db.search_messages(query="test", limit=10)

        assert len(result) == 1
        assert "text_highlight" in result[0]
        mock_conn.fetch.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_chat_context(self, mock_database):
        """Test get_chat_context method."""
        from services.database import Database

        db = Database()
        db._pool = mock_database

        mock_messages = [
            {"username": "user1", "first_name": "User", "text": "Hello", "timestamp": datetime.now()},
        ]

        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=mock_messages)

        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_ctx.__aexit__ = AsyncMock()
        mock_database.acquire.return_value = mock_ctx

        result = await db.get_chat_context(chat_id=1, limit=10)

        assert isinstance(result, str)
        assert "user1" in result or "User" in result

    @pytest.mark.asyncio
    async def test_get_message_count(self, mock_database):
        """Test get_message_count method."""
        from services.database import Database

        db = Database()
        db._pool = mock_database

        mock_conn = AsyncMock()
        mock_conn.fetchval = AsyncMock(return_value=42)

        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_ctx.__aexit__ = AsyncMock()
        mock_database.acquire.return_value = mock_ctx

        result = await db.get_message_count(chat_id=1)

        assert result == 42
        mock_conn.fetchval.assert_called_once()


class TestDatabaseConnectionRetry:
    """Tests for database connection retry logic."""

    @pytest.mark.asyncio
    async def test_connect_with_retry_success(self, mock_database):
        """Test successful connection with retry."""
        from services.database import Database

        db = Database()
        mock_pool = MagicMock()

        with patch("services.database.asyncpg.create_pool", new_callable=AsyncMock) as mock_create_pool:
            mock_create_pool.return_value = mock_pool

            result = await db._connect_with_retry("postgresql://test")

            assert result == mock_pool
            mock_create_pool.assert_called_once()

    @pytest.mark.asyncio
    async def test_connect_with_retry_retries_on_failure(self, mock_database):
        """Test retry on connection failure."""
        from services.database import Database
        import asyncpg

        db = Database()
        mock_pool = MagicMock()

        with patch("services.database.asyncpg.create_pool", new_callable=AsyncMock) as mock_create_pool:
            # First two calls fail, third succeeds
            mock_create_pool.side_effect = [
                asyncpg.PostgresConnectionError("Connection failed"),
                asyncpg.PostgresConnectionError("Connection failed"),
                mock_pool,
            ]

            result = await db._connect_with_retry("postgresql://test")

            assert result == mock_pool
            assert mock_create_pool.call_count == 3
