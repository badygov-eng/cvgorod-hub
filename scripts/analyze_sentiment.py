#!/usr/bin/env python3
"""
===============================================================================
Sentiment Analysis Script - Анализ настроений клиентов через DeepSeek

Заполняет поле sentiment для сообщений за указанный день.
Использует DeepSeek для определения настроения: positive, neutral, negative

Использование:
    python scripts/analyze_sentiment.py --date 2026-01-12 --limit 100
    python scripts/analyze_sentiment.py --dry-run  # Тестовый прогон
===============================================================================

"""

import argparse
import asyncio
import logging
import sys
from datetime import datetime
from pathlib import Path

# Добавляем путь к MCP shared modules
sys.path.insert(0, str(Path.home() / "MCP"))

# Добавляем путь к проекту
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv

load_dotenv(project_root / ".env.local", override=True)

import asyncpg
from MCP.shared.llm import DeepSeekClient

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# Системный промпт для анализа настроений
SENTIMENT_SYSTEM_PROMPT = """Ты — аналитик клиентских настроений для службы поддержки.
Твоя задача — определить эмоциональный окрас сообщения клиента.

Возможные значения sentiment:
- positive: клиент доволен, благодарен, рад, выражает удовлетворение
- negative: клиент недоволен, жалуется, возмущается, есть проблема
- neutral: нейтральный вопрос, просто информация, без эмоций

Отвечай ТОЛЬКО одним словом: positive, negative или neutral.
Не добавляй никаких пояснений, комментариев или знаков препинания."""


async def get_messages_for_date(
    pool: asyncpg.Pool,
    date: datetime,
    limit: int = 100,
    offset: int = 0,
) -> list[dict]:
    """
    Получает сообщения за указанный день.

    Args:
        pool: Пул соединений к БД
        date: Дата для выборки
        limit: Максимум сообщений
        offset: Смещение для пагинации

    Returns:
        Список сообщений
    """
    date_start = date.replace(hour=0, minute=0, second=0, microsecond=0)
    date_end = date.replace(hour=23, minute=59, second=59, microsecond=999999)

    query = """
        SELECT
            m.id,
            m.text,
            m.chat_id,
            c.name as chat_name,
            m.user_id,
            u.username,
            u.first_name,
            m.timestamp
        FROM messages m
        LEFT JOIN chats c ON m.chat_id = c.id
        LEFT JOIN users u ON m.user_id = u.id
        WHERE m.timestamp >= $1
            AND m.timestamp <= $2
            AND m.text IS NOT NULL
            AND m.text != ''
            AND m.sentiment IS NULL  -- Только сообщения без sentiment
        ORDER BY m.timestamp ASC
        LIMIT $3 OFFSET $4
    """

    async with pool.acquire() as conn:
        rows = await conn.fetch(query, date_start, date_end, limit, offset)

    return [dict(row) for row in rows]


async def update_sentiment(
    pool: asyncpg.Pool,
    message_id: int,
    sentiment: str,
) -> None:
    """Обновляет поле sentiment для сообщения."""
    query = "UPDATE messages SET sentiment = $1 WHERE id = $2"
    async with pool.acquire() as conn:
        await conn.execute(query, sentiment, message_id)


async def analyze_sentiment_batch(
    client: DeepSeekClient,
    messages: list[dict],
    batch_size: int = 10,
) -> dict[int, str]:
    """
    Анализирует настроения для batch сообщений через DeepSeek.

    Args:
        client: DeepSeek клиент
        messages: Список сообщений
        batch_size: Размер батча

    Returns:
        Словарь {message_id: sentiment}
    """
    results = {}

    for i in range(0, len(messages), batch_size):
        batch = messages[i : i + batch_size]

        # Формируем промпт с несколькими сообщениями
        messages_text = "\n---\n".join(
            f"[{idx + 1}] {msg['text'][:200]}"
            for idx, msg in enumerate(batch)
        )

        prompt = f"""Проанализируй настроения следующих {len(batch)} сообщений клиентов.
Для каждого сообщения определи sentiment (positive/negative/neutral).

{messages_text}

Ответ в формате JSON:
{{"results": [
    {{"index": 1, "sentiment": "positive"}},
    {{"index": 2, "sentiment": "neutral"}},
    ...
]}}"""

        try:
            response = await client.chat_json(
                message=prompt,
                system_prompt=SENTIMENT_SYSTEM_PROMPT,
                temperature=0.1,
                max_tokens=500,
            )

            if response and "results" in response:
                for item in response["results"]:
                    idx = item.get("index", 0) - 1  # Индекс в базе (1-based → 0-based)
                    sentiment = item.get("sentiment", "neutral").lower()

                    # Валидация sentiment
                    if sentiment not in ["positive", "negative", "neutral"]:
                        sentiment = "neutral"

                    if 0 <= idx < len(batch):
                        msg = batch[idx]
                        results[msg["id"]] = sentiment

                        logger.debug(
                            f"  [{msg['id']}] {sentiment}: {msg['text'][:50]}..."
                        )
            else:
                # Если JSON не получен, используем fallback
                logger.warning(f"  Не удалось распарсить ответ для батча {i//batch_size + 1}")
                for msg in batch:
                    results[msg["id"]] = "neutral"

        except Exception as e:
            logger.error(f"  Ошибка при анализе батча {i//batch_size + 1}: {e}")
            # Fallback на neutral
            for msg in batch:
                results[msg["id"]] = "neutral"

    return results


