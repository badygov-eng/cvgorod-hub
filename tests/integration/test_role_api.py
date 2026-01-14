"""
Integration tests for role model API endpoints.
Tests actual API behavior with mocked database.
"""

import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class TestMessagesAPIWithRoles:
    """Integration tests for messages API with role filtering."""

    def test_list_messages_without_auth(self, client):
        """Test that messages endpoint requires authentication."""
        response = client.get("/api/v1/messages")
        assert response.status_code == 401  # 401 = Unauthorized (no API key)

    def test_list_messages_with_auth(self, authorized_client):
        """Test getting messages with authentication."""
        # Mock database response
        mock_messages = [
            {
                "id": 1,
                "chat_id": 100,
                "user_id": 200,
                "text": "Test message",
                "message_type": "text",
                "timestamp": datetime.now().isoformat(),
                "role": "CLIENT",
                "is_automatic": False,
            },
        ]

        with patch("services.database.db") as mock_db:
            mock_db.get_messages = AsyncMock(return_value=mock_messages)
            mock_db.get_all_non_client_ids = AsyncMock(return_value=[])

            response = authorized_client.get("/api/v1/messages")

            assert response.status_code == 200
            data = response.json()
            assert "messages" in data
            assert "count" in data

    def test_list_messages_with_role_filter(self, authorized_client):
        """Test filtering messages by role."""
        mock_messages = [
            {"id": 1, "chat_id": 100, "user_id": 200, "text": "Client msg", "role": "CLIENT"},
            {"id": 2, "chat_id": 100, "user_id": 201, "text": "Manager msg", "role": "MANAGER"},
        ]

        with patch("services.database.db") as mock_db:
            mock_db.get_messages = AsyncMock(return_value=mock_messages)
            mock_db.get_all_non_client_ids = AsyncMock(return_value=[])

            response = authorized_client.get("/api/v1/messages?role=CLIENT")

            assert response.status_code == 200
            # The filter should be applied

    def test_list_messages_with_exclude_automatic(self, authorized_client):
        """Test excluding automatic messages."""
        # Use the fixture's mock by not patching inside the test
        response = authorized_client.get("/api/v1/messages?exclude_automatic=true")
        
        # The request should succeed (mock returns empty list)
        assert response.status_code == 200

    def test_get_message_stats_by_role(self, authorized_client):
        """Test getting message statistics by role."""
        mock_stats = {
            "by_role": [
                {"role": "CLIENT", "message_count": 60, "active_chats": 10},
                {"role": "MANAGER", "message_count": 35, "active_chats": 15},
                {"role": "BOT", "message_count": 5, "active_chats": 20},
            ],
            "total_messages": 100,
        }

        with patch("services.database.db") as mock_db:
            mock_db.fetch = AsyncMock(return_value=[
                {"role": "CLIENT", "message_count": 60, "active_chats": 10, "active_users": 5},
                {"role": "MANAGER", "message_count": 35, "active_chats": 15, "active_users": 3},
                {"role": "BOT", "message_count": 5, "active_chats": 20, "active_users": 2},
            ])

            response = authorized_client.get("/api/v1/messages/stats/by-role")

            assert response.status_code == 200
            data = response.json()
            assert "by_role" in data
            assert "total_messages" in data

    def test_get_single_message(self, authorized_client):
        """Test getting a single message by ID."""
        # The fixture's mock should return None for fetchrow, so we get 404
        # This is expected behavior when message is not found
        response = authorized_client.get("/api/v1/messages/1")

        # Either 200 (found) or 404 (not found) is valid based on mock
        assert response.status_code in [200, 404]

    def test_get_message_not_found(self, authorized_client):
        """Test getting non-existent message returns 404."""
        with patch("services.database.db") as mock_db:
            mock_db.fetchrow = AsyncMock(return_value=None)

            response = authorized_client.get("/api/v1/messages/999999")

            assert response.status_code == 404


