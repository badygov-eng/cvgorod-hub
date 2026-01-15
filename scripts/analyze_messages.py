#!/usr/bin/env python3
"""
===============================================================================
DeepSeek Intent + Sentiment Analysis Script

Анализирует сообщения за последние N дней и заполняет message_analysis.
Только клиентские сообщения (не staff/боты).

Использование:
    python scripts/analyze_messages.py --days 30 --batch-size 50
    python scripts/analyze_messages.py --dry-run
===============================================================================
"""

import argparse
import asyncio
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Добавляем путь к проекту
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from config import settings
from services.database import db
from services.intent_classifier import IntentClassifier

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


async def fetch_batch(
    since: datetime,
    until: datetime,
    last_ts: datetime,
    last_id: int,
    limit: int,
) -> list[dict]:
    query = """
        SELECT
            m.id,
            m.text,
            m.timestamp,
            m.chat_id,
            m.user_id
        FROM messages m
        LEFT JOIN users u ON m.user_id = u.id
        LEFT JOIN user_roles ur ON u.role_id = ur.id
        LEFT JOIN message_analysis ma ON m.id = ma.message_id
        WHERE m.timestamp >= $1
            AND m.timestamp <= $2
            AND m.text IS NOT NULL
            AND m.text != ''
            AND ma.message_id IS NULL
            AND COALESCE(ur.is_bot, FALSE) = FALSE
            AND COALESCE(ur.is_staff, FALSE) = FALSE
            AND COALESCE(u.is_manager, FALSE) = FALSE
            AND (
                m.timestamp > $3
                OR (m.timestamp = $3 AND m.id > $4)
            )
        ORDER BY m.timestamp ASC, m.id ASC
        LIMIT $5
    """

    rows = await db.fetch(query, since, until, last_ts, last_id, limit)
    return [dict(row) for row in rows]


async def analysis_exists(message_id: int) -> bool:
    return await db.fetchval(
        "SELECT 1 FROM message_analysis WHERE message_id = $1",
        message_id,
    ) is not None


async def process_message(
    classifier: IntentClassifier,
    msg: dict,
    semaphore: asyncio.Semaphore,
    dry_run: bool,
) -> tuple[bool, str]:
    async with semaphore:
        if dry_run:
            return True, "dry_run"

        if await analysis_exists(msg["id"]):
            return False, "skipped_exists"

        analysis = await classifier.classify(msg["id"], msg["text"])
        await classifier.save_analysis(analysis)
        return True, analysis.intent


async def main() -> int:
    parser = argparse.ArgumentParser(
        description="DeepSeek intent/sentiment analysis for client messages",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="Сколько дней назад анализировать (по умолчанию: 30)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=50,
        help="Размер батча выборки (по умолчанию: 50)",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=5,
        help="Количество параллельных запросов к LLM",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Прогон без сохранения результатов",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Подробное логирование",
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    if not settings.DEEPSEEK_API_KEY and not args.dry_run:
        logger.error("DEEPSEEK_API_KEY не задан")
        return 1

    since = datetime.utcnow() - timedelta(days=args.days)
    until = datetime.utcnow()

    logger.info("=" * 60)
    logger.info("Intent + Sentiment Analysis")
    logger.info("Период: %s → %s", since.isoformat(), until.isoformat())
    logger.info("Batch size: %s, concurrency: %s", args.batch_size, args.concurrency)
    logger.info("Режим: %s", "DRY RUN" if args.dry_run else "PROD")
    logger.info("=" * 60)

    await db.connect()

    classifier = IntentClassifier()
    semaphore = asyncio.Semaphore(args.concurrency)

    total_processed = 0
    total_saved = 0
    intent_counts: dict[str, int] = {}

    last_ts = since
    last_id = 0
    batch_num = 0

    try:
        while True:
            batch = await fetch_batch(
                since=since,
                until=until,
                last_ts=last_ts,
                last_id=last_id,
                limit=args.batch_size,
            )

            if not batch:
                logger.info("Все сообщения обработаны")
                break

            batch_num += 1
            logger.info(
                "Батч %s: %s сообщений (последний ts=%s)",
                batch_num,
                len(batch),
                batch[-1]["timestamp"],
            )

            tasks = [
                process_message(classifier, msg, semaphore, args.dry_run)
                for msg in batch
            ]
            results = await asyncio.gather(*tasks)

            for saved, intent in results:
                total_processed += 1
                if saved:
                    total_saved += 1
                intent_counts[intent] = intent_counts.get(intent, 0) + 1

            last_ts = batch[-1]["timestamp"]
            last_id = batch[-1]["id"]

            await asyncio.sleep(0.2)

    finally:
        await db.close()

    logger.info("=" * 60)
    logger.info("РЕЗУЛЬТАТЫ")
    logger.info("Всего обработано: %s", total_processed)
    logger.info("Сохранено: %s", total_saved)
    for intent, count in sorted(intent_counts.items()):
        logger.info("  %s: %s", intent, count)
    logger.info("=" * 60)

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