async def process_day(
    date: datetime,
    limit: int = 100,
    dry_run: bool = False,
) -> dict:
    """
    Обрабатывает все сообщения за день и заполняет sentiment.

    Returns:
        Статистика обработки
    """
    stats = {
        "date": date.strftime("%Y-%m-%d"),
        "total_processed": 0,
        "positive": 0,
        "negative": 0,
        "neutral": 0,
        "errors": 0,
        "cost_usd": 0.0,
        "tokens_used": 0,
    }

    # Подключение к БД
    database_url = "postgresql://cvgorod:cvgorod_secret_2024@postgres:5432/cvgorod_hub"
    pool = await asyncpg.create_pool(
        database_url,
        min_size=2,
        max_size=5,
        command_timeout=30,
    )

    try:
        # Инициализация DeepSeek
        client = DeepSeekClient(timeout=60.0)

        offset = 0
        batch_num = 0

        while True:
            # Получаем порцию сообщений
            messages = await get_messages_for_date(pool, date, limit=limit, offset=offset)

            if not messages:
                logger.info("  Все сообщения обработаны!")
                break

            batch_num += 1
            logger.info(
                f"[{date.strftime('%Y-%m-%d')}] Батч {batch_num}: "
                f"{len(messages)} сообщений (offset={offset})"
            )

            if dry_run:
                # Dry run — просто показываем сообщения
                for msg in messages[:3]:  # Первые 3
                    logger.info(f"  [{msg['id']}] {msg['text'][:80]}...")
                stats["total_processed"] += len(messages)
                offset += limit
                continue

            # Анализируем настроения
            sentiments = await analyze_sentiment_batch(client, messages, batch_size=10)

            # Обновляем БД
            for msg_id, sentiment in sentiments.items():
                await update_sentiment(pool, msg_id, sentiment)
                stats["total_processed"] += 1
                stats[sentiment] += 1

            # Статистика от DeepSeek
            client_stats = client.get_stats()
            stats["cost_usd"] += client_stats.get("cost_usd", 0)
            stats["tokens_used"] += client_stats.get("total_tokens", 0)

            logger.info(
                f"  → Обработано: {len(sentiments)}, "
                f"стоимость: ${client_stats.get('cost_usd', 0):.6f}"
            )

            offset += limit

            # Небольшая пауза между батчами
            await asyncio.sleep(0.5)

            # Лимит на всякий случай
            if offset > 10000:
                logger.warning("  Достигнут лимит обработки (10000 сообщений)")
                break

    finally:
        await pool.close()

    return stats


async def main():
    """Главная функция."""
    parser = argparse.ArgumentParser(
        description="Анализ настроений клиентов через DeepSeek"
    )
    parser.add_argument(
        "--date", "-d",
        default="2026-01-12",
        help="Дата для анализа (YYYY-MM-DD), по умолчанию: 2026-01-12"
    )
    parser.add_argument(
        "--limit", "-l",
        type=int,
        default=100,
        help="Максимум сообщений за один запрос к БД"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Тестовый прогон без реального анализа"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Подробное логирование"
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Парсим дату
    try:
        date = datetime.strptime(args.date, "%Y-%m-%d")
    except ValueError:
        logger.error(f"Неверный формат даты: {args.date}. Используйте YYYY-MM-DD")
        return 1

    logger.info("=" * 60)
    logger.info(f"  Sentiment Analysis для {args.date}")
    logger.info(f"  Режим: {'DRY RUN' if args.dry_run else 'ПРОДАКШЕН'}")
    logger.info("=" * 60)

    # Проверяем, есть ли сообщения за этот день
    database_url = "postgresql://cvgorod:cvgorod_secret_2024@postgres:5432/cvgorod_hub"
    pool = await asyncpg.create_pool(database_url, min_size=1, max_size=2)

    date_start = date.replace(hour=0, minute=0, second=0)
    date_end = date.replace(hour=23, minute=59, second=59)

    async with pool.acquire() as conn:
        count = await conn.fetchval("""
            SELECT COUNT(*) FROM messages
            WHERE timestamp >= $1 AND timestamp <= $2
            AND sentiment IS NULL
        """, date_start, date_end)

    await pool.close()

    logger.info(f"Сообщений без sentiment за {args.date}: {count}")

    if count == 0:
        logger.info("Нечего обрабатывать!")
        return 0

    if args.dry_run:
        logger.info("Пропуск анализа в dry-run режиме")
        return 0

    # Запускаем обработку
    stats = await process_day(date, limit=args.limit, dry_run=args.dry_run)

    # Выводим результаты
    logger.info("")
    logger.info("=" * 60)
    logger.info("  РЕЗУЛЬТАТЫ")
    logger.info("=" * 60)
    logger.info(f"  Дата: {stats['date']}")
    logger.info(f"  Всего обработано: {stats['total_processed']}")
    logger.info(f"  ✅ Positive: {stats['positive']}")
    logger.info(f"  ⚪ Neutral: {stats['neutral']}")
    logger.info(f"  ❌ Negative: {stats['negative']}")
    logger.info(f"  💰 Потрачено: ${stats['cost_usd']:.6f}")
    logger.info(f"  📊 Токенов: {stats['tokens_used']:,}")
    logger.info("=" * 60)

    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
