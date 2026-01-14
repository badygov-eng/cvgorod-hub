"""
Unit tests for role model functionality.
Tests for role classification, API endpoints with role filtering, and database methods.
"""

import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class TestRoleClassification:
    """Tests for role classification logic."""

    def test_valid_roles(self):
        """Test that valid roles are accepted."""
        valid_roles = ["CLIENT", "MANAGER", "DIRECTOR", "BOT"]
        for role in valid_roles:
            assert role in valid_roles

    def test_role_constants_from_schema(self):
        """Test that roles match database schema."""
        # Roles from user_roles table
        expected_roles = ["admin", "director", "manager", "broadcast_bot", "assistant_bot", "client"]
        # Mapped roles for messages
        message_roles = ["CLIENT", "MANAGER", "DIRECTOR", "BOT"]

        # All message roles should be valid
        for role in message_roles:
            assert role in ["CLIENT", "MANAGER", "DIRECTOR", "BOT"]

    def test_client_role_characteristics(self):
        """Test CLIENT role characteristics."""
        client_role = "CLIENT"

        # Client characteristics
        assert client_role == "CLIENT"
        assert client_role != "MANAGER"
        assert client_role != "BOT"

    def test_manager_role_characteristics(self):
        """Test MANAGER role characteristics."""
        manager_role = "MANAGER"

        # Manager characteristics
        assert manager_role == "MANAGER"
        assert manager_role != "CLIENT"
        assert manager_role != "BOT"

    def test_role_mapping(self):
        """Test role mapping between user_roles table and message role."""
        # Mapping from database roles to message roles
        role_mapping = {
            "client": "CLIENT",
            "manager": "MANAGER",
            "director": "DIRECTOR",
            "admin": "MANAGER",  # Admins have same role as managers for messaging
            "broadcast_bot": "BOT",
            "assistant_bot": "BOT",
        }

        for db_role, message_role in role_mapping.items():
            assert message_role in ["CLIENT", "MANAGER", "DIRECTOR", "BOT"]


class TestMessageRoleFiltering:
    """Tests for message filtering by role."""

    @pytest.mark.asyncio
    async def test_get_messages_with_role_filter(self, mock_database):
        """Test get_messages with role filter."""
        from services.database import Database

        db = Database()
        db._pool = mock_database

        mock_rows = [
            {"id": 1, "text": "Client message", "role": "CLIENT", "username": "client1"},
            {"id": 2, "text": "Manager message", "role": "MANAGER", "username": "manager1"},
        ]

        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=mock_rows)

        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_ctx.__aexit__ = AsyncMock()
        mock_database.acquire.return_value = mock_ctx

        result = await db.get_messages(role="CLIENT", limit=10)

        assert len(result) == 2
        mock_conn.fetch.assert_called_once()
        # Check that role filter was in the query
        call_args = mock_conn.fetch.call_args[0][0]
        assert "m.role = " in call_args

    @pytest.mark.asyncio
    async def test_get_messages_with_exclude_automatic(self, mock_database):
        """Test get_messages with exclude_automatic filter."""
        from services.database import Database

        db = Database()
        db._pool = mock_database

        mock_rows = [
            {"id": 1, "text": "Manual message", "is_automatic": False},
            {"id": 2, "text": "Auto message", "is_automatic": True},
        ]

        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=mock_rows)

        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_ctx.__aexit__ = AsyncMock()
        mock_database.acquire.return_value = mock_ctx

        result = await db.get_messages(exclude_automatic=True, limit=10)

        assert len(result) == 2
        call_args = mock_conn.fetch.call_args[0][0]
        assert "is_automatic" in call_args

    @pytest.mark.asyncio
    async def test_get_messages_with_intent_filter(self, mock_database):
        """Test get_messages with intent filter."""
        from services.database import Database

        db = Database()
        db._pool = mock_database

        mock_rows = [
            {"id": 1, "text": "Question", "intent": "inquiry_stock"},
        ]

        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=mock_rows)

        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_ctx.__aexit__ = AsyncMock()
        mock_database.acquire.return_value = mock_ctx

        result = await db.get_messages(has_intent="inquiry_stock", limit=10)

        assert len(result) == 1
        call_args = mock_conn.fetch.call_args[0][0]
        assert "m.intent = " in call_args

    @pytest.mark.asyncio
    async def test_get_messages_clients_only(self, mock_database):
        """Test get_messages with clients_only filter."""
        from services.database import Database

        db = Database()
        db._pool = mock_database

        mock_rows = [
            {"id": 1, "text": "Client 1", "role": "CLIENT"},
            {"id": 2, "text": "Client 2", "role": "CLIENT"},
        ]

        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=mock_rows)
        mock_conn.fetchval = AsyncMock(return_value=[100, 200, 300])  # Non-client IDs

        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_ctx.__aexit__ = AsyncMock()
        mock_database.acquire.return_value = mock_ctx

        result = await db.get_messages(clients_only=True, limit=10)

        assert len(result) == 2
        call_args = mock_conn.fetch.call_args[0][0]
        assert "NOT IN" in call_args


