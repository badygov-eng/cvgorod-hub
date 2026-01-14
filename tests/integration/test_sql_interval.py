"""
Integration tests for SQL queries with date intervals.
Tests that parameters inside INTERVAL work correctly.

Запускать с реальной БД:
pytest tests/integration/test_sql_interval.py -v
"""

import pytest
import asyncio
from datetime import datetime, timedelta


class TestSQLIntervalParameters:
    """Tests for SQL queries with INTERVAL parameters."""
    
    @pytest.mark.asyncio
    async def test_interval_with_days_parameter(self, real_db):
        """Test that INTERVAL works with parameter substitution."""
        # Создаём тестовые данные
        await real_db.execute(
            """
            INSERT INTO messages (id, chat_id, user_id, text, role, timestamp)
            VALUES ($1, $2, $3, $4, $5, $6)
            ON CONFLICT (id) DO NOTHING
            """,
            999999, 123, 456, "Test message", "CLIENT", datetime.utcnow()
        )
        
        # Запрос с параметром в INTERVAL
        result = await real_db.fetchval(
            """
            SELECT COUNT(*) FROM messages
            WHERE timestamp >= NOW() - ($1 || ' days')::interval
            """,
            30  # 30 days
        )
        
        assert result >= 1, "Should find test message within 30 days"
    
    @pytest.mark.asyncio
    async def test_interval_with_hours_parameter(self, real_db):
        """Test INTERVAL with hours parameter."""
        # Создаём сообщение 1 час назад
        one_hour_ago = datetime.utcnow() - timedelta(hours=1)
        await real_db.execute(
            """
            INSERT INTO messages (id, chat_id, user_id, text, role, timestamp)
            VALUES ($1, $2, $3, $4, $5, $6)
            ON CONFLICT (id) DO NOTHING
            """,
            999998, 123, 456, "Recent test", "CLIENT", one_hour_ago
        )
        
        result = await real_db.fetchval(
            """
            SELECT COUNT(*) FROM messages
            WHERE timestamp >= NOW() - ($1 || ' hours')::interval
            """,
            24  # 24 hours
        )
        
        assert result >= 1, "Should find message within 24 hours"
    
    @pytest.mark.asyncio
    @pytest.mark.asyncio
    async def test_unanswered_questions_query(self, real_db):
        """Test get_unanswered_questions query with interval parameters."""
        # Это тестирует реальный запрос из database.py
        result = await real_db.fetch(
            """
            SELECT m.id as message_id, m.text
            FROM messages m
            WHERE m.role = 'CLIENT'
                AND m.text LIKE '%?%'
                AND NOT EXISTS (
                    SELECT 1 FROM messages m2
                    WHERE m2.chat_id = m.chat_id
                        AND m2.timestamp > m.timestamp
                        AND m2.timestamp < m.timestamp + ($1 || ' hours')::interval
                        AND m2.role = 'MANAGER'
                )
                AND m.timestamp > NOW() - ($2 || ' hours')::interval
            LIMIT 10
            """,
            2, 24
        )
        
        # Должен вернуть список (возможно пустой, но не ошибку)
        assert isinstance(result, list)
    
    @pytest.mark.asyncio
    async def test_get_user_statistics_query(self, real_db):
        """Test get_user_statistics query with interval parameters."""
        result = await real_db.fetchrow(
            """
            SELECT
                u.id,
                COUNT(DISTINCT m.chat_id) as chats_count,
                COUNT(m.id) as messages_count
            FROM users u
            LEFT JOIN messages m ON u.id = m.user_id
                AND m.timestamp >= NOW() - ($1 || ' days')::interval
            WHERE u.id = $2
            GROUP BY u.id
            """,
            30, 456
        )
        
        # Должен вернуть строку или None (если пользователя нет)
        assert result is None or isinstance(dict(result), dict)


# =============================================================================
# Конфигурация для запуска с реальной БД
# =============================================================================

def pytest_configure(config):
    """Configure pytest to run integration tests with real database."""
    # Если есть переменная RUN_INTEGRATION_TESTS, запускаем с реальной БД
    import os
    if os.getenv("RUN_INTEGRATION_TESTS") == "1":
        # Нужен DATABASE_URL для реального подключения
        if not os.getenv("DATABASE_URL"):
            pytest.skip("DATABASE_URL not set for integration tests")
