#!/usr/bin/env python3
"""
Analyze chat expectations using DeepSeek and cache results.
"""

import argparse
import asyncio
import logging
import sys
from datetime import datetime
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from services.database import db
from services.expectations import analyze_expectations

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


async def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze chat expectations")
    parser.add_argument("--active-hours", type=int, default=24)
    parser.add_argument("--context-days", type=int, default=3)
    parser.add_argument("--max-messages", type=int, default=50)
    parser.add_argument("--concurrency", type=int, default=3)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=None)

    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("Chat Expectations Analysis")
    logger.info("Active hours: %s", args.active_hours)
    logger.info("Context days: %s", args.context_days)
    logger.info("Max messages: %s", args.max_messages)
    logger.info("Concurrency: %s", args.concurrency)
    logger.info("Force: %s", args.force)
    logger.info("Dry run: %s", args.dry_run)
    logger.info("=" * 60)

    await db.connect()

    try:
        result = await analyze_expectations(
            force=args.force,
            active_hours=args.active_hours,
            context_days=args.context_days,
            max_messages=args.max_messages,
            concurrency=args.concurrency,
            limit=args.limit,
            dry_run=args.dry_run,
        )
    finally:
        await db.close()

    stats = result.get("stats", {})
    logger.info("=" * 60)
    logger.info("Updated at: %s", result.get("updated_at"))
    logger.info("Active chats: %s", stats.get("active_chats"))
    logger.info("Analyzed: %s", stats.get("analyzed"))
    logger.info("Skipped: %s", stats.get("skipped"))
    logger.info("=" * 60)

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