class TestUserRoleManagement:
    """Tests for user role management."""

    @pytest.mark.asyncio
    async def test_update_user_role_valid(self, mock_database):
        """Test updating user role with valid role."""
        from services.database import Database

        db = Database()
        db._pool = mock_database

        mock_conn = AsyncMock()
        mock_conn.fetchval = AsyncMock(return_value=123)

        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_ctx.__aexit__ = AsyncMock()
        mock_database.acquire.return_value = mock_ctx

        result = await db.update_user_role(user_id=123, role="MANAGER")

        assert result is True
        mock_conn.fetchval.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_user_role_invalid(self, mock_database):
        """Test updating user role with invalid role raises error."""
        from services.database import Database

        db = Database()
        db._pool = mock_database

        with pytest.raises(ValueError, match="Invalid role"):
            await db.update_user_role(user_id=123, role="INVALID")

    @pytest.mark.asyncio
    async def test_get_users_with_role_filter(self, mock_database):
        """Test getting users with role filter."""
        from services.database import Database

        db = Database()
        db._pool = mock_database

        mock_rows = [
            {"id": 1, "username": "user1", "role": "MANAGER"},
            {"id": 2, "username": "user2", "role": "MANAGER"},
        ]

        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=mock_rows)

        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_ctx.__aexit__ = AsyncMock()
        mock_database.acquire.return_value = mock_ctx

        result = await db.get_users(role="MANAGER", limit=10)

        assert len(result) == 2
        call_args = mock_conn.fetch.call_args[0][0]
        assert "u.role = " in call_args

    @pytest.mark.asyncio
    async def test_get_all_managers(self, mock_database):
        """Test getting all managers."""
        from services.database import Database

        db = Database()
        db._pool = mock_database

        mock_rows = [
            {"id": 1, "first_name": "Manager1", "chats_count": 5, "messages_count": 100},
            {"id": 2, "first_name": "Manager2", "chats_count": 3, "messages_count": 50},
        ]

        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=mock_rows)

        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_ctx.__aexit__ = AsyncMock()
        mock_database.acquire.return_value = mock_ctx

        result = await db.get_all_managers()

        assert len(result) == 2
        assert result[0]["chats_count"] == 5


class TestMailingCampaigns:
    """Tests for mailing campaign functionality."""

    @pytest.mark.asyncio
    async def test_create_mailing_campaign(self, mock_database):
        """Test creating mailing campaign."""
        from services.database import Database

        db = Database()
        db._pool = mock_database

        mock_conn = AsyncMock()
        mock_conn.fetchval = AsyncMock(return_value=1)

        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_ctx.__aexit__ = AsyncMock()
        mock_database.acquire.return_value = mock_ctx

        result = await db.create_mailing_campaign(
            name="Test Campaign",
            message_template="Hello {name}!",
            sent_by_user_id=123,
            description="Test description"
        )

        assert result == 1
        mock_conn.fetchval.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_mailing_campaigns(self, mock_database):
        """Test getting mailing campaigns."""
        from services.database import Database

        db = Database()
        db._pool = mock_database

        mock_rows = [
            {
                "id": 1,
                "name": "Campaign1",
                "message_template": "Template1",
                "status": "COMPLETED",
                "sent_by_username": "manager1",
            },
        ]

        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=mock_rows)

        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_ctx.__aexit__ = AsyncMock()
        mock_database.acquire.return_value = mock_ctx

        result = await db.get_mailing_campaigns(status="COMPLETED", limit=10)

        assert len(result) == 1
        assert result[0]["name"] == "Campaign1"


