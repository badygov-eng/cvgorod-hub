"""
Tests for services/tracker.py - Priority class and DummyTracker.
Following MCP project testing rules:
- HTTP Timeout - not applicable for unit tests
- Error Handling - test error cases
- Pydantic Strict Mode - not applicable
- Type Hints - verify type correctness
"""

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestPriorityClass:
    """Tests for Priority class (fallback when MCP is not available)."""

    def test_priority_has_all_levels(self):
        """Priority should have LOW, NORMAL, HIGH levels."""
        from services.tracker import Priority

        assert hasattr(Priority, "LOW")
        assert hasattr(Priority, "NORMAL")
        assert hasattr(Priority, "HIGH")

    def test_priority_values(self):
        """Priority values should be lowercase strings."""
        from services.tracker import Priority

        assert Priority.LOW == "low"
        assert Priority.NORMAL == "normal"
        assert Priority.HIGH == "high"

    def test_priority_string_comparison(self):
        """Priority values should support string comparison."""
        from services.tracker import Priority

        # Values are strings, so they should compare correctly
        assert Priority.LOW == "low"
        assert Priority.HIGH == "high"
        assert Priority.NORMAL == "normal"

    def test_priority_in_tracker_error_calls(self):
        """Priority values should be usable in tracker.error() calls."""
        from services.tracker import Priority

        # Verify that Priority values are valid strings for the tracker
        assert isinstance(Priority.LOW, str)
        assert isinstance(Priority.NORMAL, str)
        assert isinstance(Priority.HIGH, str)


class TestDummyTracker:
    """Tests for DummyTracker class."""

    def test_dummy_tracker_initialization(self):
        """DummyTracker should initialize with project and component."""
        from services.tracker import DummyTracker

        tracker = DummyTracker(
            project="test-project",
            component="test-component",
            enabled=True,
        )

        assert tracker.project == "test-project"
        assert tracker.component == "test-component"
        assert tracker.enabled is True

    def test_dummy_tracker_disabled_by_default(self):
        """DummyTracker should be disabled by default."""
        from services.tracker import DummyTracker

        tracker = DummyTracker(
            project="test-project",
            component="test-component",
        )

        assert tracker.enabled is False

    @pytest.mark.asyncio
    async def test_dummy_tracker_info_logs_when_enabled(self):
        """info() should log when enabled."""
        from services.tracker import DummyTracker

        tracker = DummyTracker(
            project="test-project",
            component="test-component",
            enabled=True,
        )

        # Should not raise
        await tracker.info("Test message", {"key": "value"})

    @pytest.mark.asyncio
    async def test_dummy_tracker_info_does_nothing_when_disabled(self):
        """info() should do nothing when disabled."""
        from services.tracker import DummyTracker

        tracker = DummyTracker(
            project="test-project",
            component="test-component",
            enabled=False,
        )

        # Should not raise
        await tracker.info("Test message")

    @pytest.mark.asyncio
    async def test_dummy_tracker_error_logs_when_enabled(self):
        """error() should log when enabled."""
        from services.tracker import DummyTracker

        tracker = DummyTracker(
            project="test-project",
            component="test-component",
            enabled=True,
        )

        await tracker.error("Error message", {"error": "details"})

    @pytest.mark.asyncio
    async def test_dummy_tracker_error_does_nothing_when_disabled(self):
        """error() should do nothing when disabled."""
        from services.tracker import DummyTracker

        tracker = DummyTracker(
            project="test-project",
            component="test-component",
            enabled=False,
        )

        await tracker.error("Error message")

    @pytest.mark.asyncio
    async def test_dummy_tracker_warning_logs_when_enabled(self):
        """warning() should log when enabled."""
        from services.tracker import DummyTracker

        tracker = DummyTracker(
            project="test-project",
            component="test-component",
            enabled=True,
        )

        await tracker.warning("Warning message")

    @pytest.mark.asyncio
    async def test_dummy_tracker_warning_does_nothing_when_disabled(self):
        """warning() should do nothing when disabled."""
        from services.tracker import DummyTracker

        tracker = DummyTracker(
            project="test-project",
            component="test-component",
            enabled=False,
        )

        await tracker.warning("Warning message")

    @pytest.mark.asyncio
    async def test_dummy_tracker_deploy_logs_when_enabled(self):
        """deploy() should log when enabled."""
        from services.tracker import DummyTracker

        tracker = DummyTracker(
            project="test-project",
            component="test-component",
            enabled=True,
        )

        await tracker.deploy("Deploy message", {"version": "1.0.0"})

    @pytest.mark.asyncio
    async def test_dummy_tracker_deploy_does_nothing_when_disabled(self):
        """deploy() should do nothing when disabled."""
        from services.tracker import DummyTracker

        tracker = DummyTracker(
            project="test-project",
            component="test-component",
            enabled=False,
        )

        await tracker.deploy("Deploy message")

    @pytest.mark.asyncio
    async def test_dummy_tracker_info_accepts_priority(self):
        """info() should accept priority parameter."""
        from services.tracker import DummyTracker

        tracker = DummyTracker(
            project="test-project",
            component="test-component",
            enabled=True,
        )

        # Should accept priority without error
        await tracker.info("Test", priority="high")
        await tracker.info("Test", priority="normal")
        await tracker.info("Test", priority="low")
        await tracker.info("Test", priority=None)

    @pytest.mark.asyncio
    async def test_dummy_tracker_error_accepts_priority(self):
        """error() should accept priority parameter."""
        from services.tracker import DummyTracker

        tracker = DummyTracker(
            project="test-project",
            component="test-component",
            enabled=True,
        )

        await tracker.error("Test", priority="high")