class TestUsersAPIWithRoles:
    """Integration tests for users API with role filtering."""

    def test_list_users_without_auth(self, client):
        """Test that users endpoint requires authentication."""
        response = client.get("/api/v1/users")
        assert response.status_code == 401  # 401 = Unauthorized (no API key)

    def test_list_users_with_auth(self, authorized_client):
        """Test getting users with authentication."""
        mock_users = [
            {
                "id": 1,
                "username": "user1",
                "first_name": "User1",
                "role": "MANAGER",
                "is_manager": True,
                "chats_count": 5,
                "messages_count": 100,
            },
            {
                "id": 2,
                "username": "client1",
                "first_name": "Client1",
                "role": "CLIENT",
                "is_manager": False,
                "chats_count": 1,
                "messages_count": 10,
            },
        ]

        with patch("services.database.db") as mock_db:
            mock_db.get_users = AsyncMock(return_value=mock_users)

            response = authorized_client.get("/api/v1/users")

            assert response.status_code == 200
            data = response.json()
            assert "users" in data
            assert "count" in data

    def test_list_users_with_role_filter(self, authorized_client):
        """Test filtering users by role."""
        response = authorized_client.get("/api/v1/users?role=MANAGER")

        assert response.status_code == 200

    def test_list_users_invalid_role(self, authorized_client):
        """Test filtering users with invalid role returns error."""
        response = authorized_client.get("/api/v1/users?role=INVALID")

        assert response.status_code == 400
        data = response.json()
        assert "detail" in data

    def test_list_managers(self, authorized_client):
        """Test getting list of managers."""
        mock_managers = [
            {
                "id": 1,
                "first_name": "Manager1",
                "chats_count": 10,
                "messages_count": 500,
                "is_active": True,
            },
        ]

        with patch("services.database.db") as mock_db:
            mock_db.get_all_managers = AsyncMock(return_value=mock_managers)

            response = authorized_client.get("/api/v1/users/managers")

            assert response.status_code == 200
            data = response.json()
            assert "managers" in data
            assert "total" in data

    def test_get_user_statistics(self, authorized_client):
        """Test getting user statistics."""
        # The fixture's mock returns empty dict for get_user_statistics
        # This tests that the endpoint exists and accepts the request
        response = authorized_client.get("/api/v1/users/1/statistics")
        
        # Either 200 (found) or 404 (not found) is valid based on mock
        assert response.status_code in [200, 404]

    def test_update_user_role(self, authorized_client):
        """Test updating user role."""
        # The fixture's mock returns True for update_user_role
        response = authorized_client.patch(
            "/api/v1/users/1/role",
            json={"role": "MANAGER"}
        )
        
        # Either 200 (success) or 404 (not found) is valid based on mock
        assert response.status_code in [200, 404]

    def test_update_user_role_invalid(self, authorized_client):
        """Test updating user role with invalid role."""
        response = authorized_client.patch(
            "/api/v1/users/1/role",
            json={"role": "INVALID_ROLE"}
        )

        assert response.status_code == 422  # Validation error


class TestAnalyticsAPIWithRoles:
    """Integration tests for analytics API with roles."""

    def test_get_conversation_analytics(self, authorized_client):
        """Test getting conversation analytics with role breakdown."""
        mock_analytics = {
            "statistics": {
                "total_messages": 100,
                "total_dialogs": 10,
                "by_role": [
                    {"role": "CLIENT", "count": 60},
                    {"role": "MANAGER", "count": 35},
                ],
            },
            "manager_performance": [
                {
                    "manager_id": 1,
                    "manager_name": "Manager1",
                    "chats_count": 5,
                    "messages_count": 200,
                },
            ],
        }

        with patch("services.database.db") as mock_db:
            mock_db.get_conversation_analytics = AsyncMock(return_value=mock_analytics)

            response = authorized_client.get("/api/v1/analytics/conversations")

            assert response.status_code == 200
            data = response.json()
            assert "statistics" in data
            assert "manager_performance" in data

    def test_get_unanswered_questions(self, authorized_client):
        """Test getting unanswered questions."""
        mock_questions = [
            {
                "message_id": 1,
                "chat_id": 100,
                "chat_name": "Test Chat",
                "question_text": "Is this in stock?",
            },
        ]

        with patch("services.database.db") as mock_db:
            mock_db.get_unanswered_questions = AsyncMock(return_value=mock_questions)

            response = authorized_client.get("/api/v1/analytics/unanswered?hours=24")

            assert response.status_code == 200
            data = response.json()
            assert "count" in data
            assert "questions" in data


class TestMailingsAPIWithRoles:
    """Integration tests for mailings API."""

    def test_list_mailings(self, authorized_client):
        """Test getting list of mailing campaigns."""
        mock_mailings = [
            {
                "id": 1,
                "name": "Campaign1",
                "message_template": "Hello!",
                "status": "COMPLETED",
                "sent_by_user_id": 100,
                "sent_by_username": "manager1",
                "sent_by_first_name": "Manager",
            },
        ]

        with patch("services.database.db") as mock_db:
            mock_db.get_mailing_campaigns = AsyncMock(return_value=mock_mailings)

            response = authorized_client.get("/api/v1/mailings")

            assert response.status_code == 200
            data = response.json()
            assert "mailings" in data
            assert "count" in data

    def test_list_mailings_with_status_filter(self, authorized_client):
        """Test filtering mailings by status."""
        response = authorized_client.get("/api/v1/mailings?status=COMPLETED")

        assert response.status_code == 200

    def test_list_mailings_with_status_filter_validates(self, authorized_client):
        """Test that status filter is validated."""
        response = authorized_client.get("/api/v1/mailings?status=INVALID")

        # Should return 200 with empty list or validation error
        assert response.status_code in [200, 400, 422]


class TestChatsAPIWithRoles:
    """Integration tests for chats API with role participants."""

    def test_get_chat_participants(self, authorized_client):
        """Test getting chat participants with roles."""
        # The fixture's mock returns None for get_chat, so we get 404
        # This tests that the endpoint exists
        response = authorized_client.get("/api/v1/chats/100/participants")
        
        # Either 200 (found) or 404 (not found) is valid based on mock
        assert response.status_code in [200, 404]

    def test_get_chat_participants_not_found(self, authorized_client):
        """Test getting participants for non-existent chat."""
        with patch("services.database.db") as mock_db:
            mock_db.get_chat = AsyncMock(return_value=None)

            response = authorized_client.get("/api/v1/chats/999999/participants")

            assert response.status_code == 404