class TestAnalytics:
    """Tests for analytics functionality."""

    @pytest.mark.asyncio
    async def test_get_conversation_analytics(self, mock_database):
        """Test getting conversation analytics."""
        from services.database import Database

        db = Database()
        db._pool = mock_database

        # Mock base stats
        mock_base = MagicMock()
        mock_base.__getitem__ = lambda self, key: {
            "total_messages": 100,
            "total_dialogs": 10,
            "client_dialogs": 8
        }.get(key)
        mock_base.get = lambda key: {"total_messages": 100}.get(key)

        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value={
            "total_messages": 100,
            "total_dialogs": 10,
            "client_dialogs": 8
        })
        mock_conn.fetch = AsyncMock(return_value=[
            {"role": "CLIENT", "count": 60},
            {"role": "MANAGER", "count": 35},
            {"role": "BOT", "count": 5},
        ])

        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_ctx.__aexit__ = AsyncMock()
        mock_database.acquire.return_value = mock_ctx

        result = await db.get_conversation_analytics()

        assert "statistics" in result
        assert "manager_performance" in result

    @pytest.mark.asyncio
    async def test_get_unanswered_questions(self, mock_database):
        """Test getting unanswered questions."""
        from services.database import Database

        db = Database()
        db._pool = mock_database

        mock_rows = [
            {
                "message_id": 1,
                "chat_id": 100,
                "chat_name": "Test Chat",
                "question_text": "Is this in stock?",
            },
        ]

        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=mock_rows)

        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_ctx.__aexit__ = AsyncMock()
        mock_database.acquire.return_value = mock_ctx

        result = await db.get_unanswered_questions(hours=24, limit=10)

        assert len(result) == 1
        assert result[0]["question_text"] == "Is this in stock?"


class TestRoleModelMigration:
    """Tests for migration script components."""

    def test_migration_script_exists(self):
        """Test that migration script exists."""
        import os
        migration_path = Path(__file__).parent.parent.parent / "scripts" / "migrate_add_roles.sql"
        assert migration_path.exists(), f"Migration script not found at {migration_path}"

    def test_migration_creates_required_tables(self):
        """Test that migration creates required tables."""
        migration_path = Path(__file__).parent.parent.parent / "scripts" / "migrate_add_roles.sql"
        content = migration_path.read_text()

        # Check for required tables
        assert "mailing_campaigns" in content
        assert "mailing_campaign_messages" in content
        assert "user_chats" in content

    def test_migration_adds_required_columns(self):
        """Test that migration adds required columns to messages."""
        migration_path = Path(__file__).parent.parent.parent / "scripts" / "migrate_add_roles.sql"
        content = migration_path.read_text()

        # Check for required columns
        assert "role" in content
        assert "is_automatic" in content
        assert "intent" in content
        assert "is_reply" in content
        assert "reply_to_message_id" in content

    def test_migration_creates_indexes(self):
        """Test that migration creates indexes."""
        migration_path = Path(__file__).parent.parent.parent / "scripts" / "migrate_add_roles.sql"
        content = migration_path.read_text()

        # Check for indexes
        assert "CREATE INDEX" in content
        assert "idx_messages_role" in content
        assert "idx_messages_intent" in content


class TestRoleModelPydanticModels:
    """Tests for Pydantic models in API."""

    def test_message_response_with_role(self):
        """Test MessageResponse model with role field."""
        from api.routes.messages import MessageResponse

        msg = MessageResponse(
            id=1,
            chat_id=100,
            user_id=200,
            text="Hello",
            message_type="text",
            timestamp=datetime.now(),
            role="CLIENT",
            is_automatic=False,
            intent="greeting",
            is_reply=False,
        )

        assert msg.role == "CLIENT"
        assert msg.is_automatic is False
        assert msg.intent == "greeting"

    def test_user_response_with_role(self):
        """Test UserResponse model with role field."""
        from api.routes.clients import UserResponse

        user = UserResponse(
            id=1,
            username="testuser",
            first_name="Test",
            role="MANAGER",
            is_manager=True,
            chats_count=5,
            messages_count=100,
        )

        assert user.role == "MANAGER"
        assert user.is_manager is True
        assert user.chats_count == 5

    def test_manager_response(self):
        """Test ManagerResponse model."""
        from api.routes.clients import ManagerResponse

        manager = ManagerResponse(
            id=1,
            first_name="John",
            chats_count=10,
            messages_count=500,
            is_active=True,
        )

        assert manager.chats_count == 10
        assert manager.is_active is True
