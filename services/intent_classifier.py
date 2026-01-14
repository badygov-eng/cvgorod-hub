"""
Intent Classifier — LLM обработка сообщений для классификации интентов.

Использует MCP.shared.llm.DeepSeekClient для:
- Centralized logging
- Token tracking
- Cost tracking
- Error handling
"""

import json
import logging
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path

# Add MCP path for shared modules
# Use MCP_PATH env var, or default to ~/MCP
mcp_path = Path(os.getenv("MCP_PATH", str(Path.home() / "MCP")))
if mcp_path.exists() and str(mcp_path) not in sys.path:
    sys.path.insert(0, str(mcp_path))

# httpx нужен для тестов и fallback
import httpx

from config import settings
from services.database import db

# Try to use MCP DeepSeekClient, fallback to direct implementation
try:
    from MCP.shared.llm import DeepSeekClient
    USE_MCP_CLIENT = True
except ImportError:
    USE_MCP_CLIENT = False

logger = logging.getLogger(__name__)


@dataclass
class MessageAnalysis:
    """Результат анализа сообщения."""
    message_id: int
    intent: str  # question, order, complaint, interest, confirmation, other
    sentiment: str  # positive, neutral, negative
    entities: dict
    confidence: float
    model_used: str
    tokens_used: int
    processing_time_ms: int


class IntentClassifier:
    """
    Классификация сообщений через DeepSeek (MCP.shared.llm).

    Features:
    - Real-time классификация с batch режимом
    - Определение интента (question, order, complaint, interest, confirmation)
    - Sentiment analysis (positive, neutral, negative)
    - Извлечение сущностей (товары, количества, цены)
    - Centralized logging через MCP
    """

    # Промпт для классификации
    CLASSIFY_PROMPT = """Ты аналитик цветочной компании. Классифицируй сообщение клиента.

Сообщение: "{message}"

Верни JSON:
{{
  "intent": "question|order|complaint|interest|confirmation|other",
  "sentiment": "positive|neutral|negative",
  "entities": {{"product": "...", "quantity": ..., "price": ...}},
  "confidence": 0.0-1.0,
  "reasoning": "краткое обоснование"
}}

Примеры:
- "Сколько стоят тюльпаны?" -> intent: question, sentiment: neutral
- "Беру 50 шт роз" -> intent: order, sentiment: positive
- "Пришли бракованные цветы!" -> intent: complaint, sentiment: negative
- "Красивые пионы, возьму" -> intent: interest, sentiment: positive
- "Да, заказываю" -> intent: confirmation, sentiment: positive
"""

    def __init__(self, api_key: str | None = None):
        self.model = settings.DEEPSEEK_MODEL

        if USE_MCP_CLIENT:
            # Use MCP DeepSeekClient with centralized logging and tracking
            self._client = DeepSeekClient(
                api_key=api_key or settings.DEEPSEEK_API_KEY,
                model=self.model,
            )
            logger.info("Using MCP.shared.llm.DeepSeekClient")
        else:
            # Fallback to direct httpx implementation
            self.api_key = api_key or settings.DEEPSEEK_API_KEY
            self.base_url = "https://api.deepseek.com/chat/completions"
            logger.warning("MCP client not available, using direct httpx implementation")

    async def classify(
        self,
        message_id: int,
        text: str,
    ) -> MessageAnalysis:
        """
        Классификация одного сообщения.

        Args:
            message_id: ID сообщения в БД
            text: Текст сообщения

        Returns:
            MessageAnalysis с результатами
        """
        start_time = time.time()

        prompt = self.CLASSIFY_PROMPT.format(message=text[:500])  # Ограничиваем длину

        try:
            if USE_MCP_CLIENT:
                # Use MCP client with centralized logging and token tracking
                content = await self._client.chat(
                    message=prompt,
                    system_prompt="Ты классифицируешь сообщения клиентов. Верни ТОЛЬКО JSON без markdown.",
                    temperature=0.3,
                    max_tokens=200,
                    response_format="json",
                )

                # Get token usage from client
                tokens_used = self._client.last_usage.get("total_tokens", 0) if hasattr(self._client, 'last_usage') else 0
            else:
                # Direct httpx implementation (fallback)
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.post(
                        self.base_url,
                        headers={
                            "Authorization": f"Bearer {self.api_key}",
                            "Content-Type": "application/json",
                        },
                        json={
                            "model": self.model,
                            "messages": [
                                {"role": "system", "content": "Ты классифицируешь сообщения клиентов. Верни ТОЛЬКО JSON без markdown."},
                                {"role": "user", "content": prompt},
                            ],
                            "temperature": 0.3,
                            "max_tokens": 200,
                        },
                    )

                    response.raise_for_status()
                    data = response.json()

                    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                    usage = data.get("usage", {})
                    tokens_used = usage.get("prompt_tokens", 0) + usage.get("completion_tokens", 0)

            # Парсим JSON из ответа
            try:
                # Убираем markdown если есть
                clean_content = content.replace("```json", "").replace("```", "").strip()
                result = json.loads(clean_content)
            except json.JSONDecodeError:
                # Fallback — простой парсинг
                result = {
                    "intent": "unknown",
                    "sentiment": "unknown",
                    "entities": {},
                    "confidence": 0.0,
                }

            processing_time = int((time.time() - start_time) * 1000)

            return MessageAnalysis(
                message_id=message_id,
                intent=result.get("intent", "unknown"),
                sentiment=result.get("sentiment", "unknown"),
                entities=result.get("entities", {}),
                confidence=result.get("confidence", 0.5),
                model_used=self.model,
                tokens_used=tokens_used,
                processing_time_ms=processing_time,
            )

        except Exception as e:
            logger.error(f"Intent classification failed: {e}")
            processing_time = int((time.time() - start_time) * 1000)

            return MessageAnalysis(
                message_id=message_id,
                intent="unknown",
                sentiment="unknown",
                entities={},
                confidence=0.0,
                model_used=self.model,
                tokens_used=0,
                processing_time_ms=processing_time,
            )

    async def save_analysis(
        self,
        analysis: MessageAnalysis,
    ) -> int:
        """
        Сохранение результата анализа в БД.

        Args:
            analysis: Результат анализа

        Returns:
            ID записи в message_analysis
        """
        result = await db.execute(
            """
            INSERT INTO message_analysis (
                message_id, intent, sentiment, entities,
                confidence, model_used, tokens_used, processing_time_ms
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            RETURNING id
            """,
            analysis.message_id,
            analysis.intent,
            analysis.sentiment,
            str(analysis.entities),
            analysis.confidence,
            analysis.model_used,
            analysis.tokens_used,
            analysis.processing_time_ms,
        )

        return int(result.split()[-1])


# Глобальный экземпляр
intent_classifier = IntentClassifier()
