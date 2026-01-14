"""
Unit tests for services/intent_classifier.py
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class TestIntentClassifier:
    """Tests for IntentClassifier class."""

    def test_classify_prompt_format(self):
        """Test that classification prompt is properly formatted."""
        from services.intent_classifier import IntentClassifier

        classifier = IntentClassifier(api_key="test-key")

        # Check that the prompt template exists and is properly formatted
        assert "Классифицируй сообщение клиента" in classifier.CLASSIFY_PROMPT
        assert "intent:" in classifier.CLASSIFY_PROMPT
        assert "sentiment:" in classifier.CLASSIFY_PROMPT

    def test_classify_prompt_includes_examples(self):
        """Test that prompt includes classification examples."""
        from services.intent_classifier import IntentClassifier

        classifier = IntentClassifier(api_key="test-key")

        # Check examples are included
        assert "Сколько стоят тюльпаны?" in classifier.CLASSIFY_PROMPT
        assert "Беру 50 шт роз" in classifier.CLASSIFY_PROMPT
        assert "Пришли бракованные цветы!" in classifier.CLASSIFY_PROMPT

    @pytest.mark.asyncio
    async def test_classify_returns_message_analysis(self, mock_deepseek_response):
        """Test classify method returns MessageAnalysis."""
        from services.intent_classifier import IntentClassifier

        classifier = IntentClassifier(api_key="test-key")

        with patch("services.intent_classifier.httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.json.return_value = mock_deepseek_response
            mock_response.raise_for_status = MagicMock()

            mock_client_instance = MagicMock()
            mock_client_instance.post = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client.return_value.__aexit__ = AsyncMock()

            result = await classifier.classify(message_id=1, text="Сколько стоят тюльпаны?")

            assert result.message_id == 1
            assert result.intent == "question"
            assert result.sentiment == "neutral"
            assert result.confidence == 0.9

    @pytest.mark.asyncio
    async def test_classify_handles_json_parse_error(self):
        """Test classify handles invalid JSON response."""
        from services.intent_classifier import IntentClassifier

        classifier = IntentClassifier(api_key="test-key")

        invalid_response = {
            "choices": [
                {
                    "message": {
                        "content": "This is not valid JSON"
                    }
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5}
        }

        with patch("services.intent_classifier.httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.json.return_value = invalid_response
            mock_response.raise_for_status = MagicMock()

            mock_client_instance = MagicMock()
            mock_client_instance.post = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client.return_value.__aexit__ = AsyncMock()

            result = await classifier.classify(message_id=1, text="Test message")

            # Should return fallback values on JSON parse error
            assert result.intent == "unknown"
            assert result.sentiment == "unknown"
            assert result.confidence == 0.0

    @pytest.mark.asyncio
    async def test_classify_handles_api_error(self):
        """Test classify handles API errors gracefully."""
        from services.intent_classifier import IntentClassifier

        classifier = IntentClassifier(api_key="test-key")

        with patch("services.intent_classifier.httpx.AsyncClient") as mock_client:
            mock_client_instance = MagicMock()
            mock_client_instance.post = AsyncMock(side_effect=Exception("API Error"))
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client.return_value.__aexit__ = AsyncMock()

            result = await classifier.classify(message_id=1, text="Test message")

            # Should return fallback values on error
            assert result.intent == "unknown"
            assert result.sentiment == "unknown"
            assert result.confidence == 0.0
            assert result.tokens_used == 0

    @pytest.mark.asyncio
    async def test_classify_uses_correct_model(self, mock_deepseek_response):
        """Test classify uses configured model."""
        from services.intent_classifier import IntentClassifier

        classifier = IntentClassifier(api_key="test-key")
        classifier.model = "deepseek-chat"

        with patch("services.intent_classifier.httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.json.return_value = mock_deepseek_response
            mock_response.raise_for_status = MagicMock()

            mock_client_instance = MagicMock()
            mock_client_instance.post = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client.return_value.__aexit__ = AsyncMock()

            await classifier.classify(message_id=1, text="Test message")

            # Verify the model was passed correctly
            call_args = mock_client_instance.post.call_args
            assert call_args[1]["json"]["model"] == "deepseek-chat"

    @pytest.mark.asyncio
    async def test_classify_includes_system_prompt(self, mock_deepseek_response):
        """Test classify includes system prompt."""
        from services.intent_classifier import IntentClassifier

        classifier = IntentClassifier(api_key="test-key")

        with patch("services.intent_classifier.httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.json.return_value = mock_deepseek_response
            mock_response.raise_for_status = MagicMock()

            mock_client_instance = MagicMock()
            mock_client_instance.post = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client.return_value.__aexit__ = AsyncMock()

            await classifier.classify(message_id=1, text="Test message")

            # Verify system prompt is included
            call_args = mock_client_instance.post.call_args
            messages = call_args[1]["json"]["messages"]
            assert len(messages) == 2
            assert messages[0]["role"] == "system"
            assert "классифицируешь сообщения клиентов" in messages[0]["content"]

    @pytest.mark.asyncio
    async def test_classify_respects_text_length_limit(self, mock_deepseek_response):
        """Test classify limits text length."""
        from services.intent_classifier import IntentClassifier

        classifier = IntentClassifier(api_key="test-key")

        # Create a very long text
        long_text = "A" * 1000

        with patch("services.intent_classifier.httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.json.return_value = mock_deepseek_response
            mock_response.raise_for_status = MagicMock()

            mock_client_instance = MagicMock()
            mock_client_instance.post = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client.return_value.__aexit__ = AsyncMock()

            await classifier.classify(message_id=1, text=long_text)

            # Verify text was truncated to 500 chars in the prompt
            call_args = mock_client_instance.post.call_args
            user_content = call_args[1]["json"]["messages"][1]["content"]
            # Проверяем что в промпте текст урезан (500 'A' вместо 1000)
            assert "A" * 500 in user_content  # Урезанный текст присутствует
            assert "A" * 501 not in user_content  # Полный текст НЕ присутствует


class TestMessageAnalysis:
    """Tests for MessageAnalysis dataclass."""

    def test_message_analysis_creation(self):
        """Test MessageAnalysis can be created."""
        from services.intent_classifier import MessageAnalysis

        analysis = MessageAnalysis(
            message_id=1,
            intent="order",
            sentiment="positive",
            entities={"product": "roses", "quantity": 50},
            confidence=0.95,
            model_used="deepseek-chat",
            tokens_used=100,
            processing_time_ms=500
        )

        assert analysis.message_id == 1
        assert analysis.intent == "order"
        assert analysis.sentiment == "positive"
        assert analysis.entities["product"] == "roses"
        assert analysis.confidence == 0.95
        assert analysis.model_used == "deepseek-chat"
        assert analysis.tokens_used == 100
        assert analysis.processing_time_ms == 500

    def test_message_analysis_default_values(self):
        """Test MessageAnalysis with minimal data."""
        from services.intent_classifier import MessageAnalysis

        analysis = MessageAnalysis(
            message_id=1,
            intent="unknown",
            sentiment="neutral",
            entities={},
            confidence=0.0,
            model_used="",
            tokens_used=0,
            processing_time_ms=0
        )

        assert analysis.intent == "unknown"
        assert analysis.confidence == 0.0