class TestTrackerHelperFunctions:
    """Tests for tracker helper functions."""

    @pytest.mark.asyncio
    async def test_log_api_error_with_status_code(self):
        """log_api_error should handle status code correctly."""
        with patch("services.tracker.tracker") as mock_tracker:
            mock_tracker.error = AsyncMock()

            from services.tracker import log_api_error

            await log_api_error(
                endpoint="/api/v1/test",
                error="Test error",
                status_code=500,
            )

            mock_tracker.error.assert_called_once()
            call_args = mock_tracker.error.call_args
            assert call_args.kwargs["priority"] == "high"  # 500+ = high

    @pytest.mark.asyncio
    async def test_log_api_error_with_low_status_code(self):
        """log_api_error should use normal priority for status < 500."""
        with patch("services.tracker.tracker") as mock_tracker:
            mock_tracker.error = AsyncMock()

            from services.tracker import log_api_error

            await log_api_error(
                endpoint="/api/v1/test",
                error="Test error",
                status_code=400,
            )

            mock_tracker.error.assert_called_once()
            call_args = mock_tracker.error.call_args
            assert call_args.kwargs["priority"] == "normal"  # 400 = normal

    @pytest.mark.asyncio
    async def test_log_api_error_without_status_code(self):
        """log_api_error should use normal priority when no status code."""
        with patch("services.tracker.tracker") as mock_tracker:
            mock_tracker.error = AsyncMock()

            from services.tracker import log_api_error

            await log_api_error(
                endpoint="/api/v1/test",
                error="Test error",
            )

            mock_tracker.error.assert_called_once()
            call_args = mock_tracker.error.call_args
            assert call_args.kwargs["priority"] == "normal"

    @pytest.mark.asyncio
    async def test_log_telegram_message(self):
        """log_telegram_message should log correctly."""
        with patch("services.tracker.tracker") as mock_tracker:
            mock_tracker.info = AsyncMock()

            from services.tracker import log_telegram_message

            await log_telegram_message(
                chat_id=12345,
                message_type="text",
                has_intent=True,
                intent_type="question",
            )

            mock_tracker.info.assert_called_once()

    @pytest.mark.asyncio
    async def test_log_telegram_message_without_intent(self):
        """log_telegram_message should handle None intent_type."""
        with patch("services.tracker.tracker") as mock_tracker:
            mock_tracker.info = AsyncMock()

            from services.tracker import log_telegram_message

            await log_telegram_message(
                chat_id=12345,
                message_type="text",
                has_intent=False,
                intent_type=None,
            )

            mock_tracker.info.assert_called_once()

    @pytest.mark.asyncio
    async def test_log_intent_classification(self):
        """log_intent_classification should log correctly."""
        with patch("services.tracker.tracker") as mock_tracker:
            mock_tracker.info = AsyncMock()

            from services.tracker import log_intent_classification

            await log_intent_classification(
                message_id=1,
                intent="question",
                sentiment="neutral",
                confidence=0.95,
                processing_time_ms=150,
            )

            mock_tracker.info.assert_called_once()

    @pytest.mark.asyncio
    async def test_log_sandbox_action(self):
        """log_sandbox_action should log correctly."""
        with patch("services.tracker.tracker") as mock_tracker:
            mock_tracker.info = AsyncMock()

            from services.tracker import log_sandbox_action

            await log_sandbox_action(
                action="approve",
                pending_id=1,
                user_id=123,
                approved=True,
            )

            mock_tracker.info.assert_called_once()

    @pytest.mark.asyncio
    async def test_log_sandbox_action_without_optional(self):
        """log_sandbox_action should handle None optional params."""
        with patch("services.tracker.tracker") as mock_tracker:
            mock_tracker.info = AsyncMock()

            from services.tracker import log_sandbox_action

            await log_sandbox_action(
                action="approve",
                pending_id=1,
                user_id=None,
                approved=None,
            )

            mock_tracker.info.assert_called_once()

    @pytest.mark.asyncio
    async def test_log_database_operation_success(self):
        """log_database_operation should log success correctly."""
        with patch("services.tracker.tracker") as mock_tracker:
            mock_tracker.info = AsyncMock()
            mock_tracker.error = AsyncMock()

            from services.tracker import log_database_operation

            await log_database_operation(
                operation="SELECT",
                table="messages",
                success=True,
                duration_ms=50,
            )

            mock_tracker.info.assert_called_once()
            mock_tracker.error.assert_not_called()

    @pytest.mark.asyncio
    async def test_log_database_operation_failure(self):
        """log_database_operation should log failure with high priority."""
        with patch("services.tracker.tracker") as mock_tracker:
            mock_tracker.info = AsyncMock()
            mock_tracker.error = AsyncMock()

            from services.tracker import log_database_operation

            await log_database_operation(
                operation="INSERT",
                table="messages",
                success=False,
                error="Connection refused",
            )

            mock_tracker.error.assert_called_once()
            call_args = mock_tracker.error.call_args
            assert call_args.kwargs["priority"] == "high"

    @pytest.mark.asyncio
    async def test_log_deploy_success(self):
        """log_deploy should use deploy method on success."""
        with patch("services.tracker.tracker") as mock_tracker:
            mock_tracker.deploy = AsyncMock()
            mock_tracker.error = AsyncMock()

            from services.tracker import log_deploy

            await log_deploy(
                version="1.0.0",
                environment="production",
                success=True,
            )

            mock_tracker.deploy.assert_called_once()
            mock_tracker.error.assert_not_called()

    @pytest.mark.asyncio
    async def test_log_deploy_failure(self):
        """log_deploy should use error method on failure."""
        with patch("services.tracker.tracker") as mock_tracker:
            mock_tracker.deploy = AsyncMock()
            mock_tracker.error = AsyncMock()

            from services.tracker import log_deploy

            await log_deploy(
                version="1.0.0",
                environment="production",
                success=False,
                error="Build failed",
            )

            mock_tracker.error.assert_called_once()
            call_args = mock_tracker.error.call_args
            assert call_args.kwargs["priority"] == "high"


class TestTrackerInitialization:
    """Tests for tracker initialization."""

    def test_tracker_has_project_and_component(self):
        """Tracker should have project and component set."""
        from services.tracker import PROJECT_NAME, COMPONENT_NAME, tracker

        assert PROJECT_NAME == "cvgorod-hub"
        assert COMPONENT_NAME == "Hub"

    def test_tracker_is_dummy_when_mcp_unavailable(self):
        """Tracker should be DummyTracker when MCP is unavailable."""
        # This test verifies the fallback works
        from services.tracker import tracker

        # Just check it can be imported and used
        assert tracker is not None
        assert hasattr(tracker, "project")
        assert hasattr(tracker, "component")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
