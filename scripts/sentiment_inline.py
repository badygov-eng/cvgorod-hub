#!/usr/bin/env python3
"""
===============================================================================
Sentiment Analysis - Inline Script
Анализ настроений через DeepSeek API напрямую
===============================================================================

"""

import asyncio
import os
import sys
from datetime import datetime

import asyncpg
import httpx

# Читаем DeepSeek ключ из файла
SECRETS_PATH = "/root/.secrets/cloud/deepseek.env"
DEEPSEEK_API_KEY = None

if os.path.exists(SECRETS_PATH):
    with open(SECRETS_PATH) as f:
        for line in f:
            line = line.strip()
            if line.startswith("DEEPSEEK_API_KEY="):
                DEEPSEEK_API_KEY = line.split("=", 1)[1].strip()
                break

if not DEEPSEEK_API_KEY:
    DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")

print(f"API Key loaded: {DEEPSEEK_API_KEY[:10] if DEEPSEEK_API_KEY else 'NONE'}...", file=sys.stderr)

DEEPSEEK_API_URL = "https://api.deepseek.com/chat/completions"
DEEPSEEK_MODEL = "deepseek-chat"

# Системный промпт
SYSTEM_PROMPT = """Ты — аналитик клиентских настроений.
Определи sentiment сообщения: positive, negative или neutral.
Отвечай только одним словом без пояснений, знаков препинания."""


async def get_messages(pool, date):
    """Получает сообщения за дату без sentiment."""
    date_start = date.replace(hour=0, minute=0, second=0, microsecond=0)
    date_end = date.replace(hour=23, minute=59, second=59, microsecond=999999)

    query = """
        SELECT id, text FROM messages
        WHERE timestamp >= $1 AND timestamp <= $2
        AND text IS NOT NULL AND text != ''
        AND sentiment IS NULL
        ORDER BY id
    """

    async with pool.acquire() as conn:
        return await conn.fetch(query, date_start, date_end)


async def analyze_sentiment(text: str) -> str:
    """Анализирует настроение текста через DeepSeek."""
    if not DEEPSEEK_API_KEY:
        print("  ⚠️  No API key, using neutral", file=sys.stderr)
        return "neutral"

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                DEEPSEEK_API_URL,
                headers={
                    "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": DEEPSEEK_MODEL,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": text[:500]},
                    ],
                    "temperature": 0.1,
                    "max_tokens": 10,
                },
            )

            if response.status_code == 401:
                print("  ❌ 401 Unauthorized - check API key", file=sys.stderr)
                return "neutral"

            response.raise_for_status()
            data = response.json()
            sentiment = data.get("choices", [{}])[0].get("message", {}).get("content", "neutral")

            # Нормализуем
            sentiment = sentiment.strip().lower()
            # Убираем любые символы кроме букв
            sentiment = ''.join(c for c in sentiment if c.isalpha())
            if sentiment not in ["positive", "negative", "neutral"]:
                sentiment = "neutral"
            return sentiment
    except Exception as e:
        print(f"  Ошибка API: {e}", file=sys.stderr)
        return "neutral"


async def update_sentiment(pool, message_id: int, sentiment: str):
    """Обновляет sentiment в базе."""
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE messages SET sentiment = $1 WHERE id = $2",
            sentiment, message_id
        )


async def main():
    date_str = sys.argv[1] if len(sys.argv) > 1 else "2026-01-12"
    date = datetime.strptime(date_str, "%Y-%m-%d")

    # Подключение к БД
    database_url = os.getenv("DATABASE_URL", "postgresql://cvgorod@localhost:5433/cvgorod_hub")
    pool = await asyncpg.create_pool(database_url, min_size=2, max_size=5)

    try:
        messages = await get_messages(pool, date)
        print(f"Найдено сообщений без sentiment: {len(messages)}")

        if not messages:
            print("Нечего обрабатывать!")
            return

        stats = {"positive": 0, "negative": 0, "neutral": 0}

        for i, msg in enumerate(messages):
            msg_id = msg["id"]
            text = msg["text"]

            print(f"[{i+1}/{len(messages)}] {text[:60]}...")

            sentiment = await analyze_sentiment(text)
            await update_sentiment(pool, msg_id, sentiment)
            stats[sentiment] += 1

            print(f"  → {sentiment}")

            # Пауза между запросами
            await asyncio.sleep(0.3)

        print("\n" + "=" * 50)
        print("РЕЗУЛЬТАТЫ:")
        print(f"  ✅ Positive: {stats['positive']}")
        print(f"  ❌ Negative: {stats['negative']}")
        print(f"  ⚪ Neutral: {stats['neutral']}")
        print("=" * 50)

    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
